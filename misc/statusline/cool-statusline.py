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
Layout: every row is made of elements (run with --list-elements) placed in left / center /
right groups; each element can be sized (columns, "N%", "auto", "flex"). The top and bottom
border bars take elements too. See cool-statusline.schema.json for all options.
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
        "clock": "",
        "cost": "$",
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
        "throughput_unit_sec": "t/s",
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
        "clock": "#7dcfff",
        "cost": "#e0af68",
        "lines_added": "#a8f5a2",
        "lines_removed": "#ff5c7a",
        "version": "#565f89",
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
        # Each row is {"left": [...], "center": [...], "right": [...], "gap": N, "divider": bool}.
        # A row may also be a bare list (= its "left" group). Items are element ids
        # ("dir", "git", ...) or objects: {"id", "width", "weight", "align", ...}.
        # Grid rows: {"columns": 1-5, "col_widths": [weights], "items": [{"id", "span", "col"}]}.
        # width: N columns | "N%" | "auto" (natural size) | "flex" (share the leftover).
        "rows": [
            {"left": ["dir", "git"], "right": ["model"]},
            {"left": [{"id": "context", "width": "flex"}]},
            {"left": [{"id": "five_hour", "width": "flex"},
                      {"id": "seven_day", "width": "flex"}], "gap": 3},
            {"left": ["in_tok", "out_tok", "tok_per_min", "tok_per_sec", {"id": "throughput", "width": "flex"}]},
        ],
        # Top / bottom border bars take the same items (plus session_id, session_duration,
        # clock, cost, lines, version, text) in left / center / right groups.
        "top": {"left": [], "center": [], "right": ["session_id", "session_duration"]},
        "bottom": {"left": [], "center": [], "right": []},
        "gap": 2,
        "border_gap": 2,
        "row_dividers": True,
        "equal_bars": False,  # bars in one row get the width of the narrowest (row-level override too)
        "clock_format": "%H:%M",
        "min_width": 60,
        "max_width": 1000,
        "side_margin": 4,
        "label_width": 3,
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
    if "--columns" in sys.argv[:-1]:
        try:
            return int(sys.argv[sys.argv.index("--columns") + 1])
        except ValueError:
            pass
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


# ------------------------------------------------------------------- layout ----
def truncate(s, w):
    """Cut `s` to `w` visible cells, keeping ANSI codes intact."""
    if w <= 0:
        return ""
    if vlen(s) <= w:
        return s
    out, seen = "", 0
    for tok in re.split(r"(\x1b\[[0-9;]*m)", s):
        if ANSI.fullmatch(tok):
            out += tok
        else:
            take = tok[:max(0, w - seen)]
            out += take
            seen += len(take)
    return out + R


