#!/usr/bin/python3

import pymongo
import os
import os.path
import requests
import re
import json
import time
from urllib.parse import unquote
from threading import Thread

from mkvtool import mkvtool

BASEURL = "http://10.0.0.5:8080/"

FFMPEG = "ffmpeg"

TIMEOUT = 600 # 10 minutes per chunk 

ROOT_DIR = "dist_enc"
VIDEO_DIR = os.path.join(ROOT_DIR, "original")
CHUNK_DIR = os.path.join(ROOT_DIR, "chunks")
ENCODE_CHUNK_DIR = os.path.join(ROOT_DIR, "encode/chunks")
ENCODE_FINAL_DIR = os.path.join(ROOT_DIR, "encode/final")

class Video:
    def __init__(self):
        self.url = ""
        self.filename = ""
        self.percent = "0%"
        self.state = "uninitialized"
            
    def from_url(self, url):
        self.url = url
        self.filename = unquote(re.sub(".*/", "", self.url))
        self.state = "queued"

class Profile:
    def __init__(self, name, desc = ""):
        self.name = name
        self.cmd = []
        self.desc = desc
    def from_string(self, cmd):
        self.cmd = cmd.split()

class Encode:
    def __init__(self, vid, pid, _in, pname):
        self.vid = vid
        self.pid = pid
        self._in = _in
        self.pname = pname
        self._id = ""
        self.percent = "0%"
        self.state = "initializing"

class Job:
    def __init__(self, _in, p, eid):
        self.eid = eid
        self._in = _in
        self.p = p
        self.out = re.sub(".mkv$", "-" + p["name"] + ".mkv", _in)
        self.cmd = [FFMPEG, "-i"] + [_in] + p["cmd"] + [self.out]
        self.state = "ready"
        print(self.__dict__)
        
