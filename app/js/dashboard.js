var data = {timeout: 2000, videos: [], encodes: [], profiles: [], video: '', profile: '', upurl: '', name: '', cmd: '', desc: ''};
var vm = null;
url = location.protocol + "//" + location.hostname;
if (location.port != 80) {
    url += ":" + location.port;
}
url += "/";

function update_videos(e) {
    data.videos = JSON.parse(this.responseText);
}

function update_encodes(e) {
    data.encodes = JSON.parse(this.responseText);
}

function update_profiles(e) {
    data.profiles = JSON.parse(this.responseText);
}


function update() {
    xhrv = new XMLHttpRequest();
    xhre = new XMLHttpRequest();
    xhrp = new XMLHttpRequest();
    console.log(url)
    xhrv.open("GET", url + "videos");
    xhrv.addEventListener("load", update_videos);
    xhrv.send();
    xhre.open("GET", url + "encodes");
    xhre.addEventListener("load", update_encodes);
    xhre.send();
    xhrp.open("GET", url + "profiles");
    xhrp.addEventListener("load", update_profiles);
    xhrp.send();
    console.log(data);
    if (vm == null) {
        vm = new Vue({
            el: '#dashboard',
            data: data
            })
    }
    setTimeout(update, data.timeout);
}

function url_upload() {
    console.log("uploading " + data.upurl);
    xhr = new XMLHttpRequest();
    xhr.open("POST", url + "upload/url");
    req = {}
    req.url = data.upurl;
    xhr.send(JSON.stringify(req));
}

function add_encode() {
    console.log("Adding encode");
    xhr = new XMLHttpRequest();
    xhr.open("POST", url + "encode");
    req = {};
    req.vid = data.video;
    req.pid = data.profile;
    xhr.send(JSON.stringify(req));
}

function add_profile() {
    console.log("Adding profile");
    xhr = new XMLHttpRequest()
    xhr.open("POST", url + "profile")
    req = {};
    req.name = data.name;
    req.cmd = data.cmd;
    req.desc = data.desc;
    xhr.send(JSON.stringify(req));
}