def fit(s, w, align="left"):
    """Pad / truncate `s` to exactly `w` visible cells."""
    s = truncate(s, w)
    pad = w - vlen(s)
    if pad <= 0:
        return s
    if align == "right":
        return " " * pad + s
    if align == "center":
        return " " * (pad // 2) + s + " " * (pad - pad // 2)
    return s + " " * pad


def tail_cut(text, w):
    """Shorten plain `text` to `w` cells keeping its end ('…/long/path')."""
    return text if len(text) <= w else ("…" + text[len(text) - w + 1:] if w > 1 else text[-w:])


def norm_item(it):
    if isinstance(it, str):
        return {"id": it}
    return dict(it) if isinstance(it, dict) and "id" in it else None


def norm_row(row):
    if isinstance(row, list):
        row = {"left": row}
    return row if isinstance(row, dict) else {}


def parse_width(spec, inner):
    """-> ('fixed', n) | ('auto', None) | ('flex', None)"""
    w = spec.get("width", "auto")
    if isinstance(w, bool):
        return "auto", None
    if isinstance(w, (int, float)):
        return "fixed", max(0, int(w))
    w = str(w).strip().lower()
    if w == "flex":
        return "flex", None
    if w.endswith("%"):
        try:
            return "fixed", int(inner * float(w[:-1]) / 100)
        except ValueError:
            return "auto", None
    try:
        return "fixed", max(0, int(w))
    except ValueError:
        return "auto", None


def last_tps(sid, out_tokens, api_ms):
    """Output tokens/sec of the latest response: delta of the cumulative output-token and
    API-time counters since the previous refresh (None until a response has been seen)."""
    path = os.path.join(os.environ.get("TMPDIR", "/tmp"), "claude-statusline-tps-%s.json" % (sid or "x"))
    try:
        with open(path) as f:
            st = json.load(f)
    except Exception:
        st = {}
    d_out, d_api = out_tokens - st.get("out", out_tokens), api_ms - st.get("api", api_ms)
    if d_out > 0 and d_api > 0:
        st["tps"] = d_out / (d_api / 1000.0)
    st["out"], st["api"] = out_tokens, api_ms
    try:
        with open(path, "w") as f:
            json.dump(st, f)
    except Exception:
        pass
    return st.get("tps")


# ------------------------------------------------------------------- studio ----
ELEMENT_IDS = ["dir", "git", "model", "context", "five_hour", "seven_day", "in_tok", "out_tok",
               "tok_per_min", "tok_per_sec", "throughput", "session_id", "session_duration",
               "clock", "cost", "lines", "version", "text"]


def studio(argv):
    """Local config GUI: serves cool-statusline-studio.html; previews use this very script."""
    import http.server
    import secrets
    import tempfile
    import webbrowser

    script = os.path.realpath(__file__)
    page = open(os.path.join(os.path.dirname(script), "cool-statusline-studio.html"),
                encoding="utf-8").read()
    cfg_path = find_config_path(argv) or os.path.expanduser("~/.claude/cool-statusline.json")
    token = secrets.token_hex(16)
    sid = "studio-preview"
    tmpdir = os.environ.get("TMPDIR", "/tmp")

    def read_cfg():
        try:
            with open(cfg_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def sample(out_tokens, api_ms):
        now = int(time.time())
        return {
            "session_id": sid, "cwd": os.getcwd(), "version": "2.1.0",
            "model": {"display_name": "Sonnet 5.5"}, "effort": "high",
            "context_window": {"context_window_size": 1000000, "used_percentage": 14,
                               "current_usage": {"input_tokens": 140000},
                               "total_input_tokens": 420000, "total_output_tokens": out_tokens},
            "rate_limits": {"five_hour": {"used_percentage": 42, "resets_at": now + 6000},
                            "seven_day": {"used_percentage": 85, "resets_at": now + 200000}},
            "cost": {"total_duration_ms": 4980000, "total_api_duration_ms": api_ms,
                     "total_cost_usd": 3.456, "total_lines_added": 120, "total_lines_removed": 30},
        }

    def render(layout, cols):
        cfg = read_cfg()
        cfg["layout"] = layout
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(cfg, f)
            cfg_file = f.name
        try:
            try:
                os.remove(os.path.join(tmpdir, "claude-statusline-tps-%s.json" % sid))
            except OSError:
                pass
            with open(os.path.join(tmpdir, "claude-statusline-%s.json" % sid), "w") as f:
                json.dump({"t": time.time(), "v": [1500, 2600, 4000, 3200, 5700, 5200, 6100, 4300]}, f)
            res = None
            for out_t, api in ((50000, 100000), (50600, 110000)):  # 2nd call yields 60 t/s
                res = subprocess.run([sys.executable, script, "--config", cfg_file, "--columns", str(cols)],
                                     input=json.dumps(sample(out_t, api)), capture_output=True,
                                     text=True, timeout=10)
            return res.stdout or res.stderr
        finally:
            os.unlink(cfg_file)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            b = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def host_ok(self):  # blocks DNS-rebinding
            return self.headers.get("Host", "") in ("127.0.0.1:%d" % port, "localhost:%d" % port)

        def do_GET(self):
            if not self.host_ok():
                return self.send(403, "{}")
            if self.path == "/":
                return self.send(200, page.replace("__TOKEN__", token), "text/html")
            if self.path == "/api/state":
                layout = deep_merge(copy.deepcopy(DEFAULTS["layout"]), read_cfg().get("layout", {}))
                return self.send(200, json.dumps({"layout": layout, "defaults": DEFAULTS["layout"],
                                                  "elements": ELEMENT_IDS, "path": cfg_path}))
            self.send(404, "{}")

        def do_POST(self):
            if not self.host_ok() or self.headers.get("X-Token") != token:
                return self.send(403, "{}")
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if self.path == "/api/render":
                    return self.send(200, json.dumps({"text": render(body["layout"], int(body["cols"]))}))
                if self.path == "/api/save":
                    cfg = read_cfg()
                    cfg["layout"] = body["layout"]
                    with open(cfg_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=2, ensure_ascii=False)
                        f.write("\n")
                    return self.send(200, json.dumps({"saved": cfg_path}))
            except Exception as e:
                return self.send(500, json.dumps({"error": str(e)}))
            self.send(404, "{}")

    want = 8765
    if "--port" in argv[:-1]:
        want = int(argv[argv.index("--port") + 1])
    try:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", want), Handler)
    except OSError:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    url = "http://127.0.0.1:%d/" % port
    print("Statusline Studio on %s  (editing %s)  -  Ctrl+C to stop" % (url, cfg_path))
    if "--no-open" not in argv:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


# --------------------------------------------------------------------- main ----
def main():
    global CFG
    argv = sys.argv[1:]
    if "--studio" in argv:
        studio(argv)
        return
    if "--dump-config" in argv:
        sys.stdout.write(json.dumps(copy.deepcopy(DEFAULTS), indent=2, ensure_ascii=False) + "\n")
        return
    CFG = load_config(argv)
    lay = CFG["layout"]
    dim, txt = col("dim"), col("text")

    try:
        data = {} if "--list-elements" in argv else json.load(sys.stdin)
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
    cost = data.get("cost") or {}
    ms = cost.get("total_duration_ms") or 0
    tpm = (t_in + t_out) / max(ms / 60000.0, 1.0)
    sid = data.get("session_id") or ""
    hist = history(sid, tpm)
    api_ms = cost.get("total_api_duration_ms")
    tps = last_tps(sid, t_out, api_ms) if api_ms else None

    width = max(int(lay["min_width"]), min(term_width() - int(lay["side_margin"]), int(lay["max_width"])))
    inner = width - 4
    label_w = int(lay["label_width"])

    bc = CFG["border"]["chars"]
    bg_ = CFG["border"]["gradient"]

    def gcol(i):
        return fg(gradient_at(i / max(1, width - 1), bg_["from"], bg_["to"], bg_["swap_point"]))

    def gtext(txt_, start):
        return "".join(gcol(start + k) + ch for k, ch in enumerate(txt_)) + R

    # ---- elements: fn(w, o) -> str. w=None asks for the natural size; otherwise the
    # result is stretched/shortened toward `w` (the caller pads/truncates the rest).
    def flag(o, k, default=True):
        return bool(o.get(k, default))

    def bar_element(ic, lab, icon_color, stops, pct, tail, w, o):
        left = ""
        if flag(o, "show_icon"):
            left += icon_color + ic + R + " "
        if flag(o, "show_label"):
            left += dim + str(o.get("label", lab)).ljust(label_w) + R + " "
        if pct is None:
            return left + dim + label("not_available") + R
        bar_w = (int(o.get("bar_width", 12)) if w is None
                 else w - vlen(left) - vlen(tail) - 1)
        if w is not None:
            o["_measured"] = bar_w
            bar_w = o.get("_bar", bar_w)
        return left + pill_bar(pct, max(4, bar_w), stops) + " " + tail

    def usage_el(key, ic, lab, icon_color, d):
        def el(w, o):
            stops = stops_for(key)
            if not d or d.get("used_percentage") is None:
                return bar_element(icon(ic), lab, col(icon_color), stops, None, "", w, o)
            p = d["used_percentage"]
            tail = fg(level_hex(p, stops)) + ("%d%%" % round(p)).rjust(4) + R
            r = until(d.get("resets_at"))
            if r and flag(o, "show_tail"):
                tail += dim + " " + label("resets") + " " + r.ljust(6) + R
            return bar_element(icon(ic), lab, col(icon_color), stops, p, tail, w, o)
        return el

    def el_context(w, o):
        if flag(o, "show_tail"):
            tail = (txt + "%s/%s" % (fmt_tokens(used), fmt_tokens(size)) + R
                    + dim + " (%d%%)" % round(ctx_pct) + R)
            tail = " " * max(0, 18 - vlen(tail)) + tail  # same width as a usage tail
        else:
            tail = fg(level_hex(ctx_pct, stops_for("context"))) + ("%d%%" % round(ctx_pct)).rjust(4) + R
        return bar_element(icon("context"), label("context"), col("context_icon"),
                           stops_for("context"), ctx_pct, tail, w, o)

    def el_dir(w, o):
        text = shown_dir if w is None else tail_cut(shown_dir, max(1, w - 2))
        return col("path") + icon("house") + " " + text + R

    git_cache = []

    def el_git(w, o):
        if not git_cache:
            git_cache.append(git_info(cwd))
        return git_cache[0]

    def el_model(w, o):
        name = icon("model") + " " + model_name
        if effort and flag(o, "show_effort"):
            name += label("effort_separator") + str(effort)
        if w is not None:
            mb = CFG["model_badge"]
            room = w - len(mb["caps"]["left"]) - len(mb["caps"]["right"]) - 2
            name = name[:max(1, room)]
        return gradient_badge(name)

    def el_in(w, o):
        return (col("tokens_in_icon") + icon("tokens_in") + R + dim + " " + label("tokens_in") + " " + R
                + txt + fmt_tokens(t_in) + R)

    def el_out(w, o):
        return (col("tokens_out_icon") + icon("tokens_out") + R + dim + " " + label("tokens_out") + " " + R
                + txt + fmt_tokens(t_out) + R)

    def el_tpm(w, o):
        return (col("throughput") + icon("throughput") + " " + fmt_tokens(tpm) + " "
                + label("throughput_unit") + R)

    def el_tps(w, o):
        return (col("throughput") + icon("throughput") + " "
                + (fmt_tokens(tps) if tps is not None else label("not_available")) + " "
                + label("throughput_unit_sec") + R)

    def el_spark(w, o):
        return sparkline(hist, int(o.get("bar_width", 20)) if w is None else w)

    def el_sid(w, o):
        return col("session_id") + sid + R if sid else ""

    def el_dur(w, o):
        return col("session_duration") + icon("session_duration") + " " + dur(ms) + R if ms else ""

    def el_clock(w, o):
        return col("clock") + icon("clock") + " " + time.strftime(o.get("format", lay["clock_format"])) + R

    def el_cost(w, o):
        c = cost.get("total_cost_usd")
        return col("cost") + icon("cost") + "%.2f" % c + R if c is not None else ""

    def el_lines(w, o):
        a, r = cost.get("total_lines_added"), cost.get("total_lines_removed")
        if a is None and r is None:
            return ""
        return (fg(CFG["colors"]["lines_added"]) + "+%d" % (a or 0) + R + " "
                + fg(CFG["colors"]["lines_removed"]) + "-%d" % (r or 0) + R)

    def el_version(w, o):
        return col("version") + "v" + str(data["version"]) + R if data.get("version") else ""

    def el_text(w, o):
        return fg(o["color"]) + str(o.get("text", "")) + R if o.get("color") else dim + str(o.get("text", "")) + R

    ELEMENTS = {
        "dir": el_dir, "git": el_git, "model": el_model, "context": el_context,
        "five_hour": usage_el("five_hour", "five_hour", label("five_hour"), "five_hour_icon", five),
        "seven_day": usage_el("weekly", "weekly", label("weekly"), "weekly_icon", seven),
        "in_tok": el_in, "out_tok": el_out, "tok_per_min": el_tpm, "tok_per_sec": el_tps, "throughput": el_spark,
        "session_id": el_sid, "session_duration": el_dur, "clock": el_clock,
        "cost": el_cost, "lines": el_lines, "version": el_version, "text": el_text,
    }
    ELEMENTS["weekly"] = ELEMENTS["seven_day"]  # old name

    if "--list-elements" in argv:
        sys.stdout.write("\n".join(ELEMENTS) + "\n")
        return

    DEFAULT_OPTS = {"show_icon": True, "show_label": True, "show_tail": True, "show_effort": True}

    def build_items(items, keep_empty=False):
        """-> [{'o': opts, 'nat': str}] for the items that exist and render something."""
        out = []
        for raw in items or []:
            o = norm_item(raw)
            if not o or o["id"] not in ELEMENTS:
                continue
            o = {**DEFAULT_OPTS, **o}
            try:
                nat = ELEMENTS[o["id"]](None, o)
            except Exception:
                continue
            if vlen(nat) or keep_empty:
                out.append({"o": o, "nat": nat, "fn": ELEMENTS[o["id"]]})
        return out

    # ---- rows
    def equalize(row, cells):
        """equal_bars: render every bar in the row as wide as the narrowest one."""
        if not row.get("equal_bars", lay["equal_bars"]):
            return
        for it, w in cells:
            it["o"].pop("_bar", None)
            it["fn"](w, it["o"])
        ms_ = [it["o"]["_measured"] for it, _ in cells if "_measured" in it["o"]]
        if len(ms_) > 1:
            for it, _ in cells:
                if "_measured" in it["o"]:
                    it["o"]["_bar"] = max(4, min(ms_))

    def compose_grid(row):
        """Grid row: `columns` (1-5) equal/weighted columns; each item takes `span` of them.
        Items fill left to right and wrap onto a new line; `col` (1-based) pins a start column."""
        ncol = max(1, min(5, int(row["columns"])))
        gap = int(row.get("gap", lay["gap"]))
        raw = row.get("items")
        if raw is None:
            raw = [i for g in ("left", "center", "right") for i in row.get(g, [])]
        items = build_items(raw, keep_empty=True)
        if not items:
            return []
        ws = row.get("col_widths") or [1] * ncol
        ws = [max(1, int(x)) for x in list(ws)[:ncol]] + [1] * max(0, ncol - len(ws))
        avail = inner - gap * (ncol - 1)
        cols, acc = [], 0
        for k, wt in enumerate(ws):
            c = avail - acc if k == ncol - 1 else int(avail * wt / sum(ws))
            cols.append(max(1, c))
            acc += cols[-1]
        lines_, cur, pos = [], [], 0  # cur: [(start_col, span, item)]

        def flush():
            nonlocal cur, pos
            if cur:
                lines_.append(cur)
            cur, pos = [], 0
        for it in items:
            span = max(1, min(ncol, int(it["o"].get("span", 1))))
            start = pos
            if it["o"].get("col"):
                start = max(0, min(ncol - span, int(it["o"]["col"]) - 1))
                if start < pos:
                    flush()
                    start = max(0, min(ncol - span, int(it["o"]["col"]) - 1))
            elif start + span > ncol:
                flush()
                start = 0
            cur.append((start, span, it))
            pos = start + span
        flush()
        equalize(row, [(it, sum(cols[st:st + sp]) + gap * (sp - 1)) for ln in lines_ for st, sp, it in ln])
        out_ = []
        for ln in lines_:
            text, at = "", 0  # at: column index already written
            for start, span, it in ln:
                text += (" " * (sum(cols[at:start]) + gap * (start - at)))
                w = sum(cols[start:start + span]) + gap * (span - 1)
                text += fit(it["fn"](w, it["o"]), w, it["o"].get("align", "left"))
                text += " " * gap if start + span < ncol else ""
                at = start + span
            out_.append(fit(text, inner))
        return out_

    def compose_row(row):
        if row.get("columns"):
            return compose_grid(row)
        gap = int(row.get("gap", lay["gap"]))
        groups = [build_items(row.get(g)) for g in ("left", "center", "right")]
        items = [it for g in groups for it in g]
        if not items:
            return []
        n_gaps = (len(items) - 1) * gap
        kinds = []
        for it in items:
            kind, val = parse_width(it["o"], inner)
            if kind == "auto":
                kind, val = "fixed", vlen(it["nat"])
            kinds.append([kind, val])
        flex_ix = [i for i, k in enumerate(kinds) if k[0] == "flex"]
        fixed = sum(k[1] for k in kinds if k[0] == "fixed")
        left_over = inner - fixed - n_gaps
        if flex_ix:
            weights = [max(1, int(items[i]["o"].get("weight", 1))) for i in flex_ix]
            tot, given = sum(weights), 0
            for j, i in enumerate(flex_ix):
                share = (left_over - given if j == len(flex_ix) - 1
                         else int(left_over * weights[j] / tot))
                share = max(4, share)
                kinds[i][1] = share
                given += share
        equalize(row, [(it, k[1]) for it, k in zip(items, kinds)])
        rendered = []
        for it, (_, w) in zip(items, kinds):
            align = it["o"].get("align", "left")
            rendered.append(fit(it["fn"](w, it["o"]), w, align))

        gs, k = [], 0
        for g in groups:
            gs.append((" " * gap).join(rendered[k:k + len(g)]))
            k += len(g)
        if flex_ix:
            line_ = (" " * gap).join(s for s, g in zip(gs, groups) if g)
        else:
            lw, cw_, rw = (vlen(s) for s in gs)
            line_ = gs[0]
            if groups[1]:
                start = max(lw + (gap if groups[0] else 0), (inner - cw_) // 2)
                start = min(start, inner - rw - (gap if groups[2] else 0) - cw_)
                line_ = fit(line_, max(start, lw), "left") + gs[1]
            if groups[2]:
                line_ = fit(line_, inner - rw, "left") + gs[2]
        return [fit(line_, inner)]

    def boxed(content):
        return gcol(0) + bc["vertical"] + " " + R + content + gcol(width - 1) + " " + bc["vertical"] + R

    def sep():
        return gtext(bc["tee_left"] + bc["horizontal"] * (width - 2) + bc["tee_right"], 0)

    # ---- top / bottom border bars
    def border(side, left_c, right_c):
        spec = lay.get(side) or {}
        g = int(lay["border_gap"])
        segs = []
        for name in ("left", "center", "right"):
            items = build_items(spec.get(name))
            if items:
                body = (" " * g).join(it["nat"] for it in items)
                segs.append((name, " " + truncate(body, width - 6) + " "))
        placed = []
        for name, s in segs:
            if name == "left":
                start = 2
            elif name == "right":
                start = width - 2 - vlen(s)
            else:
                start = (width - vlen(s)) // 2
            placed.append((max(2, start), s))
        out, pos = gtext(left_c + "", 0), 1
        for start, s in sorted(placed):
            if start < pos:
                continue  # overlaps an earlier group
            out += gtext(bc["horizontal"] * (start - pos), pos) + s
            pos = start + vlen(s)
        return out + gtext(bc["horizontal"] * max(0, width - 1 - pos) + right_c, pos)

    out = [border("top", bc["top_left"], bc["top_right"])]
    first = True
    for raw in lay["rows"]:
        row = norm_row(raw)
        content = compose_row(row)
        if not content:
            continue
        if not first and row.get("divider", lay["row_dividers"]):
            out.append(sep())
        out.extend(boxed(c) for c in content)
        first = False
    out.append(border("bottom", bc["bottom_left"], bc["bottom_right"]))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
