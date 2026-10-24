#!/usr/bin/env python3
"""Boxed Claude Code statusline (Nerd Font required), fully driven by a JSON config.

Install:
  1. save this file as ~/.claude/statusline.py
  2. python3 ~/.claude/statusline.py --dump-config > ~/.claude/statusline.json
  3. in ~/.claude/settings.json:
       "statusLine": {"type": "command", "command": "python3 ~/.claude/statusline.py"}

Config lookup order (first one found wins):
  --config PATH   |   $STATUSLINE_CONFIG   |   ~/.claude/statusline.json
  |   statusline.json next to this script
Anything missing from your config falls back to the built-in defaults below, so the
JSON only needs the keys you want to change.
"""
import copy
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

# ------------------------------------------------------------------ defaults ----
DEFAULTS = {
    "_comment": "Every value here is optional; missing keys fall back to built-in defaults.",
    "icons": {
        "house": "",
        "git": "",
        "worktree": "⧉",
        "model": "✱",
        "context": "\U000f09d1",
        "five_hour": "",
        "weekly": "",
        "session_duration": "",
        "tokens_in": "",
        "tokens_out": "",
        "throughput": "●",
        "ahead": "↑",
        "behind": "↓",
    },
    "labels": {
        "context": "ctx",
        "five_hour": "5h",
        "weekly": "7d",
        "tokens_in": "in",
        "tokens_out": "out",
        "throughput_unit": "t/m",
        "of": "of",
        "resets": "resets",
        "not_available": "n/a",
        "default_model": "Claude",
        "effort_separator": " · ",
    },
    "colors": {
        "text": "#c0caf5",
        "dim": "#565f89",
        "path": "#8ecbff",
        "git": "#a8f5a2",
        "session_id": "#565f89",
        "session_duration": "#7dcfff",
        "context_icon": "#bb9af7",
        "five_hour_icon": "#7dcfff",
        "weekly_icon": "#7aa2f7",
        "tokens_in_icon": "#7dcfff",
        "tokens_out_icon": "#bb9af7",
        "throughput": "#7dcfff",
    },
    "bars": {
        "caps": {"left": "◖", "right": "◗"},
        "fill": "█",
        "track_color": "#27332e",
        "color_stops": [
            {"from": 0, "color": "#39ff88"},
            {"from": 80, "color": "#ffd84a"},
            {"from": 91, "color": "#ff5c7a"},
        ],
        "context": {"color_stops": None},
        "five_hour": {"color_stops": None},
        "weekly": {"color_stops": None},
    },
    "border": {
        "gradient": {"from": "#39ff88", "to": "#6b7280", "swap_point": 0.5},
        "chars": {
            "top_left": "╭",
            "top_right": "╮",
            "bottom_left": "╰",
            "bottom_right": "╯",
            "horizontal": "─",
            "vertical": "│",
            "tee_left": "├",
            "tee_right": "┤",
        },
    },
    "model_badge": {
        "gradient": {"from": "#e0af68", "to": "#e0603c", "swap_point": 1.0},
        "text_color": "#1a1b26",
        "bold": True,
        "caps": {"left": "", "right": ""},
    },
    "sparkline": {
        "chars": "▁▂▃▄▅▆▇█",
        "empty_char": "─",
        "color_from": "#39ff88",
        "color_to": "#ff5c7a",
        "history_samples": 120,
        "sample_interval_seconds": 5,
    },
    "git": {"show_ahead_behind": True, "show_worktree": True},
    "layout": {
        "rows": ["header", "context", "five_hour", "weekly", "footer"],
        "min_width": 60,
        "max_width": 120,
        "side_margin": 4,
        "right_column_width": 22,
        "label_width": 3,
        "show_session_id": True,
        "show_session_duration": True,
    },
}

R = "\x1b[0m"
BOLD = "\x1b[1m"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


# ------------------------------------------------------------------- config ----
def deep_merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def find_config_path(argv):
    if "--config" in argv:
        i = argv.index("--config")
        if i + 1 < len(argv):
            return argv[i + 1]
    if os.environ.get("STATUSLINE_CONFIG"):
        return os.environ["STATUSLINE_CONFIG"]
    for p in (os.path.expanduser("~/.claude/cool-statusline.json"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "statusline.json")):
        if os.path.isfile(p):
            return p
    return None


def load_config(argv):
    cfg = copy.deepcopy(DEFAULTS)
    path = find_config_path(argv)
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                deep_merge(cfg, json.load(f))
        except Exception:
            pass  # a broken config must never break the statusline
    return cfg


