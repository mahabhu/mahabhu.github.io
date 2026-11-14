#!/usr/bin/env python3
"""Fast pre-filter: mark names that have an active public profile as taken.

Fetches instagram.com/<name>/ logged out, as a link-preview bot, and looks for
the profile title "(@name) • Instagram photos and videos". Only a positive match
is written (as "taken") to results.csv; anything else is left for check.py, so a
free name can never be filtered out by mistake. Uses no login and no cookies.

  python urlcheck.py                 # all of names.txt not yet in results.csv
  python urlcheck.py --gap 3        # slower, if it keeps getting throttled
"""
import argparse
import csv
import html
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
TITLE_RE = re.compile(r'<meta property="og:title" content="([^"]*)"')
CANARY = "instagram"  # always exists; if it stops matching we're being throttled


def fetch_title(name, timeout=20):
    """Return (status, title). Reads only until og:title or </head> appears."""
    req = urllib.request.Request(f"https://www.instagram.com/{name}/", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            buf = b""
            while len(buf) < 2_000_000:
                chunk = r.read(65536)
                if not chunk:
                    break
                buf += chunk
                m = TITLE_RE.search(buf.decode("utf-8", "ignore"))
                if m:
                    return r.status, html.unescape(m.group(1))
                if b"</head>" in buf:
                    break
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, e.__class__.__name__


def has_profile(name, title):
    return f"(@{name})" in title


def load_done(path):
    done = set()
    if os.path.exists(path):
        with open(path) as f:
            done = {row["name"] for row in csv.DictReader(f)}
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--names", default="names.txt")
    ap.add_argument("--out", default="results.csv")
    ap.add_argument("--seen", default="urlcheck_seen.txt", help="names already URL-checked with no profile found")
    ap.add_argument("--gap", type=float, default=2.0, help="seconds between requests (default 2)")
    ap.add_argument("--batch", type=int, default=10, help="'no profile' answers held until a canary check confirms them")
    a = ap.parse_args()

    done = load_done(a.out)
    seen = set(open(a.seen).read().split()) if os.path.exists(a.seen) else set()
    names = [l.strip() for l in open(a.names) if l.strip()]
    todo = [n for n in names if n not in done and n not in seen]
    print(f"{len(todo)} names to URL-check ({len(names) - len(todo)} already known)", flush=True)

    stats = {"profile": 0, "none": 0, "throttled": 0}
    new_file = not os.path.exists(a.out)
    out = open(a.out, "a", newline="")
    w = csv.writer(out)
    if new_file:
        w.writerow(["name", "result", "message", "checked_at"])
    seen_f = open(a.seen, "a")

    def canary_ok():
        st, t = fetch_title(CANARY)
        return st == 200 and has_profile(CANARY, t)

    def wait_unthrottled(reason):
        stats["throttled"] += 1
        delay = 120
        while True:
            print(f"[{datetime.now():%H:%M:%S}] throttled ({reason}); waiting {delay}s", flush=True)
            time.sleep(delay)
            if canary_ok():
                return
            delay = min(delay * 2, 1800)

    if not canary_ok():
        wait_unthrottled("canary missing at start")

    # A throttled reply looks exactly like "no profile", so "none" answers are only
    # trusted once a canary check made *after* them still passes.
    queue, pending, n = list(todo), [], 0
    try:
        while queue or pending:
            time.sleep(random.uniform(a.gap * 0.6, a.gap * 1.4))
            if queue and len(pending) < a.batch:
                name = queue.pop(0)
                st, title = fetch_title(name)
                if st != 200:
                    queue[:0] = pending + [name]
                    n -= len(pending)
                    pending = []
                    wait_unthrottled(f"HTTP {st}")
                    continue
                n += 1
                if has_profile(name, title):
                    stats["profile"] += 1
                    w.writerow([name, "taken", "active profile (url)", datetime.now().isoformat(timespec="seconds")])
                    out.flush()
                else:
                    pending.append(name)
                if n % 100 == 0:
                    print(f"[{datetime.now():%H:%M:%S}] {n}/{len(todo)}  profile={stats['profile']} none={stats['none']}", flush=True)
                continue
            # pending batch full (or queue empty): confirm with the canary
            if canary_ok():
                stats["none"] += len(pending)
                seen_f.write("".join(x + "\n" for x in pending))
                seen_f.flush()
                pending = []
            else:
                queue[:0] = pending
                n -= len(pending)
                pending = []
                wait_unthrottled("canary missing")
    except KeyboardInterrupt:
        print("interrupted")
    finally:
        out.close()
        seen_f.close()
    print(f"done: profile={stats['profile']} none={stats['none']} throttled={stats['throttled']}x")


if __name__ == "__main__":
    main()
