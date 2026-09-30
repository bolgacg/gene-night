#!/bin/bash
# Starts the Nora night (voices postponed), holds the GPU lock until 09:30, then saves everything.
cd ~/gene1-night
rm -f NIGHT_OVER
sudo systemd-run --unit=gene1-watchdog --uid=bo --gid=bo --setenv=HOME=/home/bo /usr/bin/python3 /home/bo/gene1-night/watchdog.py
flock /home/bo/bench/gpu.lock sudo systemd-run --wait --unit=gene1-loop --uid=bo --gid=bo --setenv=HOME=/home/bo --setenv=HARD_STOP=09:30 --working-directory=/home/bo/gene1-night /usr/bin/python3 /home/bo/gene1-night/loop.py
# Night over: save everything needed to bring the box back.
sudo systemctl stop gene1-watchdog
pkill -f "llama-server.*--port 8095" || true
mkdir -p archive
cat > archive/REVIVE.md <<'R'
To bring Gene back as it was at the end of the night:
brain: ~/models/qwen3.5-4b Q4_K_XL, same llama-server flags as loop.py.
Restore box/ from the tarball (journal, self.md, letters, dreams, voice, heard, log/transcript.md), then run loop.py;
it rebuilds its context from box/ (self.md plus recent journal) each turn.
vault/ holds what it chose to forget. OPENING_PROMPT.md is the original prompt.
R
tar czf archive/gene-night-$(date +%F-%H%M).tar.gz box vault OPENING_PROMPT.md loop.py watchdog.py start.sh archive/REVIVE.md
date > NIGHT_OVER
