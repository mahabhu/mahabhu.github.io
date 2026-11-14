#!/usr/bin/env python3
"""Check Instagram handle availability through your own logged-in Chrome tab.

It types each name into the Accounts Centre "Username" box (the same box you
use by hand) and reads Instagram's reply. It NEVER clicks Done or presses Enter.

Setup (once):
  ./start-chrome.sh              # Chrome with remote control on port 9222, separate profile
  -> log in to Instagram in that window (a spare account is safer)
  -> open Accounts Centre > Profiles > your profile > Username

Run:
  python gen.py --len 5 --contains mhb     # makes names.txt
  .venv/bin/python check.py                # reads names.txt, appends to results.csv
"""
import argparse
import csv
import os
import random
import re
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

CDP = "http://localhost:9222"
AC_URL = "https://accountscenter.instagram.com/?entry_point=app_settings"
VALID = re.compile(r"^(?!\.)(?!.*\.\.)(?!.*\.$)[a-z0-9._]{1,30}$")

TAKEN_RE = re.compile(r"(is not available|isn.t available|not available|already taken|is taken)", re.I)
INVALID_RE = re.compile(r"(can only use|can.t (contain|start|end)|only contain|not allowed|too long|must contain)", re.I)
STOP_RE = re.compile(
    r"(try again later|wait a few minutes|too many|something went wrong|unusual activity|"
    r"confirm it.s you|captcha|security check|we restrict certain activity)", re.I)

# Blocks Enter, form submit and any click on a "Done"/"Save" button while the script runs.
GUARD_JS = r"""
() => {
  if (window.__igGuard) return;
  const isSubmitBtn = (el) => {
    const b = el && el.closest && el.closest('button,[role=button]');
    return b && /^(done|save|submit|confirm)$/i.test((b.innerText || b.getAttribute('aria-label') || '').trim());
  };
  const onKey = (e) => { if (e.key === 'Enter' || e.keyCode === 13) { e.preventDefault(); e.stopImmediatePropagation(); } };
  const onClick = (e) => { if (isSubmitBtn(e.target)) { e.preventDefault(); e.stopImmediatePropagation(); console.warn('igGuard blocked click'); } };
  const onSubmit = (e) => { e.preventDefault(); e.stopImmediatePropagation(); };
  for (const t of ['keydown', 'keypress', 'keyup']) document.addEventListener(t, onKey, true);
  for (const t of ['click', 'mousedown', 'mouseup', 'pointerdown', 'pointerup']) document.addEventListener(t, onClick, true);
  document.addEventListener('submit', onSubmit, true);
  window.__igGuard = () => {
    for (const t of ['keydown', 'keypress', 'keyup']) document.removeEventListener(t, onKey, true);
    for (const t of ['click', 'mousedown', 'mouseup', 'pointerdown', 'pointerup']) document.removeEventListener(t, onClick, true);
    document.removeEventListener('submit', onSubmit, true);
    delete window.__igGuard;
  };
}
"""
UNGUARD_JS = "() => { if (window.__igGuard) window.__igGuard(); }"


class Stop(Exception):
    pass


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def find_page(browser):
    for ctx in browser.contexts:
        for p in ctx.pages:
            if "accountscenter.instagram.com" in p.url:
                return p
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    p = ctx.new_page()
    p.goto(AC_URL)
    return p


def username_box(page):
    dialog = page.get_by_role("dialog").filter(has_text=re.compile("Username"))
    scope = dialog.last if dialog.count() else page
    box = scope.get_by_role("textbox", name=re.compile("^Username$", re.I))
    if box.count() == 0:
        box = scope.get_by_label(re.compile("^Username$", re.I))
    return scope, box.first


def done_enabled(scope):
    btn = scope.get_by_role("button", name=re.compile(r"^Done$", re.I))
    if btn.count() == 0:
        return None
    btn = btn.last
    if (btn.get_attribute("aria-disabled") or "").lower() == "true":
        return False
    if btn.get_attribute("disabled") is not None:
        return False
    return btn.is_enabled()


def check_page_ok(page):
    url = page.url
    if any(k in url for k in ("/login", "/challenge", "/checkpoint", "/suspended")):
        raise Stop(f"page moved to {url}")
    if "accountscenter.instagram.com" not in url:
        raise Stop(f"left Accounts Centre: {url}")


def read_state(page, scope):
    """Return (state, message). state in: taken, invalid, available, pending."""
    text = scope.inner_text(timeout=3000)
    m = STOP_RE.search(text) or STOP_RE.search(page.inner_text("body", timeout=3000))
    if m:
        raise Stop(f"Instagram said: {m.group(0)!r}")
    # The dialog's own description mentions "username" but not these phrases.
    m = TAKEN_RE.search(text)
    if m:
        return "taken", m.group(0)
    m = INVALID_RE.search(text)
    if m:
        line = next((l for l in text.splitlines() if INVALID_RE.search(l)), m.group(0))
        return "invalid", line.strip()
    if done_enabled(scope):
        return "available", ""
    return "pending", ""


def type_name(box, name):
    box.click()
    box.press("Control+a")
    box.press("Backspace")
    time.sleep(random.uniform(0.3, 0.7))
    box.press_sequentially(name, delay=random.randint(70, 160))