CFG = copy.deepcopy(DEFAULTS)


# ------------------------------------------------------------------- colors ----
def rgb(h):
    m = HEX.match(str(h).strip())
    if not m:
        return None
    h = m.group(1)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def fg(h):
    c = rgb(h)
    return "\x1b[38;2;%d;%d;%dm" % c if c else ""


def bg(h):
    c = rgb(h)
    return "\x1b[48;2;%d;%d;%dm" % c if c else ""


def lerp(a, b, t):
    ca, cb = rgb(a), rgb(b)
    if not ca or not cb:
        return a
    t = max(0.0, min(1.0, t))
    return "#%02x%02x%02x" % tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))


def gradient_at(frac, a, b, swap_point):
    """Color at position `frac` (0..1); the gradient finishes at `swap_point`."""
    try:
        swap = float(swap_point)
    except (TypeError, ValueError):
        swap = 1.0
    t = 1.0 if swap <= 0 else min(1.0, frac / swap)
    return lerp(a, b, t)


def col(name):
    return fg(CFG["colors"].get(name, ""))


def icon(name):
    return CFG["icons"].get(name, "")


def label(name):
    return CFG["labels"].get(name, "")


def vlen(s):
    return len(ANSI.sub("", s))


# ------------------------------------------------------------------ helpers ----
def fmt_tokens(n):
    n = float(n or 0)
    if n >= 1_000_000:
        return "%.1fM" % (n / 1_000_000)
    if n >= 1_000:
        return "%.1fK" % (n / 1_000)
    return "%d" % n


def stops_for(key=None):
    stops = None
    if key:
        stops = (CFG["bars"].get(key) or {}).get("color_stops")
    stops = stops or CFG["bars"].get("color_stops") or []
    valid = [s for s in stops if isinstance(s, dict) and "from" in s and "color" in s]
    return sorted(valid, key=lambda s: s["from"])


def level_hex(pct, stops):
    color = stops[0]["color"] if stops else "#ffffff"
    for s in stops:
        if pct >= s["from"]:
            color = s["color"]
    return color


def pill_bar(pct, width, stops):
    """Rounded progress bar exactly `width` cells wide."""
    width = max(4, width)
    pct = max(0.0, min(100.0, float(pct)))
    filled = int(round(pct / 100 * width))
    if pct > 0 and filled == 0:
        filled = 1
    bars = CFG["bars"]
    c = fg(level_hex(pct, stops))
    track = fg(bars["track_color"])
    parts = [c + bars["caps"]["left"]]
    for i in range(1, width - 1):
        parts.append((c if i < filled else track) + bars["fill"])
    parts.append((c if filled >= width else track) + bars["caps"]["right"])
    return "".join(parts) + R


def gradient_badge(text):
    mb = CFG["model_badge"]
    g = mb["gradient"]
    chars = " " + text + " "
    n = max(1, len(chars))
    text_color = fg(mb["text_color"]) + (BOLD if mb.get("bold") else "")
    out = fg(g["from"]) + mb["caps"]["left"]
    for i, ch in enumerate(chars):
        c = gradient_at(i / max(1, n - 1), g["from"], g["to"], g["swap_point"])
        out += bg(c) + text_color + ch
    end = gradient_at(1.0, g["from"], g["to"], g["swap_point"])
    return out + R + fg(end) + mb["caps"]["right"] + R


def sparkline(vals, width):
    sp = CFG["sparkline"]
    if width <= 0:
        return ""
    chars = sp["chars"] or "█"
    vals = vals[-width:]
    dim = col("dim")
    if not vals:
        return dim + sp["empty_char"] * width + R
    hi = max(vals) or 1
    out = ""
    for v in vals:
        idx = min(len(chars) - 1, int(v / hi * (len(chars) - 1)))
        out += fg(lerp(sp["color_from"], sp["color_to"], v / hi)) + chars[idx]
    return dim + sp["empty_char"] * (width - len(vals)) + R + out + R


def until(ts):
    if ts is None:
        return ""
    try:
        if isinstance(ts, (int, float)):
            t = float(ts) / (1000 if ts > 1e12 else 1)
        else:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except Exception:
        return ""
    s = int(t - time.time())
    if s <= 0:
        return "now"
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return "%dd%dh" % (d, h)
    if h:
        return "%dh%02dm" % (h, m)
    return "%dm" % m


def dur(ms):
    s = int((ms or 0) / 1000)
    h, rem = divmod(s, 3600)
    m = rem // 60
    return "%dh%dm" % (h, m) if h else "%dm" % m


