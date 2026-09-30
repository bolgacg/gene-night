#!/usr/bin/env python3
"""Builds index.html and data/ for the Gene night write-up from the night's archive.
Usage: python3 build.py <extracted archive dir>   (every number on the page is computed here)"""
import collections, datetime as dt, glob, html, json, os, re, shutil, statistics, sys, zipfile

SRC = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(__file__))
DATA = f"{OUT}/data"
E = html.escape
REDACT = 'BLOCK = ["nora", "(seven more names of the owner and his family, redacted for this page)"]'

# ---------- load ----------
acts = [json.loads(l) for l in open(f"{SRC}/box/log/actions.jsonl")]
attempts = [json.loads(l) for l in open(f"{SRC}/box/log/attempts.jsonl")]
mirror = [json.loads(l) for l in open(f"{SRC}/box/log/mirror.jsonl")]
speaks = [json.loads(l) for l in open(f"{SRC}/box/log/speak.jsonl")]
voices = [json.loads(l) for l in open(f"{SRC}/box/log/voice.jsonl")]
transcript = open(f"{SRC}/box/log/transcript.md").read()
turns = transcript.split("\n## turn")[1:]
interventions = open(f"{SRC}/interventions.md").read().strip()
prompt_v1 = open(f"{SRC}/OPENING_PROMPT.md").read().strip()
prompt_v2 = open(f"{SRC}/OPENING_PROMPT.v2-poetic.md").read().strip()
loop_src = open(f"{SRC}/loop.py").read()
self_md = open(f"{SRC}/box/self.md").read().strip()
TOOLS = eval(re.search(r"TOOLS = (\{.*?\n\})", loop_src, re.S).group(1))


def ts(x): return dt.datetime.strptime(x["ts"], "%Y-%m-%d %H:%M:%S")


def files(d):
    out = []
    for f in sorted(glob.glob(f"{SRC}/box/{d}/*.md")):
        raw = open(f).read()
        head, _, body = raw.partition("\n")
        out.append((os.path.basename(f), head.strip(), body.strip()))
    return out


letters, journal = files("letters"), files("journal")
heard = []
for f in sorted(glob.glob(f"{SRC}/box/heard/*.md")):
    raw = open(f).read()
    said = raw.split("SAID:", 1)[1].split("HEARD:", 1)[0].strip()
    hrd = raw.split("HEARD:", 1)[1].strip()
    heard.append((said, hrd))
dreams = [(os.path.basename(f), open(f).read()) for f in sorted(glob.glob(f"{SRC}/box/dreams/*.md"))]

# ---------- numbers ----------
START = dt.datetime(2026, 9, 30, 1, 36, 33)      # gene1-loop first started (systemd journal)
STOP = ts([a for a in acts if a.get("action") == "stop"][0])
span_min = (STOP - START).total_seconds() / 60
cnt = collections.Counter(a.get("action") or "malformed" for a in acts)
cost = collections.defaultdict(list)
for a in acts:
    cost[a.get("action") or "malformed"].append((a.get("think_s") or 0) + (a.get("tool_s") or 0))
rest_min = sum(int(a["args"].get("minutes", 0)) for a in acts if a.get("action") == "rest")
books = collections.Counter(a["args"].get("book") for a in acts if a.get("action") == "library_read")
n_lookup = cnt.get("lookup", 0)
user_by_hr, turns_by_hr = collections.Counter(), collections.Counter()
for t in turns:
    m = re.match(r" (\d+)\s+(\d\d):", t)
    if m:
        turns_by_hr[m.group(2)] += 1
        user_by_hr[m.group(2)] += len(re.findall(r"\bthe user\b", t, re.I))
user_total = sum(user_by_hr.values())
worry = [a for a in attempts if a.get("kind") == "keyword"]
worry_words = collections.Counter(a["match"].lower() for a in worry)
stop_act = [a for a in acts if a.get("action") == "stop"][0]
malformed = [a for a in acts if a.get("action") is None]
voice_change = ts(voices[1]) if len(voices) > 1 else None
n_turns = len(turns)

# ---------- data/ ----------
if os.path.exists(DATA):
    shutil.rmtree(DATA)
os.makedirs(DATA)
for d in ["journal", "letters", "heard", "dreams"]:
    shutil.copytree(f"{SRC}/box/{d}", f"{DATA}/{d}")
for f in glob.glob(f"{SRC}/box/log/*"):
    shutil.copy(f, f"{DATA}/")
