#!/usr/bin/env python3
"""Generate candidate Instagram handles from simple rules.

Examples:
  python gen.py --len 4                         # all 4-letter a-z handles (456,976 - too many!)
  python gen.py --len 4 --letters mashro        # 4 chars using only these letters
  python gen.py --len 5 --contains mhb --pron   # 5 chars, contains "mhb", pronounceable-ish
  python gen.py --len 4-5 --letters mhbo --sep  # allow one '.' or '_' in the middle

Writes names.txt (one per line). Review it before running check.py.
"""
import argparse
import itertools
import random
import re
import sys

VOWELS = set("aeiouy")
# Instagram rules: a-z 0-9 . _ ; max 30; no leading/trailing '.', no '..'
VALID = re.compile(r"^(?!\.)(?!.*\.\.)(?!.*\.$)[a-z0-9._]{1,30}$")


def parse_len(s):
    if "-" in s:
        a, b = s.split("-")
        return range(int(a), int(b) + 1)
    return range(int(s), int(s) + 1)


def pronounceable(name):
    core = name.replace(".", "").replace("_", "")
    if not any(c in VOWELS for c in core):
        return False
    # no more than 2 consonants or 2 vowels in a row
    run, last = 0, None
    for c in core:
        if c.isdigit():
            return False
        kind = c in VOWELS
        run = run + 1 if kind == last else 1
        last = kind
        if run > 2:
            return False
    return True


def candidates(length, letters, sep):
    for combo in itertools.product(letters, repeat=length):
        yield "".join(combo)
    if sep:
        # one separator at an inner position; separator counts toward length
        for pos in range(1, length - 1):
            for combo in itertools.product(letters, repeat=length - 1):
                s = "".join(combo)
                for ch in "._":
                    yield s[:pos] + ch + s[pos:]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--len", default="5", help="length or range, e.g. 4 or 4-6 (default 5)")
    ap.add_argument("--letters", default="abcdefghijklmnopqrstuvwxyz", help="allowed characters")
    ap.add_argument("--digits", action="store_true", help="also allow 0-9")
    ap.add_argument("--sep", action="store_true", help="allow one '.' or '_' inside the name")
    ap.add_argument("--contains", default="", help="name must contain this substring")
    ap.add_argument("--starts", default="", help="name must start with this")
    ap.add_argument("--pron", action="store_true", help="keep only pronounceable-ish names")
    ap.add_argument("--max", type=int, default=150, help="max names to output (default 150)")
    ap.add_argument("--shuffle", action="store_true", help="random sample instead of alphabetical")
    ap.add_argument("--out", default="names.txt")
    a = ap.parse_args()

    letters = sorted(set(a.letters.lower() + ("0123456789" if a.digits else "")))
    out = set()
    for n in parse_len(a.len):
        for name in candidates(n, letters, a.sep):
            if a.contains and a.contains not in name:
                continue
            if a.starts and not name.startswith(a.starts):
                continue
            if not VALID.match(name):
                continue
            if a.pron and not pronounceable(name):
                continue
            out.add(name)

    names = sorted(out, key=lambda s: (len(s), s))
    total = len(names)
    if a.shuffle:
        random.shuffle(names)
    names = names[: a.max]
    with open(a.out, "w") as f:
        f.write("\n".join(names) + "\n")
    print(f"{total} names matched, wrote {len(names)} to {a.out}", file=sys.stderr)
    if total > a.max:
        print(f"(capped by --max {a.max}; tighten rules or use --shuffle)", file=sys.stderr)


if __name__ == "__main__":
    main()
