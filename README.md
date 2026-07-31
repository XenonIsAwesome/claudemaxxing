# claudemaxxing

Personal Claude Code configuration: custom skills, slash commands, plugin list, and settings, installed into `~/.claude/` via symlinks.

## What's here

- `install.sh` — bootstrap script. Installs `uv`/`graphify`/`plannotator` CLIs if missing, adds the `plannotator` plugin marketplace, installs every plugin listed in `claude_plugins`, and symlinks every file/directory listed in `claude_links` into place under `~`.
- `claude_links` — `<source> <destination>` pairs; the single source of truth for what this repo installs and where.
- `claude_plugins` — list of `<plugin>@<marketplace>` entries installed via `claude plugin install`.
- `commands/` — custom slash commands (`/claudify-project`, `/update-claudification`, `/go-contained`).
- `skills/` — custom skills (`graphify`, `find-skills`, the `plannotator-*` family).
- `misc/` — files linked directly to `~/.claude/`: global `CLAUDE.md`, `settings.json`, the statusline script, and the contained-session handoff hook.
- `contained-claude/` — git submodule ([`claude-container-sandbox`](https://github.com/XenonIsAwesome/claude-container-sandbox)) that runs Claude Code in an isolated Docker container. See below.

## Install

```bash
git clone --recurse-submodules git@github.com:XenonIsAwesome/claudemaxxing.git
./install.sh
```

(If you already cloned without `--recurse-submodules`, run `git submodule update --init` first.)

Requires `curl` and `git`, and the `claude` CLI to already be installed. The script is idempotent — safe to re-run after pulling changes to relink, pick up newly added plugins, or refresh the `CLAUDE_SANDBOX_SCRIPT` path (see below) after moving this checkout.

## Contained sessions

`contained-claude` runs Claude Code inside an isolated Docker sandbox (own network/filesystem, `--dangerously-skip-permissions`), while still sharing your real `~/.claude` config and mounting the current project at its real path — so session history lines up between native and sandboxed runs.

From a normal (native) Claude Code session, run `/go-contained` to hand off: it saves the current session id, ends the session, and — thanks to a hook `install.sh` wires into `~/.bashrc` — the very next shell prompt in that same terminal automatically launches `contained-claude/sandbox.sh -r <session-id>`, resuming that exact conversation inside the container.

You can also run the sandbox directly without going through `/go-contained`:

```bash
cd <your-project>
~/.claudemaxxing/contained-claude/sandbox.sh          # start a fresh sandboxed session
~/.claudemaxxing/contained-claude/sandbox.sh -r <id>  # resume a specific session
```

## Adding a new skill or command

1. Add the files under `skills/<name>/` or `commands/<name>.md`.
2. Add the corresponding `<source> <destination>` line to `claude_links` so `install.sh` actually links it into `~/.claude/`.
3. Re-run `./install.sh` (or symlink it manually) to pick it up immediately.

See `CLAUDE.md` for more detail on the repo's architecture.
