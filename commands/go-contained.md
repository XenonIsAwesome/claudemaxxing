---
description: Hand off the current session to contained-claude, resuming the exact same conversation inside an isolated Docker sandbox.
---

# /go-contained

Ends the current (native, unsandboxed) Claude Code session and hands it off to
`contained-claude` (the `claude-container-sandbox` project, vendored as the
`contained-claude` git submodule in `claudemaxxing`). Because `sandbox.sh`
mounts the real project path and the real `~/.claude`, resuming with `-r
<session-id>` inside the container picks up this exact conversation where it
left off — same transcript, same project, same skills/settings.

Follow these steps **in order**. Do not skip steps. Stop and tell the user if
any check fails instead of pushing through — do not fall back to guessing a
path or silently doing nothing.

## Step 1 - Refuse to run if already inside a container

```bash
test -f /.dockerenv && echo ALREADY_CONTAINED || echo NOT_CONTAINED
```

If `ALREADY_CONTAINED`: stop. Tell the user this session is already running
inside contained-claude, so there's nothing to hand off — `/go-contained`
only makes sense from a native (host) session.

## Step 2 - Verify the environment this command depends on

```bash
echo "session=$CLAUDE_CODE_SESSION_ID pid=$CLAUDE_PID sandbox=$CLAUDE_SANDBOX_SCRIPT"
[ -n "$CLAUDE_CODE_SESSION_ID" ] && [ -n "$CLAUDE_PID" ] || echo MISSING_SESSION_VARS
[ -n "$CLAUDE_SANDBOX_SCRIPT" ] && [ -x "$CLAUDE_SANDBOX_SCRIPT" ] || echo MISSING_SANDBOX_SCRIPT
command -v docker >/dev/null 2>&1 || echo MISSING_DOCKER
```

- If `MISSING_SESSION_VARS`: stop. This shouldn't happen in a normal native
  Claude Code session — tell the user something is off with their
  environment and not to proceed.
- If `MISSING_SANDBOX_SCRIPT`: stop. Tell the user `CLAUDE_SANDBOX_SCRIPT` is
  not set to an executable path — it's exported by `claudemaxxing`'s
  `install.sh` into `~/.bashrc`, so this usually means `install.sh` hasn't
  been (re-)run since `contained-claude` was added, or they're not in a bash
  shell that sourced `~/.bashrc`. Do not guess a path yourself.
- If `MISSING_DOCKER`: stop. Tell the user Docker is required and not found
  on PATH.
- If none of the above print: continue.

## Step 3 - Write the handoff file

The sandbox needs to be launched from the project directory (so `sandbox.sh`
mounts the right path), needs to know which session to resume, and the hook
needs the PID + a timestamp to guard against a double-resume race and stale
handoffs. The file is named per-terminal (by `tty`) so concurrent
`/go-contained` invocations in different terminals don't clobber each other.

```bash
TTY_ID=$(tty 2>/dev/null | tr -c 'A-Za-z0-9' '_')
HANDOFF_FILE="$HOME/.claude/.contained-handoff.$TTY_ID"
printf '%s\n%s\n%s\n%s\n' "$CLAUDE_CODE_SESSION_ID" "$PWD" "$CLAUDE_PID" "$(date +%s)" > "$HANDOFF_FILE"
cat "$HANDOFF_FILE"
```

Confirm the file now contains exactly four lines: the session id, the
current project directory, `$CLAUDE_PID`, and a unix timestamp.

## Step 4 - Tell the user what's about to happen

Before doing anything irreversible, tell the user clearly, in your own
words, something like:

> Handing off to contained-claude. This session is ending now — it will
> resume automatically inside the sandbox on your next shell prompt, in this
> same terminal.

## Step 5 - End the current session

```bash
kill "$CLAUDE_PID" || echo "KILL_FAILED"
```

This is the intended effect of `/go-contained` — the user invoked this
command specifically to end the native session and continue in the sandbox,
so no further confirmation is needed beyond Step 4's notice.

If `KILL_FAILED` prints: tell the user the session could not be ended and
the handoff will **not** happen automatically — do not claim the handoff is
in progress. (The hook itself also refuses to resume while `$CLAUDE_PID` is
still alive, so a failed kill fails safe rather than double-resuming.)

Otherwise, after this runs, the parent `claude` process exits; the
`contained-handoff-hook.sh` hook sourced from `~/.bashrc` detects the
handoff file for this terminal's `tty` on the next prompt, confirms
`$CLAUDE_PID` has actually exited, and runs `contained-claude`'s
`sandbox.sh -r <session-id>` from the saved directory — resuming this
conversation inside the container. This requires the terminal's shell to be
bash with `~/.bashrc` sourced; it silently won't happen otherwise (see
CLAUDE.md's "Contained sessions" section).