def check_one(page, name, timeout):
    assert VALID.match(name), name  # only a-z0-9._ ever gets typed: no Enter possible
    check_page_ok(page)
    page.evaluate(GUARD_JS)
    scope, box = username_box(page)
    if box.count() == 0 or not box.is_visible():
        raise Stop("Username box not found - is the Username dialog still open?")
    type_name(box, name)
    if box.input_value() != name:
        return "unknown", f"box shows {box.input_value()!r}"

    time.sleep(1.2)  # let Instagram's check start, so we don't read the previous name's state
    deadline = time.time() + timeout
    last, same = None, 0
    while time.time() < deadline:
        check_page_ok(page)
        if box.input_value() != name:
            return "unknown", "box changed while checking"
        state, msg = read_state(page, scope)
        if state != "pending":
            same = same + 1 if state == last else 1
            last = state
            if same >= 3:  # stable for ~0.9s
                return state, msg
        else:
            last, same = None, 0
        time.sleep(0.3)
    return "unknown", "no answer before timeout"


def load_done(path):
    done = {}
    if os.path.exists(path):
        with open(path) as f:
            for row in csv.DictReader(f):
                done[row["name"]] = row["result"]
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--names", default="names.txt")
    ap.add_argument("--out", default="results.csv")
    ap.add_argument("--limit", type=int, default=120, help="max names this session (default 120)")
    ap.add_argument("--min-gap", type=float, default=5.0)
    ap.add_argument("--max-gap", type=float, default=10.0)
    ap.add_argument("--timeout", type=float, default=10.0, help="seconds to wait for Instagram's reply")
    ap.add_argument("--recheck", action="store_true", help="also re-check names already in results.csv")
    ap.add_argument("-y", "--yes", action="store_true", help="skip the confirmation prompt")
    a = ap.parse_args()

    names = [l.strip().lower().lstrip("@") for l in open(a.names) if l.strip() and not l.startswith("#")]
    bad = [n for n in names if not VALID.match(n)]
    if bad:
        sys.exit(f"invalid names in {a.names}: {bad[:10]}")
    done = load_done(a.out)
    if not a.recheck:
        names = [n for n in names if done.get(n) not in ("available", "taken", "invalid")]
    names = list(dict.fromkeys(names))
    if not names:
        sys.exit("nothing to check")

    n_run = min(len(names), a.limit)
    print(f"{len(names)} names left; checking up to {n_run} this run, ~{n_run * (a.min_gap + a.max_gap) / 2 / 60:.0f} min:")
    print("  " + " ".join(names[:60]) + (" ..." if len(names) > 60 else ""))
    if not a.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        sys.exit("cancelled")

    new_file = not os.path.exists(a.out)
    out = open(a.out, "a", newline="")
    w = csv.writer(out)
    if new_file:
        w.writerow(["name", "result", "message", "checked_at"])

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(CDP)
        except Exception as e:
            sys.exit(f"can't reach Chrome on {CDP} - run ./start-chrome.sh first ({e.__class__.__name__})")
        page = find_page(browser)
        page.bring_to_front()

        scope, box = username_box(page)
        while box.count() == 0 or not box.is_visible():
            input("Open Profiles > your profile > Username in the Chrome window, then press Enter here...")
            scope, box = username_box(page)
        original = box.input_value()
        log(f"found Username box (current value: {original!r})")

        counts, unknown_streak = {}, 0
        try:
            i = 0
            for name in names:
                if i >= a.limit:
                    break
                # urlcheck.py may have marked this name meanwhile
                if not a.recheck and load_done(a.out).get(name) in ("available", "taken", "invalid"):
                    continue
                i += 1
                result, msg = check_one(page, name, a.timeout)
                counts[result] = counts.get(result, 0) + 1
                w.writerow([name, result, msg, datetime.now().isoformat(timespec="seconds")])
                out.flush()
                mark = {"available": "FREE ", "taken": "taken", "invalid": "inval"}.get(result, "?????")
                log(f"{i:>3}/{n_run}  {mark}  {name}  {msg}")

                unknown_streak = unknown_streak + 1 if result == "unknown" else 0
                if unknown_streak >= 3:
                    raise Stop("3 unknown results in a row - page layout may have changed")

                if i < n_run:
                    gap = random.uniform(a.min_gap, a.max_gap)
                    if i % 25 == 0:
                        gap += random.uniform(30, 60)
                        log(f"short break ({gap:.0f}s)")
                    time.sleep(gap)
        except Stop as e:
            log(f"STOPPED: {e}")
        except KeyboardInterrupt:
            log("interrupted")
        finally:
            # put the real username back so the dialog is left unchanged, then drop the guard
            try:
                scope, box = username_box(page)
                if box.count() and box.is_visible() and VALID.match(original or ""):
                    type_name(box, original)
                page.evaluate(UNGUARD_JS)
            except Exception:
                pass
            out.close()
            # disconnect only; never close the user's Chrome
            log("summary: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    free = [n for n, r in load_done(a.out).items() if r == "available"]
    if free:
        print("\nAvailable so far:", " ".join(sorted(free, key=lambda s: (len(s), s))))


if __name__ == "__main__":
    main()
