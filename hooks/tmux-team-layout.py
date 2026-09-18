#!/usr/bin/env python3
"""
Re-lays-out the current tmux window whenever the Claude Code agent-team
roster changes: lead/main pane as a full-width bar at the TOP, teammate
panes tiled in a grid below it (wrapping to more rows as the team grows).

Only ever resizes/repositions EXISTING panes via `tmux select-layout` with
a hand-built custom layout string -- never kills/recreates panes, since
each teammate pane hosts a live running process.

Always exits 0. Never prints to stdout on the success/no-op path (this is
a PostToolUse/SessionStart hook; stdout should stay quiet). Diagnostics
only go to LOG_PATH.

See: /home/xenon/.claude/plans/linked-wandering-catmull.md
"""

import fcntl
import json
import math
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
HOOKS_DIR = os.path.join(HOME, ".claude", "hooks")
TEAMS_DIR = os.path.join(HOME, ".claude", "teams")
LOCK_PATH = os.path.join(HOOKS_DIR, ".tmux-team-layout.lock")
LOG_PATH = os.path.join(HOOKS_DIR, ".tmux-team-layout.log")

# --- tunables -----------------------------------------------------------
TOP_FRACTION = 0.5       # main/lead bar height as a fraction of window height
TOP_MIN_LINES = 7
TOP_MAX_LINES = 20
MIN_PANE_WIDTH = 50        # wrap threshold: columns
MIN_PANE_HEIGHT = 15       # target only, not force-enforced for large N
HARD_MIN_COL_WIDTH = 20    # never shrink columns narrower than this


_log_truncated = False


def log(msg):
    global _log_truncated
    try:
        mode = "w" if not _log_truncated else "a"
        with open(LOG_PATH, mode) as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")
        _log_truncated = True
    except Exception:
        pass


def tmux(*args):
    return subprocess.run(
        ["tmux", *args], capture_output=True, text=True, timeout=5
    )


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def checksum(desc: str) -> str:
    csum = 0
    for c in desc:
        csum = ((csum >> 1) | ((csum & 1) << 15))
        csum = (csum + ord(c)) & 0xFFFF
    return format(csum, "04x")


def leaf(w, h, x, y, pane_index):
    return f"{w}x{h},{x},{y},{pane_index}"


def split_node(w, h, x, y, bracket_open, bracket_close, children):
    """A non-leaf node: area directly followed by its bracket (no comma)."""
    return f"{w}x{h},{x},{y}{bracket_open}{','.join(children)}{bracket_close}"


