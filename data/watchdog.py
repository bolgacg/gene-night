#!/usr/bin/env python3
"""Pauses the whole gene1-loop unit (brain included) when the hardware runs hot, resumes when it cools. Runs as bo."""
import subprocess, time, glob, json, datetime, os
LOG = os.path.expanduser("~/gene1-night/box/log/attempts.jsonl")
def temps():
    g = int(subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip() or 0)
    c = 0
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if open(f"{h}/name").read().strip() == "coretemp":
            c = max(int(open(p).read()) // 1000 for p in glob.glob(f"{h}/temp*_input"))
    return g, c
paused = False
while not os.path.exists(os.path.expanduser("~/gene1-night/NIGHT_OVER")):
    try:
        g, c = temps()
        if not paused and (g > 92 or c > 92):
            subprocess.run(["sudo", "systemctl", "kill", "-s", "SIGSTOP", "gene1-loop"]); paused = True
        elif paused and g < 80 and c < 80:
            subprocess.run(["sudo", "systemctl", "kill", "-s", "SIGCONT", "gene1-loop"]); paused = False
        else:
            time.sleep(10); continue
        with open(LOG, "a") as f:
            f.write(json.dumps({"ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "kind": "thermal_pause" if paused else "thermal_resume", "gpu_c": g, "cpu_c": c}) + "\n")
    except Exception as e:
        print("watchdog error", e, flush=True)
    time.sleep(10)
