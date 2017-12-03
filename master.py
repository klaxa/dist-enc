#!/usr/bin/python3

from bottle import get, post, run, request, response, static_file, redirect, abort
import json
from videos import Videos, CHUNK_DIR, ENCODE_FINAL_DIR
import traceback
from urllib.parse import unquote

vids = Videos("10.0.0.1")
vids.db_connect()

@get("/")
def goto_index():
    redirect("/app/html/dashboard.html")

@get("/app/<filepath:path>")
def app(filepath):
    return static_file(filepath, root="./app")

@post("/upload/url")
def upload_url():
    try:
        data = str(request.body.read())[2:-1]
        print(data)
        data_dict = json.loads(data)
        url = data_dict["url"]
        print(url)
        return vids.add_video_by_url(url)
    except Exception as e:
        abort(500)

@post("/upload/file/<filename>")
def upload(filename):
    upload = request.body
    return vids.upload_video(upload, filename)

@get("/videos")
def videos():
    return vids.cache["videos"]

@post("/profile")
def profile():
    try:
        data = str(request.body.read())[2:-1]
        print(data)
        data_dict = json.loads(data)
        return vids.set_profile(data_dict)
    except:
        abort(500)

@get("/profiles")
def get_profile():
    return vids.cache["profiles"]

@get("/profile/<_id>")
def get_profile(_id):
    return vids.get_profile_by_id(_id)

@get("/video/<_id>")
def video(_id):
    return vids.get_by_id(_id)

@post("/encode")
def add_encode():
    try:
        data = str(request.body.read())[2:-1]
        print(data)
        data_dict = json.loads(data)
        return vids.add_encode(data_dict)
    except:
        abort(500)

@get("/encodes")
def get_encodes():
    return vids.cache["encodes"]

@get("/encode/<_id>")
def get_encode(_id):
    return vids.get_encode_by_id(_id)

@get("/chunk/<filename>")
def get_chunk(filename):
    return static_file(filename, root=CHUNK_DIR)

@get("/final/<filename>")
def get_chunk(filename):
    filename = unquote(filename)
    return static_file(filename, root=ENCODE_FINAL_DIR)

@get("/jobs")
def get_jobs():
    return vids.get_all_jobs()

@get("/jobs/ready")
def get_ready_jobs():
    return vids.get_ready_jobs()

@get("/jobs/encode/<_id>")
def get_jobs_by_encode(_id):
    return vids.get_encode_jobs(_id)

@get("/jobs/encode/<_id>/ready")
def get_ready_jobs_by_encode(_id):
    return vids.get_encode_ready_jobs(_id)

@get("/jobs/claim/<_id>")
def claim_job(_id):
    return vids.claim_job(_id)

@post("/jobs/submit/<_id>")
def submit_job(_id):
    upload = request.files.get("upload").file
    vids.submit_job(upload, _id)
    return

run(host="10.0.0.5", port=8080, debug=True)
