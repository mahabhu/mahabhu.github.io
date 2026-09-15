#!/usr/bin/env python3
"""Build the site palette from assets/csv/color_wheel_hex.csv.

The day is cut into 32 slots of 45 minutes. Slot i runs from (i-1)*45 minutes
after midnight to i*45, so i = minutes_since_midnight // 45 + 1, and i is
1-based (slot 1 is 00:00-00:45, slot 32 is 23:15-00:00).

Each slot needs three colours -- white, black and select. How those are derived
is up to you: see the YOUR FORMULAS block below. Everything outside that block
just reads the CSV, hands you helpers, and writes the results into
assets/js/palette.js and the fallback in assets/css/site.css.

    python3 gen_palette.py            regenerate, print a report
    python3 gen_palette.py --dry-run  print the report, write nothing
"""
import csv, re, sys, math

CSV_PATH  = "assets/csv/color_wheel_hex.csv"
JS_PATH   = "assets/js/palette.js"
CSS_PATH  = "assets/css/site.css"
SLOTS     = 32     # sections per day
SLOT_MIN  = 45     # minutes per section  (SLOTS * SLOT_MIN must be 1440)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers available to your formulas.  You do not need to read this part.
# ─────────────────────────────────────────────────────────────────────────────
def _load(path):
    rows = {r[0]: r[1:] for r in csv.reader(open(path)) if r[0] != "ring"}
    return {int(k): v for k, v in rows.items()}

WHEEL = _load(CSV_PATH)                 # WHEEL[ring][col-1] -> "#RRGGBB"
N_RINGS, N_COLS = len(WHEEL), len(WHEEL[1])

def cell(ring, col):
    """The wheel cell at (ring, col). Both wrap, and both are 1-based, so
    cell(8, 0) is column 32 and cell(8, 33) is column 1."""
    ring = ((int(ring) - 1) % N_RINGS) + 1
    return WHEEL[ring][(int(col) - 1) % N_COLS]

def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

def hexs(c):
    return "#%02X%02X%02X" % tuple(round(max(0.0, min(1.0, x)) * 255) for x in c)

def _lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def _gam(c): return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055