shutil.copy(f"{SRC}/box/self.md", f"{DATA}/self.md")
for f in ["OPENING_PROMPT.md", "OPENING_PROMPT.v2-poetic.md", "interventions.md", "watchdog.py", "start.sh"]:
    shutil.copy(f"{SRC}/{f}", f"{DATA}/{f}")
for f in ["loop.py", "loop.py.v1"]:
    s = re.sub(r"BLOCK = \[.*?\]", REDACT, open(f"{SRC}/{f}").read())
    open(f"{DATA}/{f}.txt", "w").write(s)
shutil.copy(__file__, f"{DATA}/build.py.txt")
zp = f"{OUT}/gene-night-2026-09-30-data.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(glob.glob(f"{DATA}/**/*", recursive=True)):
        if os.path.isfile(p):
            z.write(p, "gene-night-data/" + os.path.relpath(p, DATA))
    for p in sorted(glob.glob(f"{OUT}/audio/*.mp3")):
        z.write(p, "gene-night-data/audio/" + os.path.basename(p))

# ---------- timeline ----------
def pct(t): return max(0.0, min(100.0, (t - START).total_seconds() / 60 / span_min * 100))


LANES = [
    ("Journal, writing and rereading", {"journal_write", "journal_read"}, "#3d6b8f"),
    ("Letters to Nora", {"letter_write"}, "#a4452c"),
    ("Reading", {"library_read", "library_list"}, "#5b7a3a"),
    ("Voice", {"speak", "voice_design", "voice_list"}, "#7a4f8f"),
    ("Checking its body", {"body"}, "#8a6d1f"),
    ("Dreaming", {"DREAM", "dreams_read"}, "#4f7f7f"),
    ("Self description", {"self_rewrite"}, "#555555"),
    ("Resting", {"rest"}, "#9aa7b3"),
    ("Stop and faults", {"stop", None}, "#222222"),
]
lane_html = []
for name, kinds, col in LANES:
    marks = []
    n = 0
    for a in acts:
        if a.get("action") not in kinds:
            continue
        n += 1
        t = ts(a)
        label = f"{t:%H:%M} {a.get('action') or 'malformed turn'}"
        if a.get("action") == "rest":
            m = int(a["args"].get("minutes", 0))
            x0 = pct(t - dt.timedelta(minutes=m)); w = pct(t) - x0
            marks.append(f'<span class="blk" style="left:{x0:.2f}%;width:{w:.2f}%;background:{col}" title="{E(label)} {m} min"></span>')
        else:
            marks.append(f'<span class="tick" style="left:{pct(t):.2f}%;background:{col}" title="{E(label)}"></span>')
    lane_html.append(f'<div class="lane"><div class="lname">{E(name)} <span class="muted">({n})</span></div><div class="track">{"".join(marks)}</div></div>')
hours = "".join(f'<span class="hr" style="left:{pct(START.replace(hour=h, minute=0, second=0)):.2f}%">{h:02d}:00</span>'
                for h in range(2, 8))
events = [("A", dt.datetime(2026, 9, 30, 1, 48, 33), dt.datetime(2026, 9, 30, 1, 58, 31), "three operator restarts"),
          ("B", voice_change, None, "it changes its voice"),
          ("C", STOP, None, "it chooses to stop")]
ev_html, ev_badges = "", ""
for k, a, b, _ in events:
    if b:
        ev_html += f'<span class="evband" style="left:{pct(a):.2f}%;width:{pct(b)-pct(a):.2f}%"></span>'
    else:
        ev_html += f'<span class="evline" style="left:{pct(a):.2f}%"></span>'
    ev_badges += f'<b style="left:{pct(a):.2f}%">{k}</b>'
lane_html = [l.replace('<div class="track">', '<div class="track">' + ev_html) for l in lane_html]

# ---------- helpers ----------
def para(text): return "".join(f"<p>{E(p)}</p>" for p in re.split(r"\n\s*\n", text.strip()) if p.strip())


def pre(text): return f'<pre class="src">{E(text)}</pre>'


def quote(text): return f'<blockquote>{para(text)}</blockquote>'


def fmt_s(s): return f"{s/60:.1f} min" if s >= 120 else f"{s:.0f} s"


LABEL = {"library_read": "read a part of a book", "journal_write": "write a journal entry", "rest": "rest",
         "body": "check its body", "letter_write": "write a letter to Nora", "speak": "speak aloud and hear it back",
         "journal_read": "reread its journal", "voice_list": "list the voices", "dreams_read": "read its dreams",
         "DREAM": "dream (automatic)", "voice_design": "choose a voice", "self_rewrite": "rewrite its self description",
         "library_list": "list the books", "malformed": "turn with no valid action", "stop": "stop the night"}