def build_layout(window_w, window_h, lead_idx, teammate_indices):
    """Returns the full 'checksum,description' layout string, or None if
    there's nothing meaningful to lay out."""
    n = len(teammate_indices)
    if n == 0:
        return None

    top_h = clamp(round(window_h * TOP_FRACTION), TOP_MIN_LINES, TOP_MAX_LINES)
    top_h = min(top_h, window_h - 2)
    if top_h < 1 or window_h - top_h - 1 < 1:
        log(f"window too small to reflow ({window_w}x{window_h}), skipping")
        return None

    columns = max(1, window_w // MIN_PANE_WIDTH)
    columns = min(columns, n)
    while columns > 1:
        col_w = (window_w - (columns - 1)) // columns
        if col_w >= HARD_MIN_COL_WIDTH:
            break
        columns -= 1
    rows = math.ceil(n / columns)

    grid_h = window_h - top_h - 1
    available_v = grid_h - (rows - 1)
    base_row_h, rem_v = divmod(available_v, rows)
    row_heights = [base_row_h + (1 if i < rem_v else 0) for i in range(rows)]

    # partition teammate_indices into rows
    rows_of_panes = []
    it = iter(teammate_indices)
    remaining = n
    for r in range(rows):
        # every row but the last takes a full `columns` panes; the last
        # row takes whatever remains (may be fewer than `columns`)
        k = columns if r < rows - 1 else remaining
        row_panes = [next(it) for _ in range(k)]
        rows_of_panes.append(row_panes)
        remaining -= k

    root_top_leaf = leaf(window_w, top_h, 0, 0, lead_idx)

    row_nodes = []
    y = top_h + 1
    for row_panes in rows_of_panes:
        h = row_heights.pop(0) if row_heights else base_row_h
        k = len(row_panes)
        available_h = window_w - (k - 1)
        base_w, rem_h = divmod(available_h, k)
        widths = [base_w + (1 if j < rem_h else 0) for j in range(k)]
        x = 0
        pane_leaves = []
        for j, pidx in enumerate(row_panes):
            w = widths[j]
            pane_leaves.append(leaf(w, h, x, y, pidx))
            x += w + 1
        if k == 1:
            row_nodes.append(pane_leaves[0])
        else:
            row_nodes.append(split_node(window_w, h, 0, y, "{", "}", pane_leaves))
        y += h + 1

    root_area = f"{window_w}x{window_h},0,0"
    desc = f"{root_area}[{root_top_leaf},{','.join(row_nodes)}]"
    return f"{checksum(desc)},{desc}"


def main():
    # --- fast no-op preconditions ---------------------------------------
    if not os.environ.get("TMUX"):
        return
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        log("TMUX set but TMUX_PANE missing, skipping")
        return

    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except Exception:
        payload = {}
    session_id = payload.get("session_id", "")
    if not session_id:
        log("no session_id in hook payload, skipping")
        return

    team_dir = os.path.join(TEAMS_DIR, f"session-{session_id[:8]}")
    config_path = os.path.join(team_dir, "config.json")
    if not os.path.isfile(config_path):
        return  # no team for this session -- normal, nothing to do

    try:
        with open(config_path) as f:
            config = json.load(f)
    except Exception:
        log(f"failed to parse {config_path}, skipping")
        return

    members = config.get("members", [])
    teammates = [
        m for m in members
        if m.get("backendType") == "tmux" and m.get("tmuxPaneId") != "leader"
    ]
    teammates.sort(key=lambda m: m.get("joinedAt", 0))
    if not teammates:
        return

    # resolve the lead's window from its own pane
    r = tmux("display-message", "-p", "-t", tmux_pane,
              "#{session_name}:#{window_index}\t#{window_width}\t#{window_height}")
    if r.returncode != 0 or not r.stdout.strip():
        log(f"display-message failed: {r.stderr.strip()}")
        return
    win_target, w_str, h_str = r.stdout.strip().split("\t")
    window_w, window_h = int(w_str), int(h_str)

    r = tmux("list-panes", "-t", win_target, "-F", "#{pane_id}\t#{pane_index}")
    if r.returncode != 0:
        log(f"list-panes failed: {r.stderr.strip()}")
        return
    id_to_index = {}
    for line in r.stdout.splitlines():
        if "\t" not in line:
            continue
        pid, pidx = line.split("\t")
        id_to_index[pid] = int(pidx)

    if tmux_pane not in id_to_index:
        log(f"lead pane {tmux_pane} not found in window {win_target}, skipping")
        return
    lead_idx = id_to_index[tmux_pane]

    teammate_indices = []
    for m in teammates:
        pid = m.get("tmuxPaneId")
        if pid in id_to_index:
            teammate_indices.append(id_to_index[pid])
        else:
            log(f"stale tmuxPaneId {pid} for {m.get('name')}, dropping")

    if not teammate_indices:
        return

    layout = build_layout(window_w, window_h, lead_idx, teammate_indices)
    if not layout:
        return

    r = tmux("select-layout", "-t", tmux_pane, layout)
    if r.returncode != 0:
        log(f"select-layout failed: {r.stderr.strip()} layout={layout}")
        return
    log(f"applied layout for {len(teammate_indices)} teammate(s): {layout}")

    # Suppress the lead pane's border-status label (it's redundant/glitchy for
    # a full-width top bar) while keeping teammate panes labeled with their
    # index+title. NOTE: comparing #{pane_id} inside #{==:...} is unreliable
    # in tmux 3.4 -- the leading '%' in pane_id trips up the comparator and
    # it always evaluates false -- so compare #{pane_index} (a plain integer)
    # instead, which works correctly.
    border_format = (
        f"#{{?#{{==:#{{pane_index}},{lead_idx}}},,"
        f"#{{?pane_active,#[reverse],}}#{{pane_index}}#[default] \"#{{pane_title}}\"}}"
    )
    r = tmux("set-option", "-t", win_target, "pane-border-format", border_format)
    if r.returncode != 0:
        log(f"set-option pane-border-format failed: {r.stderr.strip()}")


if __name__ == "__main__":
    try:
        os.makedirs(HOOKS_DIR, exist_ok=True)
        lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            sys.exit(0)  # another invocation is mid-run; next trigger reconciles
        try:
            main()
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
    except Exception:
        try:
            log("unhandled exception:\n" + traceback.format_exc())
        except Exception:
            pass
    sys.exit(0)
