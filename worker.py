#!/usr/bin/python3

import requests
import json
import time
import os
import sys
from subprocess import Popen, PIPE

TIMEOUT = 10

def main():
    if len(sys.argv) > 1:
        BASEURL = sys.argv[1]
    else:
        BASEURL = "http://localhost:8080/"

    while True:
        ret = requests.get(BASEURL + "jobs/ready")
        jobs = ret.json()
        if len(jobs) == 0:
            time.sleep(TIMEOUT)
            continue
        ret = requests.get(BASEURL + "jobs/claim/" + jobs[0]["_id"])
        desc = ret.json()
        ret = requests.get(desc["chunk_url"], stream=True)
        if 'Content-Length' in ret.headers:
            length = int(ret.headers['Content-Length'])
        have = 0
        percent = "???%"
        with open(desc["chunk_url"].split("/")[-1], 'wb') as fd:
            for chunk in ret.iter_content(chunk_size=4096):
                if have % (256 * 1024) < 4096:
                    print(str(have) + "/" + str(length) + " " + percent)
                have += fd.write(chunk)
                if length > 0:
                    percent = str(have * 100 / length)[:5] + "%"
        ffmpeg = Popen(desc["command"])
        ffmpeg.wait()
        files = {"upload": (desc["command"][-1], open(desc["command"][-1], 'rb'), 'application/octet-stream')}
        requests.post(BASEURL + "jobs/submit/" + jobs[0]["_id"], files=files)
        os.remove(desc["chunk_url"].split("/")[-1])
        os.remove(desc["command"][-1])
        
main()