def worktree_name(cwd, run):
    """Name of the linked git worktree (None in the main checkout)."""
    try:
        gdir = os.path.realpath(os.path.join(cwd, run("rev-parse", "--git-dir")))
        cdir = os.path.realpath(os.path.join(cwd, run("rev-parse", "--git-common-dir")))
        if gdir != cdir:
            return os.path.basename(run("rev-parse", "--show-toplevel"))
    except Exception:
        pass
    return None


def git_info(cwd):
    gcfg = CFG["git"]
    gc = col("git")

    def run(*a):
        return subprocess.run(["git", "-C", cwd] + list(a), capture_output=True,
                              text=True, timeout=1.5).stdout.strip()
    try:
        branch = run("branch", "--show-current") or run("rev-parse", "--short", "HEAD")
        if not branch:
            return ""
        out = gc + icon("git") + " " + branch + R
        if gcfg.get("show_ahead_behind"):
            ab = run("rev-list", "--left-right", "--count", "@{u}...HEAD")
            if ab:  # empty when the branch has no upstream
                behind, ahead = [int(x) for x in ab.split()]
                counts = []
                if ahead:
                    counts.append("%s%d" % (icon("ahead"), ahead))
                if behind:
                    counts.append("%s%d" % (icon("behind"), behind))
                if counts:  # hidden entirely when both are 0
                    out += gc + " (" + " ".join(counts) + ")" + R
        if gcfg.get("show_worktree"):
            wt = worktree_name(cwd, run)
            if wt:
                out += "  " + gc + icon("worktree") + " " + wt + R
        return out
    except Exception:
        return ""


def term_width():
    try:
        with open("/dev/tty") as t:
            return os.get_terminal_size(t.fileno()).columns
    except Exception:
        pass
    try:
        return int(os.environ.get("COLUMNS", ""))
    except ValueError:
        return 100


def history(sid, tpm):
    """Rolling history of throughput samples for the sparkline."""
    sp = CFG["sparkline"]
    path = os.path.join(os.environ.get("TMPDIR", "/tmp"), "claude-statusline-%s.json" % (sid or "x"))
    try:
        with open(path) as f:
            st = json.load(f)
    except Exception:
        st = {"t": 0, "v": []}
    now = time.time()
    if now - st.get("t", 0) >= sp["sample_interval_seconds"] and tpm > 0:
        st["v"] = (st.get("v", []) + [tpm])[-int(sp["history_samples"]):]
        st["t"] = now
        try:
            with open(path, "w") as f:
                json.dump(st, f)
        except Exception:
            pass
    return st.get("v", [])