def luminance(h):
    """WCAG relative luminance, 0 (black) to 1 (white)."""
    r, g, b = (_lin(x) for x in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(a, b):
    """WCAG contrast ratio, 1.0 to 21.0. Body text wants 4.5 or more."""
    x, y = luminance(a), luminance(b)
    x, y = max(x, y), min(x, y)
    return (x + 0.05) / (y + 0.05)

def _oklab(h):
    r, g, b = (_lin(x) for x in rgb(h))
    l = (0.4122214708*r + 0.5363325363*g + 0.0514459929*b) ** (1/3)
    m = (0.2119034982*r + 0.6806995451*g + 0.1073969566*b) ** (1/3)
    s = (0.0883024619*r + 0.2817188376*g + 0.6299787005*b) ** (1/3)
    return (0.2104542553*l + 0.7936177850*m - 0.0040720468*s,
            1.9779984951*l - 2.4285922050*m + 0.4505937099*s,
            0.0259040371*l + 0.7827717662*m - 0.8086757660*s)

def _unoklab(L, a, b):
    l = (L + 0.3963377774*a + 0.2158037573*b) ** 3
    m = (L - 0.1055613458*a - 0.0638541728*b) ** 3
    s = (L - 0.0894841775*a - 1.2914855480*b) ** 3
    return tuple(_gam(x) for x in (
        4.0767416621*l - 3.3077115913*m + 0.2309699292*s,
       -1.2684380046*l + 2.6097574011*m - 0.3413193965*s,
       -0.0041960863*l - 0.7034186147*m + 1.7076147010*s))

def lightness(h):
    """Perceptual lightness, 0.0 (black) to 1.0 (white). Unlike luminance()
    this matches how light a colour *looks*."""
    return _oklab(h)[0]

def set_lightness(h, L):
    """Same hue and saturation, new perceptual lightness. Chroma is reduced
    only if the result would fall outside sRGB."""
    _, a, b = _oklab(h)
    C, ang = math.hypot(a, b), math.atan2(b, a)
    while C > 0:
        out = _unoklab(L, C * math.cos(ang), C * math.sin(ang))
        if all(-0.001 <= x <= 1.001 for x in out):
            return hexs(out)
        C -= 0.005
    return hexs(_unoklab(L, 0, 0))

def darken(h, amount):
    """Drop perceptual lightness by `amount` (0.0-1.0)."""
    return set_lightness(h, max(0.0, lightness(h) - amount))

def lighten(h, amount):
    return set_lightness(h, min(1.0, lightness(h) + amount))

def mix(a, b, t):
    """Blend a into b. t=0 gives a, t=1 gives b."""
    ca, cb = rgb(a), rgb(b)
    return hexs(tuple(ca[i] * (1 - t) + cb[i] * t for i in range(3)))

def best_contrast(against, candidates):
    """The candidate that contrasts most with `against`."""
    return max(candidates, key=lambda c: contrast(c, against))


# ═════════════════════════════════════════════════════════════════════════════
#  YOUR FORMULAS -- everything between these two banners is yours to rewrite.
#
#  Three functions, each given the slot number i (1 to 32) and each returning
#  one "#RRGGBB" string. They may return wheel cells or any colour you compute.
#
#  Available to you:
#    cell(ring, col)        a wheel cell; ring 1-10, col 1-32, both wrap
#    WHEEL[ring][col-1]     the raw grid, if you want to loop over it
#    N_RINGS, N_COLS        10 and 32
#    SLOTS, SLOT_MIN        32 and 45
#
#    lightness(h)           how light it looks, 0.0-1.0
#    set_lightness(h, L)    same hue, new lightness
#    lighten(h, x) / darken(h, x)
#    mix(a, b, t)           blend, t=0 is a, t=1 is b
#    contrast(a, b)         WCAG ratio, 1-21; body text wants >= 4.5
#    luminance(h)           WCAG relative luminance
#    best_contrast(against, candidates)
#
#  The report printed after each run scores whatever you write here, so you can
#  edit, re-run, and read the contrast column to see if it worked.
# ═════════════════════════════════════════════════════════════════════════════

# RING = 8

def white(i):
    """Every surface that used to be white: page, cards, text on the bars."""
    return cell(1, i)

def black(i):
    """Every bar and every piece of text."""
    return cell(10, i - 1)

def select(i):
    """Hover, and the current page's sidebar button."""
    return cell(5, i)

# ═════════════════════════════════════════════════════════════════════════════
#  END OF YOUR FORMULAS -- the rest just validates, reports and writes files.
# ═════════════════════════════════════════════════════════════════════════════


HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

def build():
    out = []
    for i in range(1, SLOTS + 1):
        trio = []
        for name, fn in (("white", white), ("black", black), ("select", select)):
            try:
                v = fn(i)
            except Exception as e:
                sys.exit("%s(%d) raised %s: %s" % (name, i, type(e).__name__, e))
            if not isinstance(v, str) or not HEX_RE.match(v):
                sys.exit("%s(%d) returned %r; expected a '#RRGGBB' string" % (name, i, v))
            trio.append(v.upper())
        out.append(tuple(trio))
    return out

def report(table):
    print("slot  window       white    black    select     text  hover  swatch")
    worst, passing = 99.0, 0
    for i, (w, b, s) in enumerate(table, 1):
        start, end = (i - 1) * SLOT_MIN, i * SLOT_MIN
        t, h = contrast(b, w), contrast(s, w)
        worst = min(worst, t)
        passing += t >= 4.5
        swatch = "".join("\033[48;2;%d;%d;%dm  \033[0m" % tuple(round(x * 255) for x in rgb(c))
                         for c in (w, b, s))
        flag = " " if t >= 4.5 else ("!" if t >= 3.0 else "!!")
        print("%4d  %02d:%02d-%02d:%02d  %s  %s  %s  %5.2f%s %5.2f  %s"
              % (i, start // 60, start % 60, (end // 60) % 24, end % 60,
                 w, b, s, t, flag, h, swatch))
    print("\n  text contrast: worst %.2f:1, %d of %d slots reach the 4.5:1 body-text minimum"
          % (worst, passing, SLOTS))
    if passing < SLOTS:
        print("  (! is under 4.5, !! is under 3.0 -- adjust the formulas above)")

def write(table):
    rows = ",\n".join('  ["%s","%s","%s"]' % t for t in table)
    open(JS_PATH, "w").write('''/* GENERATED by gen_palette.py -- do not edit; edit the formulas in that file.
   %d slots of %d minutes. Slot index = minutes_since_midnight / %d, and each
   row is [white, black, select] for that slot, in slot order. */
(function () {
  var SLOTS = [
%s
  ];
  var SLOT_MIN = %d;

  function paint() {
    var d = new Date(),
        i = Math.floor((d.getHours() * 60 + d.getMinutes()) / SLOT_MIN),
        c = SLOTS[i], s = document.documentElement.style;
    s.setProperty("--white", c[0]);
    s.setProperty("--black", c[1]);
    s.setProperty("--select", c[2]);
    document.documentElement.dataset.slot = i + 1;
  }

  paint();

  // Re-paint on the next slot boundary, so a page left open keeps up.
  (function schedule() {
    var d = new Date(), mins = d.getHours() * 60 + d.getMinutes(),
        next = (Math.floor(mins / SLOT_MIN) + 1) * SLOT_MIN,
        ms = (next - mins) * 60000 - d.getSeconds() * 1000 - d.getMilliseconds() + 1000;
    setTimeout(function () { paint(); schedule(); }, ms);
  })();
})();
''' % (SLOTS, SLOT_MIN, SLOT_MIN, rows, SLOT_MIN))

    w, b, s = table[0]
    block = ("    /* palette:start -- written by gen_palette.py; edit the formulas there */\n"
             "    --white: %s;    /* every surface that used to be white */\n"
             "    --black: %s;    /* every bar, every piece of text */\n"
             "    --select: %s;   /* hover and current-page states */\n"
             "    /* palette:end */" % (w, b, s))
    css = open(CSS_PATH).read()
    css, n = re.subn(r"    /\* palette:start.*?/\* palette:end \*/", block, css, count=1, flags=re.S)
    if n != 1:
        sys.exit("palette:start/end markers not found in " + CSS_PATH)
    open(CSS_PATH, "w").write(css)
    print("\n  wrote %s (%d slots) and the slot-1 fallback in %s" % (JS_PATH, SLOTS, CSS_PATH))

if __name__ == "__main__":
    assert SLOTS * SLOT_MIN == 1440, "SLOTS * SLOT_MIN must cover a 1440-minute day"
    table = build()
    report(table)
    if "--dry-run" in sys.argv:
        print("\n  --dry-run: nothing written")
    else:
        write(table)
