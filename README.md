# claudemaxxing

Personal Claude Code configuration: custom skills, slash commands, plugin list, and settings, installed into `~/.claude/` via symlinks.

## What's here

- `install.sh` — bootstrap script. Installs `uv`/`graphify`/`plannotator` CLIs if missing, adds the `plannotator` plugin marketplace, installs every plugin listed in `claude_plugins`, and symlinks every file/directory listed in `claude_links` into place under `~`.
- `claude_links` — `<source> <destination>` pairs; the single source of truth for what this repo installs and where.
- `claude_plugins` — list of `<plugin>@<marketplace>` entries installed via `claude plugin install`.
- `commands/` — custom slash commands (`/claudify-project`, `/update-claudification`).
- `skills/` — custom skills (`graphify`, `find-skills`, the `plannotator-*` family).
- `misc/` — files linked directly to `~/.claude/`: global `CLAUDE.md`, `settings.json`, and the statusline script.

## Install

```bash
./install.sh
```

Requires `curl` and `git`, and the `claude` CLI to already be installed. The script is idempotent — safe to re-run after pulling changes to relink or pick up newly added plugins.

## Adding a new skill or command

1. Add the files under `skills/<name>/` or `commands/<name>.md`.
2. Add the corresponding `<source> <destination>` line to `claude_links` so `install.sh` actually links it into `~/.claude/`.
3. Re-run `./install.sh` (or symlink it manually) to pick it up immediately.

See `CLAUDE.md` for more detail on the repo's architecture.
