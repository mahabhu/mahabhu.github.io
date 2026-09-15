# Regenerating `cv.pdf`

`cv.tex` is the source; `cv.pdf` is the output. Nothing else is kept in this
directory — the build writes every intermediate file (`.aux`, `.log`, `.fls`,
`.fdb_latexmk`, `.out`) to a scratch directory outside the repo, and only the
finished PDF is copied back.

From the repository root:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error \
        -outdir="$HOME/.cache/cvbuild" cv/cv.tex \
  && cp "$HOME/.cache/cvbuild/cv.pdf" cv/cv.pdf
```

Or from inside this directory:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error \
        -outdir="$HOME/.cache/cvbuild" cv.tex \
  && cp "$HOME/.cache/cvbuild/cv.pdf" cv.pdf
```

## Notes

- Needs TeX Live with `latexmk` and `pdflatex`. On Debian/Ubuntu:

  ```bash
  sudo apt install texlive-latex-extra latexmk
  ```

- Write `"$HOME/..."` rather than `~` in `-outdir=`. The shell does not expand a
  tilde after `=` in an ordinary argument, so `-outdir=~/.cache/cvbuild`
  silently creates a literal `./~/` directory instead of using your home
  directory.

- Keep the same `-outdir` between runs. `latexmk` stores its `.fdb_latexmk`
  database there, so it skips the work when nothing changed and still runs the
  extra pass `hyperref` needs when something did. `/tmp` works too, but the
  cache is lost on reboot.

- `cv.tex` is self-contained. The definitions that used to live in `resume.cls`
  are inlined in its preamble, so there is no class file to install.

## Keeping the website in step

[`../sync.py`](../sync.py) reads the Education section of `cv.tex` and
regenerates the Career timeline in [`../career.html`](../career.html), so the
page cannot drift from the CV. Commented-out (`% ...`) entries are included, in
the order they appear here. After editing the Education section, run from the
repository root:

```bash
python3 sync.py           # rewrite career.html
python3 sync.py --print   # preview the generated block, change nothing
python3 sync.py --check   # exit 1 if career.html is stale
```