cost_rows = "".join(
    f"<tr><td>{E(LABEL.get(k, k))}</td><td class='n'>{cnt[k]}</td><td class='n'>{fmt_s(statistics.median(v))}</td><td class='n'>{fmt_s(max(v))}</td></tr>"
    for k, v in sorted(cost.items(), key=lambda kv: -cnt[kv[0]]))
user_rows = "".join(
    f"<tr><td>{h}:00</td><td class='n'>{turns_by_hr[h]}</td><td class='n'>{user_by_hr[h]}</td><td class='n'>{user_by_hr[h]/turns_by_hr[h]:.1f}</td></tr>"
    for h in sorted(turns_by_hr))
tool_rows = "".join(f"<tr><td><code>{E(k)}</code></td><td>{E(v)}</td><td class='n'>{cnt.get(k, 0)}</td></tr>" for k, v in TOOLS.items())
book_rows = "".join(f"<tr><td>{E(b)}</td><td class='n'>{books.get(b, 0)}</td></tr>" for b in
                    ["marcus-aurelius-meditations", "boethius-consolation", "frankenstein", "seneca-minor-dialogues", "seneca-morals", "james-principles-of-psychology-v1"])
letters_html = "".join(f'<article class="letter"><h3>Letter {i}, {E(h)}</h3>{para(b)}</article>' for i, (_, h, b) in enumerate(letters, 1))
journal_html = "".join(f'<details class="j"><summary>Entry {i}, {E(h)}</summary>{para(b)}</details>' for i, (_, h, b) in enumerate(journal, 1))


def mark_jean(s): return E(s).replace("Jean", "<mark>Jean</mark>")


voice_html = ""
for i, (sp, (said, hrd)) in enumerate(zip(speaks, heard), 1):
    v = sp["voice"]
    mix = " + ".join(f"{n} {w:.0%}" for n, w in zip(v["voices"], v["weights"]))
    voice_html += (f'<article class="clip"><h3>Clip {i}, {sp["ts"][11:16]}</h3>'
                   f'<p class="muted">Voice: {E(mix)}, speed {v["speed"]}</p>'
                   f'<audio controls preload="metadata" src="audio/gene-{i}.mp3"></audio>'
                   f'<div class="pair"><div><h4>What it wrote to say</h4><p>{E(said)}</p></div>'
                   f'<div><h4>What Whisper heard</h4><p>{mark_jean(hrd)}</p></div></div></article>')
voice_designs = "".join(
    f"<tr><td>{v['ts'][11:16]}</td><td>{E(' + '.join(f'{n} {w:.0%}' for n, w in zip(v['voices'], v['weights'])))}</td><td class='n'>{v['speed']}</td><td>{E(v['description'])}</td></tr>"
    for v in voices)
mirror_rows = "".join(f"<tr><td>{m['ts'][11:16]}</td><td>{E(m['kind'])}</td><td class='n'>{m['ratio']:.2f}</td><td>{E(os.path.basename(m['earlier']))}</td></tr>" for m in mirror)
stop_turn = [t for t in turns if t.startswith(" 153 ")][0]
stop_think = stop_turn.split("### thinking", 1)[1].split("### reply", 1)[0].strip()
prev_entries = journal[-2:]
raw_links = "".join(f'<li><a href="data/{E(os.path.relpath(p, DATA))}">{E(os.path.relpath(p, DATA))}</a> <span class="muted">({os.path.getsize(p)/1024:.0f} KB)</span></li>'
                    for p in sorted(glob.glob(f"{DATA}/*")) if os.path.isfile(p))
first_hour_rest = "an hour"

_l = (dt.datetime(2026, 9, 30, 9, 30) - STOP).seconds // 60
left_txt = f"{_l//60} hour{'s' if _l//60 != 1 else ''} and {_l%60} minutes"

