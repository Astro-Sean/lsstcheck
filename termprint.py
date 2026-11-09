"""Terminal output helpers for scripts and CLIs.

Dependency-free status lines, tables, boxes, and progress output with
automatic color and Unicode fallbacks. Symbols use ASCII or escape-coded
Unicode so the source stays plain ASCII and output degrades cleanly on
dumb terminals, pipes, and NO_COLOR environments.

    import sys
    sys.path.insert(0, "<optimize_prints skill dir>/scripts")
    import termprint as tp

    tp.header("Reduction pipeline")
    tp.ok("bias frames stacked")
    tp.warn("3 flats saturated; skipped")
    tp.fail("could not read SP001.fits")          # goes to stderr
    tp.table(["file", "exptime", "status"], rows)
    tp.box("QA summary", ["7 files ok", "1 skipped", "0 failed"])

Rules these helpers enforce so output stays scannable:
- One symbol per line, always in the same column: ok/warn/fail/info.
- Errors go to stderr; results stay on stdout so pipes work.
- No emoji; a fixed symbol set with ASCII fallbacks is portable.
- Tables cap at six columns; numbers right-align, text left-aligns.
"""

from __future__ import annotations

import os
import sys
import time

# Symbols are escape-coded so this file stays ASCII-only.
_OK = "\u2713"
_WARN = "\u26a0"
_FAIL = "\u2717"
_INFO = "\u2192"
_ASCII = {_OK: "[ok]", _WARN: "[warn]", _FAIL: "[FAIL]", _INFO: "->"}

_CODES = {
    "ok": "32",      # green
    "warn": "33",    # yellow
    "fail": "31",    # red
    "info": "36",    # cyan
    "dim": "2",
    "bold": "1",
}


def supports_color(stream=None):
    """Honor NO_COLOR, dumb terminals, and non-tty output."""
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    term = os.environ.get("TERM", "")
    if term in ("", "dumb"):
        return False
    return hasattr(stream, "isatty") and stream.isatty()


_COLOR = supports_color()
_COLOR_ERR = supports_color(sys.stderr)

# Set True to force ASCII symbols ([ok], ->) regardless of encoding.
FORCE_ASCII = False


def _use_unicode(stream):
    if FORCE_ASCII:
        return False
    enc = (getattr(stream, "encoding", "") or "").lower()
    return "utf" in enc


def _sym(symbol, color, stream):
    if not _use_unicode(stream):
        return _ASCII[symbol]
    if (stream is sys.stderr and _COLOR_ERR) or \
            (stream is not sys.stderr and _COLOR):
        return f"\033[{_CODES[color]}m{symbol}\033[0m"
    return symbol


def _line(symbol, color, msg, stream):
    print(f"{_sym(symbol, color, stream)} {msg}", file=stream, flush=True)


def ok(msg):
    _line(_OK, "ok", msg, sys.stdout)


def warn(msg):
    _line(_WARN, "warn", msg, sys.stdout)


def info(msg):
    _line(_INFO, "info", msg, sys.stdout)


def fail(msg):
    _line(_FAIL, "fail", msg, sys.stderr)


def die(msg, code=1):
    fail(msg)
    raise SystemExit(code)


def header(title, width=60, char="="):
    """Section banner: '===== title ====='."""
    side = max(2, (width - len(title) - 2) // 2)
    print(char * side + " " + title + " " + char * side)


def subheader(title, width=60):
    """Lighter phase banner: '---- title ----'; use under a header."""
    header(title, width=width, char="-")


def rule(char="-", width=60):
    print(char * width)


def kv(key, value, width=24):
    """Aligned key-value pair: 'exptime        : 60 s'."""
    print(f"{key:<{width}} : {value}")


def table(headers, rows, aligns=None, max_cols=6):
    """Print an aligned table. Text left-aligns, numbers right-align.

    headers : list of column names (max max_cols)
    rows    : iterable of row tuples/lists
    aligns  : optional 'l'/'r' per column; default auto-detects numbers
    """
    headers = [str(h) for h in headers[:max_cols]]
    rows = [[str(c) for c in r[:max_cols]] for r in rows]
    if not headers:
        return
    ncols = len(headers)

    def is_num(s):
        try:
            float(s)
            return True
        except (ValueError, TypeError):
            return False

    if aligns is None:
        aligns = ["r" if all(is_num(r[i]) for r in rows) and rows else "l"
                  for i in range(ncols)]

    widths = [len(headers[i]) for i in range(ncols)]
    for r in rows:
        for i in range(ncols):
            widths[i] = max(widths[i], len(r[i]))

    def fmt_row(cells):
        parts = []
        for i in range(ncols):
            w = widths[i]
            parts.append(f"{cells[i]:>{w}}" if aligns[i] == "r"
                         else f"{cells[i]:<{w}}")
        return "  ".join(parts).rstrip()

    print(fmt_row(headers))
    print(fmt_row(["-" * w for w in widths]))
    for r in rows:
        print(fmt_row(r))


def box(title, lines, width=None, stream=None):
    """Multi-check summary box; use for >= 3 results, not one-liners."""
    stream = stream or sys.stdout
    body = [title] + [""] + [str(l) for l in lines]
    w = width or (max(len(l) for l in body) + 4)
    edge = "+" + "-" * (w - 2) + "+"
    print(edge, file=stream)
    for l in body:
        print(f"| {l:<{w - 4}} |", file=stream)
    print(edge, file=stream)


def progress(i, total, label="", every=1, width=30):
    """In-place progress line ending with a newline at completion.

    Throttle-heavy loops print at most 'every' iterations; final call
    always emits. Call with i == total once to close the line.
    """
    if i % every and i != total:
        return
    frac = min(1.0, i / total) if total else 1.0
    # on a pipe there is no carriage return; emit a line only when a
    # quartile boundary is crossed so logs stay readable
    if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
        prev = max(i - every, 0) / total if total else 0
        if i == total or int(frac * 4) != int(prev * 4):
            print(f"{label} {100 * frac:5.1f}%")
        return
    filled = int(width * frac)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\r{label} [{bar}] {100 * frac:5.1f}%",
          end="\n" if i >= total else "", flush=True)


class timed:
    """Context manager: 'label... done in 0.42 s' on exit."""

    def __init__(self, label):
        self.label = label

    def __enter__(self):
        print(f"{self.label}... ", end="", flush=True)
        self._t0 = time.monotonic()
        return self

    def __exit__(self, exc_type, *_):
        dt = time.monotonic() - self._t0
        if exc_type is None:
            print(f"done in {dt:.2f} s")
        else:
            print(f"FAILED after {dt:.2f} s")
        return False


__all__ = [
    "ok", "warn", "fail", "info", "die", "header", "subheader", "rule",
    "kv", "table", "box", "progress", "timed", "supports_color",
]
