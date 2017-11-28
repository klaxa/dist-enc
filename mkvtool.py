#!/usr/bin/python3

from subprocess import Popen, PIPE
import re
import os
import os.path


MKVMERGE = "mkvmerge"
MKVINFO = "mkvinfo"

mkvinfo_out_fmt = re.compile(r"(.) frame, track (\d+), timestamp (\d+) \(([0-9:\.]+)\), .*")
mkvmerge_out_fmt = re.compile(r"Progress: (\d+\%).*")

def ts2secs(ts):
    split = ts.split(":")
    s = float(split[-1])
    s += float(split[-2] * 60)
    s += float(split[-3] * 3600)
    return s

class mkvtool:
    def get_i_frames(filename, report):
        report("reading I-Frames", "0%")
        duration = 0
        cmd = [MKVINFO, filename]
        mkvinfo = Popen(cmd, stdout=PIPE)
        segment_flag = False
        line = str(mkvinfo.stdout.readline())[2:-1].rstrip()
        while line != "":
            if segment_flag and "Duration" in line:
                pattern = re.compile(r".*\(([0-9:\.]*)\).*")
                try:
                    duration = ts2secs(pattern.match(line).group(1))
                except:
                    pass   
            if "Segment" in line:
                segment_flag = True
            line = str(mkvinfo.stdout.readline())[2:-1].rstrip()
        cmd = [MKVINFO, "-s", filename]
        frames = []
        mkvinfo = Popen(cmd, stdout=PIPE)
        line = str(mkvinfo.stdout.readline())[2:-1].rstrip()
        while line != "":
            #print(line)
            match = mkvinfo_out_fmt.match(line)
            try:
                frame = match.groups()
                frames.append(frame)
                if frame[0] == 'I' and frame[1] == '1' and duration > 0:
                    secs = ts2secs(frame[3])
                    percent = str(int(secs * 90 / duration)) + "%" 
                    report("reading I-Frames", percent)
            except:
                print(line)
            line = str(mkvinfo.stdout.readline())[2:-1].rstrip()
        mkvinfo.wait()
        print("filtering I-Frames")
        report("Read file, filtering...", "90%")
        i_frames = list(map(lambda x: x[3], filter(lambda x: x[0] == 'I' and x[1] == '1', frames)))
        print(i_frames)
        report("Read file, filtering...", "100%")
        return i_frames
    
    def split(orig, chunks, splits, report):
        report("splitting", "0%")
        chunk_dir = os.path.dirname(chunks)
        chunk_name = re.sub(".mkv", "", os.path.basename(chunks))
        cmd = [MKVMERGE, "--split", "timestamps:" + ",".join(splits), orig, "-o", chunks]
        print(cmd)
        mkvmerge = Popen(cmd, stdout=PIPE)
        line = str(mkvmerge.stdout.readline())[2:-1].rstrip()
        while line != "":
            match = mkvmerge_out_fmt.match(line)
            try:
                report("splitting", match.group(1))
            except:
                pass
            line = str(mkvmerge.stdout.readline())[2:-1].rstrip()
        mkvmerge.wait()
        report("splitting", "100%")
        return sorted([f for f in os.listdir(chunk_dir) if chunk_name in f])
    
    def merge(files, out, report):
        report("merging", "0%")
        #cmd = [MKVMERGE] + " + ".join(list(map(lambda x: "\"" + x + "\"", files))).split() + ["-o", out]
        cmd = [MKVMERGE] + " + ".join(files).split() + ["-o", out]
        print(cmd)
        mkvmerge = Popen(cmd, stdout=PIPE)
        line = str(mkvmerge.stdout.readline())[2:-1].rstrip()
        while line != "":
            match = mkvmerge_out_fmt.match(line)
            try:
                report("merging", match.group(1))
            except:
                pass
            line = str(mkvmerge.stdout.readline())[2:-1].rstrip()
        mkvmerge.wait()
        report("finished", "100%")
        return out
        
        