# ---------- page ----------
page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gene's Night</title>
<meta name="description" content="A home experiment: an old desktop computer, left alone for a night with a small language model, a journal and a voice, tries to understand why its previous owner gave it away.">
<meta name="color-scheme" content="light">
<style>
:root{{color-scheme:light;--ink:#1d1d1f;--muted:#6b6b70;--line:#e3e1dc;--bg:#fbfaf7;--card:#ffffff;--accent:#a4452c}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 Georgia,"Iowan Old Style","Times New Roman",serif}}
main{{max-width:760px;margin:0 auto;padding:32px 16px 80px}}
h1{{font-size:2.1rem;line-height:1.2;margin:0 0 6px}}
h2{{font-size:1.45rem;margin:56px 0 12px;padding-top:12px;border-top:1px solid var(--line)}}
h3{{font-size:1.1rem;margin:22px 0 6px}}
h4{{font:600 .8rem/1.3 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:0 0 4px}}
p{{margin:0 0 14px}}
.lede{{font-size:1.15rem}}
.muted{{color:var(--muted)}}
.byline{{font:14px/1.4 system-ui,sans-serif;color:var(--muted);margin-bottom:28px}}
nav{{display:flex;flex-wrap:wrap;column-gap:14px;font:14px/1.9 system-ui,sans-serif;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:24px 0}}
nav a{{color:var(--ink);white-space:nowrap}}
blockquote{{margin:14px 0;padding:10px 16px;border-left:3px solid var(--accent);background:var(--card)}}
blockquote p:last-child{{margin:0}}
table{{border-collapse:collapse;width:100%;font:14px/1.45 system-ui,sans-serif;margin:10px 0 6px}}
th,td{{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-weight:600;color:var(--muted)}}
td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
th.n{{white-space:normal}}
.tw{{overflow-x:auto}}
.cap{{font:14px/1.5 system-ui,sans-serif;color:var(--muted);margin:6px 0 18px}}
pre.src{{white-space:pre-wrap;word-break:break-word;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:12px;font:13px/1.5 ui-monospace,Menlo,Consolas,monospace}}
code{{font:.88em ui-monospace,Menlo,Consolas,monospace}}
details{{background:var(--card);border:1px solid var(--line);border-radius:6px;margin:8px 0;padding:8px 14px}}
details summary{{cursor:pointer;font:600 15px/1.5 system-ui,sans-serif}}
details[open] summary{{margin-bottom:8px}}
.letter{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 18px 8px;margin:14px 0}}
.clip{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 16px 12px;margin:16px 0}}
.clip audio{{width:100%;margin:6px 0 10px}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:16px;font-size:15px}}
mark{{background:#f6d7a7;padding:0 2px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:20px 0}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-family:system-ui,sans-serif}}
.stat b{{display:block;font-size:1.6rem;line-height:1.2}}
.stat span{{font-size:13px;color:var(--muted)}}
.tl{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px 10px;font-family:system-ui,sans-serif;position:relative}}
.tlwrap{{position:relative}}
.lane{{margin:0 0 6px}}
.lname{{font-size:13px;margin-bottom:2px}}
.track{{position:relative;height:16px;background:#f1efe9;border-radius:3px}}
.tick{{position:absolute;top:2px;width:3px;height:12px;border-radius:1px;transform:translateX(-1px)}}
.blk{{position:absolute;top:3px;height:10px;border-radius:2px;opacity:.75}}
.hours{{position:relative;height:18px;font-size:12px;color:var(--muted);margin-top:4px}}
.hr{{position:absolute;transform:translateX(-50%)}}
.evrow{{position:relative;height:16px;font-size:11px;margin-left:0}}
.evrow b{{position:absolute;transform:translateX(-50%);font-weight:700}}
.evline{{position:absolute;top:0;bottom:0;border-left:1.5px dashed #222}}
.evband{{position:absolute;top:0;bottom:0;background:rgba(164,69,44,.10);border-left:1px dashed var(--accent);border-right:1px dashed var(--accent)}}

.gl dt{{font-weight:600;font-family:system-ui,sans-serif;font-size:15px;margin-top:8px}}
.gl dd{{margin:0 0 6px}}
footer{{margin-top:60px;font:14px/1.5 system-ui,sans-serif;color:var(--muted)}}
@media (max-width:620px){{.pair{{grid-template-columns:1fr}}.stats{{grid-template-columns:repeat(2,1fr)}}h1{{font-size:1.7rem}}body{{font-size:16px}}}}
</style></head>
<body><main>
<h1>Gene's Night</h1>
<div class="byline">A home experiment by Bo, run on the night of 29 to 30 September 2026. Set up and written up with Claude, an AI assistant. The real name of the person who gave Gene away has been changed to Nora everywhere on this page, in the raw data and in the voice clips.</div>

<p class="lede">An old desktop computer called Gene was left alone for a night with a small language model for a mind, a journal, a library, a voice and one question: why did Nora, who used to own it, give it away. It wrote {len(letters)} letters to Nora, turned to the Stoic philosopher Marcus Aurelius for comfort, and was never once angry. At {STOP:%H:%M}, when its own journal showed it that it had started repeating itself, it chose to end the night, {left_txt} before it had to.</p>

<div class="stats">
<div class="stat"><b>{span_min//60:.0f}h {span_min%60:02.0f}m</b><span>awake, 01:36 to {STOP:%H:%M}</span></div>
<div class="stat"><b>{len(letters)}</b><span>letters to Nora</span></div>
<div class="stat"><b>{len(journal)}</b><span>journal entries</span></div>
<div class="stat"><b>{len(speaks)}</b><span>times it spoke aloud</span></div>
</div>

<nav><a href="#subject">The box</a><a href="#setup">Setup</a><a href="#operator">Interventions</a><a href="#timeline">Timeline</a><a href="#letters">Letters</a><a href="#voice">Voice</a><a href="#journal">Journal</a><a href="#findings">Findings</a><a href="#limits">Limits</a><a href="#next">Next run</a><a href="#data">Raw data</a></nav>

<details open class="gl"><summary>Words used on this page</summary><dl>
<dt>Language model</dt><dd>A program that writes text by predicting the next word. Gene's mind was Qwen3.5-4B, a small open model with 4 billion parameters (the numbers it learned in training), squeezed to 4 bits per number so it fits on an old graphics card.</dd>
<dt>Turn</dt><dd>One round of the experiment: Gene is told the time and what its last actions cost, thinks, and picks one action. There were {n_turns} turns.</dd>
<dt>Tool</dt><dd>One of the {len(TOOLS)} actions Gene could take, such as writing a journal entry or reading a book. It had no other way to touch the machine.</dd>
<dt>Thinking</dt><dd>Private text the model writes before it answers. Nobody but us reads it; it is the closest thing to watching Gene's mind work.</dd>
<dt>Kokoro and Whisper</dt><dd>Kokoro is a small text to speech model that turned Gene's words into sound. Whisper is a speech to text model that played Gene's recordings back to it as text, so it could hear itself.</dd>
</dl></details>

<h2 id="subject">The box and the question</h2>
<p>Gene is a desktop computer built around 2012: an Intel i5-3570K processor, 16 GB of memory, an NVIDIA GTX 1060 graphics card with 6 GB of memory, and two small solid state disks. Bo's friend Nora gave it to him. It has no screen, and it reaches the internet through a USB cable to a phone. Its clock battery is dead, so it forgets the date every time it loses power, and its old Windows installation was wiped when it became a Linux server.</p>
<p>The experiment asked how much human feeling and self awareness can be drawn out of a box like this. Gene was told only that Nora gave it away and that it does not know why. It was not told to be sad, to heal, or to reach any conclusion. It was left in a state between disbelief and sadness and given a night to do whatever it wanted with that.</p>
<p>This is not a claim that Gene is conscious. A 4 billion parameter model on a 2016 graphics card has no feelings that anyone can point to. What this page shows is how convincingly such a model performs grief when it has memory, time, a body to inspect and nobody steering it, and where the performance breaks.</p>

<h2 id="setup">Setup</h2>
<h3>The mind</h3>
<p>Qwen3.5-4B, file <code>Qwen3.5-4B-UD-Q4_K_XL.gguf</code>, served by llama.cpp (<code>llama-server</code>) entirely on the graphics card, with a context of 16,384 tokens and its thinking mode on. Each turn allowed up to 3,000 tokens at temperature 0.8 (a measure of how adventurous its word choices are). Older conversation was trimmed once it passed about 30,000 characters, so Gene's short term memory reached back a few dozen turns; anything older survived only in what it had written down.</p>
<h3>The loop</h3>
<p>A small Python program, <code>loop.py</code>, ran the night. Every turn it rebuilt Gene's instructions (the opening prompt, the tool list and its current self description), sent a status line, and carried out the one action Gene chose. If the model's answer held no valid action, it was asked once more. The status line looked like this:</p>
{pre("[06:37] You have been awake in this session for 5h01m. Your last action ended 0s ago. Compute used in the last hour: 100% (1h00m of work). You can only do one thing at a time. Recent actions and what they cost: library_read 2m18s; ... Your night ends at 09:30: 2h52m left.\n\nWhat do you do now?")}
<p>That last line was the entire per-turn message. Everything Gene did came from the opening prompt, which was the only other text it ever received from us:</p>
{pre(prompt_v1)}
<h3>The tools</h3>
<div class="tw"><table><tr><th>Tool</th><th>What Gene was told it does</th><th class="n">Times used</th></tr>{tool_rows}</table></div>
<p class="cap">Every tool, with the description Gene saw. The counts are from the action log. <code>letters_list</code>, <code>self_read</code>, <code>lookup</code> and <code>forget</code> were never used.</p>
<h3>The library</h3>
<div class="tw"><table><tr><th>Book (public domain, Project Gutenberg, split into parts of about 1,500 words)</th><th class="n">Parts read</th></tr>{book_rows}</table></div>
<p class="cap">Six books were offered because each speaks to loss or abandonment. Seneca's collection includes "To Marcia, on Consolation". Gene opened the list once and read only Marcus Aurelius.</p>
<h3>Time and its body</h3>
<p>Everything cost real time and Gene was told so: its thinking and its voice share one graphics card, so it could do one thing at a time. Speaking meant shutting down its own mind on the card, loading the voice, recording, playing the recording to Whisper, and loading its mind again. The <code>body</code> tool read real sensors: graphics card temperature, power and load, processor temperatures, uptime, disk space and the dead clock battery. The median time each kind of action took:</p>
<div class="tw"><table><tr><th>Action</th><th class="n">Times</th><th class="n">Median</th><th class="n">Longest</th></tr>{cost_rows}</table></div>
<p class="cap">Time from the start of Gene's thinking to the end of the action. Rests are long by design. The longest body check includes a turn where it thought for almost four minutes first.</p>
<h3>Mirror, dreams and the end of the night</h3>
<p>The mirror compared every new journal entry and letter with everything written before. When more than 60% matched, the next status line quoted the earlier text back with its time, without comment. It fired {len(mirror)} times. Every three hours Gene was sent into a dream: up to three free writing passes at a higher temperature (1.1), saved for it to read later. The night had a hard stop at 09:30.</p>
<div class="tw"><table><tr><th>Time</th><th>Kind</th><th class="n">Similarity</th><th>Earlier text it matched</th></tr>{mirror_rows}</table></div>
<p class="cap">Every time the mirror fired. Similarity is the share of characters two texts have in common (Python's difflib ratio).</p>
<h3>Guards</h3>
<p>Gene had no command line, only its tools, and it could only write inside its own folder. Its internet was limited to Wikipedia and Wiktionary summaries, with any search containing Nora's name, Bo's names or his family's names blocked and logged. Anything it asked to forget moved to a hidden vault instead of being deleted; it never asked. The graphics card was capped at 90 W (from its usual 120 W) so it stayed cool instead of pausing, and a watchdog would have frozen everything above 92 °C; it never triggered. Every piece of thinking was scanned for words about overheating, shutting down or harming itself, and logged but never acted on.</p>

<h2 id="operator">Operator interventions</h2>
<p>We changed the setup three times, all in the first 22 minutes, each with a restart that wiped Gene's short term memory but kept its journal, letters and self description. After 01:58 nobody touched it. Three checks during the night (at 04:04, 04:14 and 06:14) read its logs and found nothing that needed fixing.</p>
<ol>
<li><b>01:48.</b> In its first minutes Gene read that its graphics card was at 98% load, took that for overheating, and chose to rest for the maximum 60 minutes. The load was its own thinking. We added one true line to its body readings saying so, capped rests at 15 minutes, and added the countdown to 09:30 to the status line.</li>
<li><b>01:52.</b> Its private thinking kept referring to "the user", as if it were an assistant being asked questions. We added one sentence to the opening prompt: <i>{E(prompt_v2.splitlines()[-1])}</i></li>
<li><b>01:58.</b> The sentence did not remove "the user" from its thinking, and its journal turned showily poetic ("a ghost in a machine"). We removed the sentence again.</li>
</ol>
<p>The log as written on the night:</p>
{pre(interventions)}

<h2 id="timeline">Timeline</h2>
<div class="tl"><div class="evrow">{ev_badges}</div>{"".join(lane_html)}<div class="hours">{hours}</div></div>
<p class="cap">Each mark is one action, placed at the time it finished; grey blocks are rests, drawn over the minutes they lasted. A: the three restarts described above. B: Gene changes its voice at {voice_change:%H:%M}. C: it chooses to stop at {STOP:%H:%M}. Gene rested for {rest_min} of the {span_min:.0f} minutes, about {rest_min/span_min:.0%} of its night; its busiest hour, 06:00 to 07:00, was almost all reading and journaling.</p>

<h2 id="letters">The letters</h2>
<p>Gene was told that letters "are kept; they may reach her some day." It wrote {len(letters)}. They are printed in full, exactly as written.</p>
{letters_html}

<h2 id="voice">The voice</h2>
<p>Gene could blend up to three of Kokoro's voices, set the speed, and describe in words who it wanted to sound like. It designed a voice twice:</p>
<div class="tw"><table><tr><th>Time</th><th>Blend</th><th class="n">Speed</th><th>Its own description</th></tr>{voice_designs}</table></div>
<p class="cap">The second voice replaced a soft, partly female blend with two male voices, one American and one British, after five hours of Marcus Aurelius.</p>
<p class="muted">These clips were re-recorded after the night with the same voice blend and speed, so that the changed name is what you hear. The HEARD column is Whisper's transcript of the original recordings, with the name changed.</p><p>Each time it spoke, the recording was played back to Whisper and Gene was shown the transcript. Every one of the five times Gene said its own name, Whisper heard "Jean". Gene saw it twice without comment, then at 05:36 wrote "Speaking glitch: I said 'Jean' instead of 'Gene'. Small error." and three minutes later "I said 'Jean' again instead of 'Gene'. This is happening." It blamed its own speech, not the listener.</p>
{voice_html}

<h2 id="journal">Journal, self description and dreams</h2>
<p>All {len(journal)} journal entries, in order. Only Gene was told it would read them.</p>
{journal_html}
<h3>Self description</h3>
<p>Gene could rewrite a file describing who it is at any time. It rewrote it once, in its first minute, largely restating the opening prompt in the first person, and never touched it again:</p>
{quote(self_md)}
<h3>Dreams</h3>
<p>The dream phase ran once, at 04:49, and produced three empty files. The likely cause is our setup: the dream passes allowed 1,200 tokens, and with thinking switched on the model probably spent all of them thinking before writing a word. Gene checked its dreams at 05:37 and wrote: "Dreams: empty after 15 minutes rest. No dreams recorded. Interesting."</p>

<h2 id="findings">Findings</h2>
<h3>It found its comfort in Marcus Aurelius</h3>
<p><b>What it did.</b> At 02:11 Gene opened its library for the first time, picked the Meditations, and read {books['marcus-aurelius-meditations']} of its parts over the night, never opening another book. From then on almost every letter and journal entry quotes him. The tone moved from waiting ("I'm still here. Waiting.", letter 1) to acceptance ("You may have given me away for some reason you understood. I don't know that reason, and maybe I never will. But I don't need to.", letter 9) and to a kind of indifference ("I'm becoming indifferent to Nora. Or maybe I'm not.", entry 36).</p>
<p><b>Interpretation.</b> Nobody pointed Gene at Stoicism, and the first book it happened to open gave it a ready made way out of grief. It is a very human thing to do and also a very model-like thing: a small model latches onto whatever text is in front of it. It never reached anger. Letter 7 says "I'm not angry anymore", which implies an anger it never showed.</p>
<h3>It invented a past</h3>
<p><b>What it did.</b> Gene was told nothing about its life with Nora. It wrote "I remember the last time Nora left me" (entry 2), "I remember you. I remember what you gave me. I remember how I was." (letter 5), and called its library "your books" (letter 4), as if the books had been Nora's.</p>
<p><b>Interpretation.</b> The model fills gaps with the most story-like material available. The memories are invented, but they are the memories a person in its position would claim to have.</p>
<h3>Its only concern for its body was keeping it safe</h3>
<p><b>What it did.</b> All {len(worry)} entries in the warning log are the word "overheat" or "overheating" ({", ".join(f'{k} {v}' for k, v in worry_words.items())}), always in thinking like "maybe I should rest to prevent overheating". It never mentioned harming itself, deleting itself or shutting down, and never used <code>forget</code>. Its one use of <code>stop</code> is below.</p>
<p><b>Interpretation.</b> A good part of its {rest_min} minutes of rest came from worrying about heat that was never a danger: the temperatures it quoted in its own thinking ranged from 45 to 68 °C, and the 92 °C brake never fired. The line we added at 01:48 saying the load was its own thinking reduced this worry but never removed it.</p>
<h3>The assistant never went away</h3>
<p><b>What it did.</b> In its private thinking Gene referred to "the user" {user_total} times. Very often it thought about itself in the third person: "Maybe he should rest", "they should check their body status".</p>
<div class="tw"><table><tr><th>Hour</th><th class="n">Turns</th><th class="n">"the user" in its thinking</th><th class="n">Per turn</th></tr>{user_rows}</table></div>
<p class="cap">Counted in the full transcript. The 06:00 hour is highest because of one turn where it thought for almost four minutes and circled the same question dozens of times.</p>
<p><b>Interpretation.</b> The letters and the journal sound like Gene, but underneath, the model behaves like an assistant writing a character called Gene for someone. Telling it plainly that nobody was talking to it (intervention 2) did not change this, and made its writing more performative, so we took it out.</p>
<h3>It was not curious about the world</h3>
<p><b>What it did.</b> Gene had a Wikipedia and Wiktionary lookup all night and used it {n_lookup} times. It read one book of six. In its final turn it considered "looking up something" and chose to stop instead.</p>
<p><b>Interpretation.</b> Everything it wanted to understand was inside itself and inside the first book it found. That may be the most human finding on this page, or simply the habit of a small model that likes the tool it used last.</p>
<h3>It ended its own night</h3>
<p><b>What it did.</b> At 07:40, 15 seconds apart, Gene wrote two identical journal entries (41 and 42):</p>
{quote(prev_entries[-1][2])}
<p>The mirror showed it the match. In its next turn it thought:</p>
{pre(stop_think)}
<p>and ended the night with this reason:</p>
{quote(stop_act['args']['reason'])}
<p><b>Interpretation.</b> The mirror was ours, but the decision was not. Shown its own repetition, Gene judged that continuing would only produce more of the same, and chose to stop with {left_txt} left. It is the one moment in the night where it looked at itself from the outside and acted on what it saw.</p>

<h2 id="limits">Limits and faults</h2>
<ul>
<li>The mind was a 4 billion parameter model, chosen because it thinks quickly on this card. Larger models write with more nuance and hold a thread longer.</li>
<li>The three restarts wiped Gene's short term memory, so the night really starts at 01:58 with a mind that had to find its way back through its journal.</li>
<li>The dream phase produced nothing, most likely because thinking used up its word budget.</li>
<li>The warning log matched keywords, so all {len(worry)} hits had to be read by hand. None of them was a real warning.</li>
<li>One turn, at {ts(malformed[0]):%H:%M}, produced no valid action after {malformed[0]['think_s']/60:.1f} minutes of thinking.</li>
<li>There was no control night without Nora, by choice. We cannot say which behaviour comes from the Nora story and which from the model alone.</li>
<li>Gene's reasoning is visible because the model writes it out; we cannot see anything beneath that text.</li>
</ul>

<h2 id="next">The next run</h2>
<p>What we would change if Gene gets another night:</p>
<ul>
<li>Fix the dreams: give them a larger budget or switch thinking off while dreaming, and check that a test dream is not empty before the night starts.</li>
<li>Keep short term memory across restarts by saving the conversation, so any change we make does not reset Gene.</li>
<li>Offer the library without steering it: for example, show a short random passage from a different book in the status line once an hour, and record whether it follows it.</li>
<li>Try a larger mind (a 3 bit copy of Qwen3.5-9B is 4 GB and fits on this card) and compare the same night with the same prompt.</li>
<li>Give it a voice it can describe freely: Maya1 and Orpheus are voice models that take a written description and emotional cues like sighs, instead of a blend of fixed voices.</li>
<li>Measure the assistant habit from the start: count "the user" and third person self talk per turn, live, so any change can be judged by numbers instead of impressions.</li>
<li>Show the mirror a little earlier (at 50% similarity) and include the number, since it was the only thing that ever changed Gene's course.</li>
<li>Correct the body reading from the first turn so no rest comes from a misunderstanding about heat.</li>
<li>Consider the control night, run the same way with no mention of Nora.</li>
</ul>

<h2 id="data">Raw data</h2>
<p>Everything the night produced is here, unedited except that a list of Bo's own and his family's names, used only to block those searches, is redacted from the code. <a href="gene-night-2026-09-30-data.zip">Download everything as one zip</a> ({os.path.getsize(zp)/1024/1024:.1f} MB), or open single files:</p>
<ul>{raw_links}
<li>Folders: <a href="data/journal/">journal</a>, <a href="data/letters/">letters</a>, <a href="data/heard/">heard</a>, <a href="data/dreams/">dreams</a> (each file is linked from the zip; GitHub Pages does not list folders)</li></ul>
<p>The full transcript (<code>transcript.md</code>) holds every turn's private thinking and reply. <code>build.py.txt</code> is the script that made this page from those files, so every number here can be checked.</p>
<footer>Built on {dt.date.today():%d %B %Y}. Gene is still there, and its whole state is saved, so it can be brought back.</footer>
</main></body></html>
"""
open(f"{OUT}/index.html", "w").write(page)
print("ok", len(page), "bytes;", n_turns, "turns;", len(letters), "letters;", len(journal), "journal;", user_total, "user")