class Videos:
    def __init__(self, host, port=27017):
        self.db_host = host
        self.db_port = port
        self.client = None
        self.db = None
        self.workers = []
        self.watchdog = Thread(target=self.watchdog)
        
        for d in [VIDEO_DIR, CHUNK_DIR, ENCODE_CHUNK_DIR, ENCODE_FINAL_DIR]:
            os.makedirs(d, exist_ok=True)
        
        self.watchdog.start()
    
    def watchdog(self):
        while True:
            time.sleep(5)
            print("refreshing watchdog")
            for d in self.workers:
                d.join(5)
                if not d.is_alive():
                    print("Thread joined()")
                    self.workers.remove(d)
            
            self.clear_job_timeouts()
            
            
    def db_connect(self):
        self.client = pymongo.MongoClient(self.db_host, self.db_port)
        self.db = self.client.dist_enc
        self.db.videos.create_index("filename", unique=True)
    
    def update_video(self, v):
        print(v)
        ret = self.db.videos.update_one({"filename": v["filename"]},
              {'$set': dict(filter(lambda kv: kv[0] != '_id', v.items()))})
        print(ret)
    
    def update_encode(self, e):
        print(e)
        ret = self.db.encodes.update_one({"vid": e["vid"], "pid": e["pid"]},
              {'$set': dict(filter(lambda kv: kv[0] != '_id', e.items()))}, upsert=True)
        ret = self.db.encodes.find_one({"vid": e["vid"], "pid": e["pid"]})
        ret["_id"] = str(ret["_id"])
        return ret
    
    def get_profiles(self):
        ret = self.db.profiles.find()
        ps = []
        for p in list(ret):
            p["_id"] = str(p["_id"])
            ps.append(p)
        return json.dumps(ps)
    
        
    def get_profile_by_id(self, _id):
        ret = self.db.profiles.find_one({"_id": pymongo.collection.ObjectId(_id)})
        ret["_id"] = _id
        return ret
    
    def get_encode_by_id(self, _id):
        ret = self.db.encodes.find_one({"_id": pymongo.collection.ObjectId(_id)})
        ret["_id"] = _id
        return ret
    
    def add_video_by_url(self, url):
        print(url)
        v = Video()
        v.from_url(url)
        print(v)
        try:
            ret = self.db.videos.insert_one(v.__dict__)
            print(ret)
        except:
            print("error while inserting")
        v = self.db.videos.find_one({"filename": v.filename})
        print(v)
        v["_id"] = str(v["_id"])
        print(v)
        ret = json.dumps(v)
        print(ret)
        if v["state"] == "ready":
            return ret
        if v["state"] == "downloaded" or v["state"] == "splitting":
            print("starting splitting")
            try:
                downloader = Thread(target=self.split_video, args=(v,))
                downloader.start()
                self.workers.append(downloader)
            except Exception as e:
                print(e)
            return ret
        print("starting downloader")
        try:
            downloader = Thread(target=self.download_video, args=(v,))
            downloader.start()
            self.workers.append(downloader)
        except Exception as e:
            print(e)
        
        print("started downloader")
        return ret
        
    def get_all_videos(self):
        ret = self.db.videos.find()
        vs = []
        for v in list(ret):
            v["_id"] = str(v["_id"])
            vs.append(v)
        return json.dumps(vs)
    
    def get_all_encodes(self):
        ret = self.db.encodes.find()
        es = []
        for e in list(ret):
            e["_id"] = str(e["_id"])
            es.append(e)
        return json.dumps(es)
    
    def get_all_jobs(self):
        ret = self.db.jobs.find()
        js = []
        for j in list(ret):
            j["_id"] = str(j["_id"])
            js.append(j)
        return json.dumps(js)
    
    def get_ready_jobs(self):
        ret = self.db.jobs.find({"state": "ready"})
        js = []
        for j in list(ret):
            j["_id"] = str(j["_id"])
            js.append(j)
        return json.dumps(js)
    
    def get_encode_jobs(self, _id):
        enc = self.get_encode_by_id(_id)
        print(enc)
        ret = self.db.jobs.find({"_id": {'$in': list(map(lambda x: pymongo.collection.ObjectId(x), enc["jobs"]))}})
        js = []
        for j in list(ret):
            j["_id"] = str(j["_id"])
            js.append(j)
        return json.dumps(js)
    
    def get_encode_ready_jobs(self, _id):
        enc = self.get_encode_by_id(_id)
        print(enc)
        ret = self.db.jobs.find({"state": "ready",
                "_id": {'$in': list(map(lambda x: pymongo.collection.ObjectId(x), enc["jobs"]))}})
        js = []
        for j in list(ret):
            j["_id"] = str(j["_id"])
            js.append(j)
        return json.dumps(js)
    
    def get_by_id(self, _id):
        ret = self.db.videos.find_one({"_id": pymongo.collection.ObjectId(_id)})
        ret["_id"] = _id
        return ret
    
    def get_job_by_id(self, _id):
        ret = self.db.jobs.find_one({"_id": pymongo.collection.ObjectId(_id)})
        ret["_id"] = _id
        return ret
    
    def download_video(self, v):
        print("downloading")
        v["state"] = "downloading"
        r = requests.get(v["url"], stream=True)
        v["length"] = 0
        if 'Content-Length' in r.headers:
            v["length"] = int(r.headers['Content-Length'])
        v["have"] = 0
        v["percent"] = "???%"
        with open(os.path.join(VIDEO_DIR, v["filename"]), 'wb') as fd:
            for chunk in r.iter_content(chunk_size=4096):
                v["have"] += fd.write(chunk)
                if v["length"] > 0:
                    v["percent"] = str(v["have"] * 100 / v["length"])[:5] + "%"
                if v["have"] % (1024 * 1024) < 4096:
                    self.update_video(v)
        v["state"] = "downloaded"
        self.update_video(v)
        self.split_video(v)
    
    def upload_video(self, upload, filename):
        v = Video()
        v.filename = filename
        v.state = "uploading"
        try:
            ret = self.db.videos.insert_one(v.__dict__)
            print(ret)
        except:
            print("error while inserting")
            return
        v = self.db.videos.find_one({"filename": v.filename})
        v["_id"] = str(v["_id"])
        v["have"] = 0
        with open(os.path.join(VIDEO_DIR, filename), "wb") as fd:
            chunk = upload.read(4096)
            while len(chunk) > 0:
                v["have"] += len(chunk)
                fd.write(chunk)
                if v["have"] % (1024 * 1024) < 4096:
                    self.update_video(v)
                chunk = upload.read(4096)
        v["state"] = "uploaded"
        self.update_video(v)
        try:
            downloader = Thread(target=self.split_video, args=(v,))
            downloader.start()
            self.workers.append(downloader)
        except Exception as e:
            print(e)
        return json.dumps(v)
    
    def submit_job(self, upload, jid):
        j = self.get_job_by_id(jid)
        j["state"] = "uploading"
        self.set_job(j)
        j["have"] = 0
        with open(os.path.join(ENCODE_CHUNK_DIR, j["out"]), "wb") as fd:
            chunk = upload.read(4096)
            while len(chunk) > 0:
                j["have"] += len(chunk)
                fd.write(chunk)
                if j["have"] % (1024 * 1024) < 4096:
                    self.set_job(j)
                chunk = upload.read(4096)
        try:
            downloader = Thread(target=self.check_merge, args=(j["eid"],))
            downloader.start()
            self.workers.append(downloader)
        except Exception as e:
            print(e)
        j["state"] = "done"
        self.set_job(j)
        
    def check_merge(self, eid):
        enc = self.get_encode_by_id(eid)
        def report(state, percent):
            enc["state"] = state
            enc["percent"] = percent
            self.update_encode(enc)
        done = self.db.jobs.find({"eid": eid, "state": "done"}).count()
        enc["percent"] = str(done * 100.0 / len(enc["jobs"]))[:5] + "%"
        self.update_encode(enc)
        if done == len(enc["jobs"]):
            nb = len(enc["jobs"])
            v = self.get_by_id(enc["vid"])
            p = self.get_profile_by_id(enc["pid"])
            files = [os.path.join(ENCODE_CHUNK_DIR, enc["vid"] + "-" + str(num).zfill(3) + "-" + p["name"] + ".mkv") for num in range(1, nb)]
            out = os.path.join(ENCODE_FINAL_DIR, re.sub(".mkv", "-" + p["name"] + ".mkv", v["filename"]))
            self.update_encode(enc)
            print(files)
            print(out)
            out = mkvtool.merge(files, out, report)
            enc["state"] = "done"
            enc["url"] = BASEURL + "final/" + os.path.basename(out)
            self.update_encode(enc)
            
    def split_video(self, v):
        def report(state, percent):
            v["state"] = state
            v["percent"] = percent
            self.update_video(v)
        i_frames = mkvtool.get_i_frames(os.path.join(VIDEO_DIR, v["filename"]), report)
        v["chunks"] = mkvtool.split(os.path.join(VIDEO_DIR, v["filename"]),
                 os.path.join(CHUNK_DIR, v["_id"] + ".mkv"), i_frames, report)
        v["percent"] = "100%"
        v["state"] = "ready"
        self.update_video(v)
        print(v["chunks"])
    
    def set_profile(self, p):
        profile = Profile(p["name"])
        profile.from_string(p["cmd"])
        if "desc" in p:
            profile.desc = p["desc"]
        self.db.profiles.update_one({"name": p["name"]}, {'$set': profile.__dict__}, upsert=True)
        p = self.db.profiles.find_one({"name": p["name"]})
        print(p)
        p["_id"] = str(p["_id"])
        ret = json.dumps(p)
        return ret
    
    def set_job(self, j):
        self.db.jobs.update_one({"_in": j["_in"], "p": j["p"]},
            {'$set': dict(filter(lambda kv: kv[0] != '_id', j.items()))}, upsert=True)
        j = self.db.jobs.find_one({"_in": j["_in"], "p": j["p"]})
        j["_id"] = str(j["_id"])
        return j
    
    def add_encode(self, e):
        vid = e["vid"]
        pid = e["pid"]
        v = self.get_by_id(vid)
        p = self.get_profile_by_id(pid)
        enc = Encode(vid, pid, v["filename"], p["name"])
        print(enc.__dict__)
        try:
            ret = self.db.encodes.find({"vid": vid, "pid": pid})
            if len(list(ret)) != 0:
                return json.dumps(ret[0])
        except:
            pass
        print(enc)
        enc = self.update_encode(enc.__dict__)
        enc["jobs"] = []
        print(enc)
        self.db.jobs.delete_many({"eid": enc["_id"]})
        encode_adder = Thread(target=self.add_encode_helper, args=(enc, v, p))
        encode_adder.start()
        self.workers.append(encode_adder)
        return json.dumps(enc)

    def add_encode_helper(self, enc, v, p):
        print(v)
        print(p)
        for c in v["chunks"]:
            print(c)
            j = Job(c, p, enc["_id"])
            j = self.set_job(j.__dict__)
            enc["jobs"].append(j["_id"])
        enc["state"] = "ready"
        enc["percent"] = "0%"
        print(enc)
        self.update_encode(enc)
        return json.dumps(enc)
    
    def claim_job(self, _id):
        j = self.get_job_by_id(_id)
        if j["state"] != "ready":
            return json.dumps({"error": "Job not ready."})
        j["state"] = "claimed"
        j["timeout"] = int(time.time() + TIMEOUT)
        print(j)
        self.set_job(j)
        job_desc = {}
        job_desc["chunk_url"] = BASEURL + "chunk/" + j["_in"]
        job_desc["command"] = j["cmd"]
        job_desc["timeout"] = j["timeout"]
        return json.dumps(job_desc)
    
    def clear_job_timeouts(self):
        ret = self.db.jobs.find({"timeout": {'$lte': int(time.time())}})
        for j in list(ret):
            if ["state"] == "claimed":
                j["state"] = "ready"
            j["timeout"] = int(time.time() + TIMEOUT)
            self.set_job(j)
        
