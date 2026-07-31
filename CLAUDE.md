# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is a personal Claude Code configuration repo ("claudemaxxing"). It is not an application — there is no build, lint, or test suite. It defines custom skills, slash commands, plugin selections, and settings that get **symlinked** into `~/.claude/` on the machine that installs it.

## Repo layout

- `install.sh` — bootstrap script. Ensures `curl`/`git`/`claude` are present, installs `uv` + the `graphify` CLI and the `plannotator` CLI if missing, adds the `plannotator` marketplace, installs every plugin listed in `claude_plugins`, then symlinks every pair listed in `claude_links`.
- `claude_links` — table of `<source path in this repo> <destination path under ~>` pairs (space-separated). `install.sh` reads this line by line and calls `ln -sf` for each, creating parent dirs as needed. **This is the single source of truth for what gets linked where** — when adding a new skill/command/misc file that should be installed, add a row here too, or it will exist in the repo but never reach `~/.claude`.
- `claude_plugins` — flat list of `<plugin>@<marketplace>` entries installed via `claude plugin install` in `install.sh`.
- `commands/` — custom slash commands (`claudify-project.md`, `update-claudification.md`, `go-contained.md`), linked individually into `~/.claude/commands/`.
- `skills/` — custom skills, each linked as a whole directory into `~/.claude/skills/<name>/`. Skills follow the standard `SKILL.md` frontmatter format (`name`, `description`) that Claude Code's skill discovery scans.
- `misc/` — files linked directly to `~/.claude/` (`CLAUDE.md` = global user instructions, `settings.json` = global settings, `statusline-command.sh`, `contained-handoff-hook.sh`).
- `contained-claude/` — git submodule (`XenonIsAwesome/claude-container-sandbox`), *not* symlinked into `~/.claude`. It stays checked out at its real path inside this repo; see "Contained sessions" below.

## Working in this repo

- Editing a file under `skills/`, `commands/`, or `misc/` changes the *source of truth*; because these are symlinked, changes take effect on the installing machine immediately (no reinstall/rebuild step) once `install.sh` has been run at least once.
- When adding a brand-new skill or command directory, remember to append the corresponding line to `claude_links` — this is easy to forget since the skill/command will still be discoverable *inside this repo* but silently absent from `~/.claude`.
- `misc/CLAUDE.md` is the global (all-projects) instruction file installed to `~/.claude/CLAUDE.md` — it is distinct from this file, which only applies within this repo. Keep global, cross-project behavior (subagent model defaults, graphify trigger wiring, etc.) there, not here.

## The `claudify-project` / `update-claudification` commands

Two of the custom commands in `commands/` are meta-tools for *other* repositories, not for this one:

- `/claudify-project [branch-name]` — onboards an arbitrary target project onto graphify + an AI coding agent: creates a new branch, builds a graphify knowledge graph (`graphify-out/`), runs `graphify benchmark`, gitignores graphify's machine-local files, wires a `## graphify` section into a fresh `CLAUDE.md` via `graphify claude install`, runs `/init` to fill out the rest (preserving the graphify section), generalizes Claude-specific phrasing, then renames the result to `AGENTS.md` with `CLAUDE.md` symlinked to it. Produces two commits.
- `/update-claudification [branch-name]` — refreshes a project previously set up by `/claudify-project`: re-extracts the graph incrementally (`--update`), regenerates the benchmark report, verifies/restores the `## graphify` wiring, refreshes `AGENTS.md` via `/init`, and commits only what actually changed.

Both are written as strict, ordered, stop-on-failure runbooks (verify tools → verify clean git state → confirm branch → do the work → commit) — if extending them, preserve that structure rather than collapsing steps.

## Contained sessions (`contained-claude` submodule + `/go-contained`)

`contained-claude` (submodule, separate repo/remote) runs Claude Code in an
isolated Docker container via `contained-claude/sandbox.sh`. Because
`sandbox.sh` mounts the real project path and the real `~/.claude`, a
container started with `sandbox.sh -r <session-id>` resumes the exact same
transcript a native session was using — same project, same skills/settings.

A running Claude Code session cannot hijack its own terminal to spawn and
attach an interactive `docker run -it` container mid-turn (a tool call is a
subprocess of the harness, not a replacement for it), so "moving" a session
into the sandbox is a two-part handoff rather than one atomic action:

1. **`/go-contained`** (`commands/go-contained.md`) — run from inside a
   native session. Writes `$CLAUDE_CODE_SESSION_ID`, `$PWD`, `$CLAUDE_PID`,
   and a timestamp to a handoff file named after the terminal's `tty`
   (`~/.claude/.contained-handoff.<tty>`, so concurrent handoffs in other
   terminals don't collide), tells the user, then `kill`s `$CLAUDE_PID` to
   end that session — checking the kill's exit status rather than assuming
   it worked.
2. **`misc/contained-handoff-hook.sh`** — sourced from `~/.bashrc` by
   `install.sh`. A `PROMPT_COMMAND` hook (array- and scalar-safe, so it
   doesn't clobber other tools' hooks) that fires on the next shell prompt
   *in that same terminal*, finds that terminal's handoff file, discards it
   if stale (>1h) or if `$CLAUDE_PID` is still alive (avoids a double-resume
   race if the kill silently failed), and otherwise runs
   `$CLAUDE_SANDBOX_SCRIPT -r <session-id>` from the saved directory —
   resuming that same session inside the container.

This mechanism is **bash-and-`~/.bashrc`-only**: it silently does nothing on
zsh/fish, or any shell setup that doesn't source `~/.bashrc` per interactive
shell. There is currently no error surfaced when this happens — the native
session just ends and nothing resumes it.

`CLAUDE_SANDBOX_SCRIPT` is exported by `install.sh` to this checkout's
`contained-claude/sandbox.sh` (an absolute path resolved at install time).
`install.sh` also adds a `contained-claude` alias to `~/.bashrc` (expanding to
`$CLAUDE_SANDBOX_SCRIPT` at invocation time) so `sandbox.sh` can be called
directly by name — e.g. `contained-claude -r <session-id>` — without needing
the full path, for starting a sandbox outside of the `/go-contained` handoff
flow. `install.sh` also runs `git submodule update --init` automatically if
`contained-claude/sandbox.sh` is missing (e.g. after a plain `git pull` on an
existing checkout), and upserts (not just appends) both the
`CLAUDE_SANDBOX_SCRIPT` export and the `contained-claude` alias in `~/.bashrc`
by exact-line match, so re-running `install.sh` after moving/re-cloning the
repo actually replaces the stale path instead of leaving it in place.

The Docker image must use `ENTRYPOINT` (not `CMD`) for `claude` — `sandbox.sh`
forwards args like `-r <session-id>` after the image name, and without an
`ENTRYPOINT`, `docker run image <args>` replaces `CMD` outright instead of
passing those args through. This was fixed upstream in
`claude-container-sandbox`; if that submodule is ever bumped to a commit that
regresses this, `/go-contained`'s resume step will silently fail to forward
`-r`.

## Settings notes (`misc/settings.json`)

- `permissions.defaultMode: "acceptEdits"` and `skipDangerousModePermissionPrompt: true` are set globally — this machine's Claude Code is configured to prompt less than default. Be mindful of this when reasoning about what "the user would be prompted for" versus what silently proceeds.
- `enabledPlugins` / `extraKnownMarketplaces` here must stay in sync with `claude_plugins` at the repo root; they are two representations of the same installed-plugin set (one for `install.sh`'s `claude plugin install` loop, one for the settings file itself).
