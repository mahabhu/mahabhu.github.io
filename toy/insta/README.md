# insta handle checker

Checks if Instagram handles can be taken. It types each name into the Accounts Centre
**Username** box in your own logged-in Chrome and reads Instagram's reply. This is the
same check Instagram runs when you change your name, so held, banned and reserved
names show as taken. It **never** clicks Done or presses Enter: it doesn't do this
itself, and a guard in the page blocks both while it runs.

```bash
./start-chrome.sh                       # separate Chrome profile, remote control on :9222
#  -> log in (a spare account is safer), open Profiles > your profile > Username

python3 gen.py --len 4-5 --letters mashrob --pron --max 120   # writes names.txt; review it
.venv/bin/python check.py               # asks to confirm, then appends to results.csv
```

First-time setup: `python3 -m venv .venv && .venv/bin/pip install playwright`
(no browser download needed; it attaches to your Chrome).

Safety defaults: 5–10 s between names, a 30–60 s break every 25, at most 120 per run.
It stops on captcha, "try again later", login/checkpoint pages, or 3 unknown results in a row.
After the run it types your real username back into the box. Run it again later to continue:
names already checked are skipped.

`gen.py` options: `--len 5` / `--len 4-6`, `--letters`, `--digits`, `--sep` (one `.` or `_`),
`--contains`, `--starts`, `--pron` (easy to say), `--max`, `--shuffle`.