# --------------------------------------------------------------------- main ----
def main():
    global CFG
    argv = sys.argv[1:]
    if "--dump-config" in argv:
        out = copy.deepcopy(DEFAULTS)
        sys.stdout.write(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
        return
    CFG = load_config(argv)
    lay = CFG["layout"]
    dim, txt = col("dim"), col("text")

    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    cwd = (data.get("workspace") or {}).get("current_dir") or data.get("cwd") or os.getcwd()
    home = os.path.expanduser("~")
    shown_dir = cwd.replace(home, "~", 1) if cwd.startswith(home) else cwd

    model = data.get("model") or {}
    model_name = model.get("display_name") or model.get("id") or label("default_model")
    eff = data.get("effort")
    effort = eff.get("level") if isinstance(eff, dict) else eff
    effort = effort or os.environ.get("CLAUDE_CODE_EFFORT_LEVEL")
    badge = gradient_badge(icon("model") + " " + model_name
                           + (label("effort_separator") + str(effort) if effort else ""))

    cw = data.get("context_window") or {}
    size = cw.get("context_window_size") or 200_000
    cu = cw.get("current_usage") or {}
    used = ((cu.get("input_tokens") or 0) + (cu.get("cache_creation_input_tokens") or 0)
            + (cu.get("cache_read_input_tokens") or 0))
    ctx_pct = cw.get("used_percentage")
    if ctx_pct is None:
        ctx_pct = (used / size * 100) if size else 0
    if not used and ctx_pct:
        used = ctx_pct / 100 * size

    rl = data.get("rate_limits") or {}
    five, seven = rl.get("five_hour") or {}, rl.get("seven_day") or {}

    t_in = cw.get("total_input_tokens") or 0
    t_out = cw.get("total_output_tokens") or 0
    ms = (data.get("cost") or {}).get("total_duration_ms") or 0
    tpm = (t_in + t_out) / max(ms / 60000.0, 1.0)
    sid = data.get("session_id") or ""
    hist = history(sid, tpm)

    width = max(int(lay["min_width"]), min(term_width() - int(lay["side_margin"]), int(lay["max_width"])))
    inner = width - 4

    bc = CFG["border"]["chars"]
    bg_ = CFG["border"]["gradient"]

    def gcol(i):
        c = gradient_at(i / max(1, width - 1), bg_["from"], bg_["to"], bg_["swap_point"])
        return fg(c)

    def gtext(txt_, start):
        return "".join(gcol(start + k) + ch for k, ch in enumerate(txt_)) + R

    def line(left, right=""):
        gap = inner - vlen(left) - vlen(right)
        return (gcol(0) + bc["vertical"] + " " + R + left + " " * max(1, gap) + right
                + gcol(width - 1) + " " + bc["vertical"] + R)

    def sep():
        return gtext(bc["tee_left"] + bc["horizontal"] * (width - 2) + bc["tee_right"], 0)

    right_w = int(lay["right_column_width"])
    label_w = int(lay["label_width"])

    def bar_row(ic, lab, icon_color, pct, right_text, stops):
        right_text = " " * max(0, right_w - vlen(right_text)) + right_text
        left = icon_color + ic + R + " " + dim + lab.ljust(label_w) + R + " "
        bar_w = inner - vlen(left) - vlen(right_text) - 3
        return line(left + pill_bar(pct, bar_w, stops) + " ", right_text)

    def usage_row(ic, lab, icon_color, d, stops):
        if not d or d.get("used_percentage") is None:
            return line(icon_color + ic + R + " " + dim + lab.ljust(label_w) + "  "
                        + label("not_available") + R)
        p = d["used_percentage"]
        r = until(d.get("resets_at"))
        right = fg(level_hex(p, stops)) + ("%d%%" % round(p)).rjust(4) + R
        if r:
            right += dim + "  " + label("resets") + " " + r.ljust(6) + R
        return bar_row(ic, lab, icon_color, p, right, stops)

    # ---- rows
    def row_header():
        g = git_info(cwd)
        left = col("path") + icon("house") + " " + shown_dir + R + ("  " + g if g else "")
        return line(left, badge)

    def row_context():
        right = (txt + "%s %s %s" % (fmt_tokens(used), label("of"), fmt_tokens(size)) + R
                 + dim + " (%d%%)" % round(ctx_pct) + R)
        stops = stops_for("context")
        return bar_row(icon("context"), label("context"), col("context_icon"), ctx_pct, right, stops)

    def row_five_hour():
        return usage_row(icon("five_hour"), label("five_hour"), col("five_hour_icon"), five,
                         stops_for("five_hour"))

    def row_weekly():
        return usage_row(icon("weekly"), label("weekly"), col("weekly_icon"), seven,
                         stops_for("weekly"))

    def row_footer():
        left = (col("tokens_in_icon") + icon("tokens_in") + R + dim + " " + label("tokens_in") + " " + R
                + txt + fmt_tokens(t_in) + R
                + "  " + col("tokens_out_icon") + icon("tokens_out") + R + dim + " "
                + label("tokens_out") + " " + R + txt + fmt_tokens(t_out) + R
                + "  " + col("throughput") + icon("throughput") + " " + fmt_tokens(tpm) + " "
                + label("throughput_unit") + R + "  ")
        return line(left + sparkline(hist, inner - vlen(left) - 1))

    builders = {
        "header": row_header,
        "context": row_context,
        "five_hour": row_five_hour,
        "weekly": row_weekly,
        "footer": row_footer,
    }

    # ---- top / bottom borders
    tag = ""
    if lay.get("show_session_id") and sid:
        tag += col("session_id") + sid + R
    if lay.get("show_session_duration") and ms:
        tag += ("  " if tag else "") + col("session_duration") + icon("session_duration") + " " + dur(ms) + R
    if tag:
        a = max(1, width - 2 - vlen(tag) - 3)
        top = (gtext(bc["top_left"] + bc["horizontal"] * a, 0) + " " + tag + " "
               + gtext(bc["horizontal"] + bc["top_right"], width - 2))
    else:
        top = gtext(bc["top_left"] + bc["horizontal"] * (width - 2) + bc["top_right"], 0)
    bottom = gtext(bc["bottom_left"] + bc["horizontal"] * (width - 2) + bc["bottom_right"], 0)

    out = [top]
    names = [n for n in lay["rows"] if n in builders]
    for i, n in enumerate(names):
        if i:
            out.append(sep())
        out.append(builders[n]())
    out.append(bottom)
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
