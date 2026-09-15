#!/usr/bin/env python3
"""Generate assets/js/palette.js from assets/csv/color_wheel_hex.csv.

The site's palette changes every hour. The hour picks a column of the colour
wheel (01:00 -> col1, 14:00 -> col14, 00:00 -> col24), and that column's two
rings become the two ends of the palette:

    ring 2  ->  the light end  (replaces what used to be white)
    ring 9  ->  the dark end   (replaces what used to be black)

Ring 2 is used verbatim; every entry is already pale enough to sit under text.
Ring 9 is *saturated*, not dark -- at noon it is #FCF11A, which scores 1.01:1
against its own ring 2 and would be invisible. So ring 9 is taken as a hue and
re-lit: its hue and chroma are kept, its OKLCH lightness is lowered until the
text it paints clears WCAG AA. Nothing is hue-shifted; only lightness moves.

Re-run after editing the CSV:  python3 gen_palette.py
"""
import csv, json, math

CSV, OUT = "assets/csv/color_wheel_hex.csv", "assets/js/palette.js"
AA_BODY, AA_UI = 4.5, 3.0

# ---------- colour maths ----------
def hex2rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
def rgb2hex(c):
    return "#%02X%02X%02X" % tuple(round(max(0.0, min(1.0, x)) * 255) for x in c)
def _lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def _gam(c): return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055

def rgb2oklab(c):
    r, g, b = (_lin(x) for x in c)
    l = (0.4122214708*r + 0.5363325363*g + 0.0514459929*b) ** (1/3)
    m = (0.2119034982*r + 0.6806995451*g + 0.1073969566*b) ** (1/3)
    s = (0.0883024619*r + 0.2817188376*g + 0.6299787005*b) ** (1/3)
    return (0.2104542553*l + 0.7936177850*m - 0.0040720468*s,
            1.9779984951*l - 2.4285922050*m + 0.4505937099*s,
            0.0259040371*l + 0.7827717662*m - 0.8086757660*s)

def oklab2rgb(lab):
    L, a, b = lab
    l = (L + 0.3963377774*a + 0.2158037573*b) ** 3
    m = (L - 0.1055613458*a - 0.0638541728*b) ** 3
    s = (L - 0.0894841775*a - 1.2914855480*b) ** 3
    return tuple(_gam(x) for x in (
        4.0767416621*l - 3.3077115913*m + 0.2309699292*s,
       -1.2684380046*l + 2.6097574011*m - 0.3413193965*s,
       -0.0041960863*l - 0.7034186147*m + 1.7076147010*s))

def to_lch(h):
    L, a, b = rgb2oklab(hex2rgb(h))
    return L, math.hypot(a, b), math.atan2(b, a)

def from_lch(L, C, h):
    """Back to hex, shrinking chroma until the colour is inside sRGB."""
    while C > 0:
        rgb = oklab2rgb((L, C * math.cos(h), C * math.sin(h)))
        if all(-0.001 <= x <= 1.001 for x in rgb):
            return rgb2hex(rgb)
        C -= 0.005
    return rgb2hex(oklab2rgb((L, 0, 0)))

def relum(h):
    r, g, b = (_lin(x) for x in hex2rgb(h))
    return 0.2126*r + 0.7152*g + 0.0722*b
def contrast(a, b):
    x, y = relum(a), relum(b)
    x, y = max(x, y), min(x, y)
    return (x + 0.05) / (y + 0.05)

def relight(src, against, target, lo=0.10, hi=0.75):
    """Keep src's hue/chroma, pick the LIGHTEST lightness that still clears
    `target` contrast against every colour in `against` (so the hour stays as
    vivid as legibility allows)."""
    _, C, h = to_lch(src)
    best = from_lch(lo, C, h)
    for i in range(60):                       # 0.75 -> 0.10 in fine steps
        L = hi - (hi - lo) * i / 59
        cand = from_lch(L, C, h)
        if all(contrast(cand, bg) >= target for bg in against):
            return cand
    return best

# ---------- build ----------
rings = {r[0]: r[1:] for r in csv.reader(open(CSV))}
ring2, ring9 = rings["2"], rings["9"]

palette, report = [], []
for hour in list(range(0, 24)):
    col = 24 if hour == 0 else hour           # 00:00 wraps to column 24
    tint, vivid = ring2[col - 1], ring9[col - 1]

    _, tC, tH = to_lch(tint)
    surface = from_lch(0.975, tC * 0.45, tH)  # cards: palest tint, still tinted
    bg      = tint                            # page: ring 2 verbatim
    border  = from_lch(to_lch(tint)[0] - 0.05, tC * 0.9, tH)

    # bars carry tint-coloured text, headings sit on bg and surface
    shade = relight(vivid, [tint, surface, bg], AA_BODY + 1.0)
    ink   = relight(vivid, [surface, bg], AA_BODY)
    muted = relight(vivid, [surface, bg], AA_UI)
    hover = from_lch(to_lch(surface)[0] - 0.07, tC * 0.7, tH)   # sidebar button hover
    active = from_lch(to_lch(shade)[0] + 0.18, to_lch(shade)[1] * 0.8, to_lch(shade)[2])

    palette.append(dict(h=hour, col=col, tint=tint, vivid=vivid, bg=bg,
                        surface=surface, border=border, shade=shade,
                        ink=ink, muted=muted, hover=hover, active=active))
    report.append((hour, col, tint, vivid, shade,
                   contrast(ink, surface), contrast(tint, shade), contrast(muted, surface)))

rows = ",\n".join(
    '  {h:%2d,c:%2d,tint:"%s",vivid:"%s",bg:"%s",surface:"%s",border:"%s",shade:"%s",ink:"%s",muted:"%s",hover:"%s",active:"%s"}'
    % (p["h"], p["col"], p["tint"], p["vivid"], p["bg"], p["surface"], p["border"],
       p["shade"], p["ink"], p["muted"], p["hover"], p["active"]) for p in palette)

open(OUT, "w").write('''/* GENERATED by gen_palette.py from assets/csv/color_wheel_hex.csv -- do not edit.
   One entry per hour. The hour picks a colour-wheel column (01:00 -> col1,
   14:00 -> col14, 00:00 -> col24); ring 2 of that column is the light end and
   ring 9 the dark end. `tint`/`vivid` are the two rings verbatim; the rest are
   ring 9 re-lit in OKLCH (hue and chroma preserved) so text clears WCAG AA. */
(function () {
  var HOURS = [
%s
  ];

  function paint() {
    var p = HOURS[new Date().getHours()], s = document.documentElement.style;
    for (var k in p) if (typeof p[k] === "string") s.setProperty("--" + k, p[k]);
    document.documentElement.dataset.hour = p.h;
    return p;
  }

  paint();

  // Re-paint when the clock rolls over, so a page left open keeps up.
  (function schedule() {
    var now = new Date(), next = new Date(now);
    next.setHours(now.getHours() + 1, 0, 1, 0);
    setTimeout(function () { paint(); schedule(); }, next - now);
  })();
})();
''' % rows)

print("wrote", OUT)
print("\\nhh col  ring2    ring9    shade(re-lit)  ink/surface  tint/shade  muted/surface")
for hour, col, tint, vivid, shade, c1, c2, c3 in report:
    print("%02d %3d  %s  %s  %s        %5.2f       %5.2f       %5.2f"
          % (hour, col, tint, vivid, shade, c1, c2, c3))
print("\\nminimums -> ink/surface %.2f   tint/shade %.2f   muted/surface %.2f"
      % (min(r[5] for r in report), min(r[6] for r in report), min(r[7] for r in report)))
