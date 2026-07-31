# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is a personal Claude Code configuration repo ("claudemaxxing"). It is not an application — there is no build, lint, or test suite. It defines custom skills, slash commands, plugin selections, and settings that get **symlinked** into `~/.claude/` on the machine that installs it.

## Repo layout

- `install.sh` — bootstrap script. Ensures `curl`/`git`/`claude` are present, installs `uv` + the `graphify` CLI and the `plannotator` CLI if missing, adds the `plannotator` marketplace, installs every plugin listed in `claude_plugins`, then symlinks every pair listed in `claude_links`.
- `claude_links` — table of `<source path in this repo> <destination path under ~>` pairs (space-separated). `install.sh` reads this line by line and calls `ln -sf` for each, creating parent dirs as needed. **This is the single source of truth for what gets linked where** — when adding a new skill/command/misc file that should be installed, add a row here too, or it will exist in the repo but never reach `~/.claude`.
- `claude_plugins` — flat list of `<plugin>@<marketplace>` entries installed via `claude plugin install` in `install.sh`.
- `commands/` — custom slash commands (`claudify-project.md`, `update-claudification.md`), linked individually into `~/.claude/commands/`.
- `skills/` — custom skills, each linked as a whole directory into `~/.claude/skills/<name>/`. Skills follow the standard `SKILL.md` frontmatter format (`name`, `description`) that Claude Code's skill discovery scans.
- `misc/` — files linked directly to `~/.claude/` (`CLAUDE.md` = global user instructions, `settings.json` = global settings, `statusline-command.sh`).

## Working in this repo

- Editing a file under `skills/`, `commands/`, or `misc/` changes the *source of truth*; because these are symlinked, changes take effect on the installing machine immediately (no reinstall/rebuild step) once `install.sh` has been run at least once.
- When adding a brand-new skill or command directory, remember to append the corresponding line to `claude_links` — this is easy to forget since the skill/command will still be discoverable *inside this repo* but silently absent from `~/.claude`.
- `misc/CLAUDE.md` is the global (all-projects) instruction file installed to `~/.claude/CLAUDE.md` — it is distinct from this file, which only applies within this repo. Keep global, cross-project behavior (subagent model defaults, graphify trigger wiring, etc.) there, not here.

## The `claudify-project` / `update-claudification` commands

Two of the custom commands in `commands/` are meta-tools for *other* repositories, not for this one:

- `/claudify-project [branch-name]` — onboards an arbitrary target project onto graphify + an AI coding agent: creates a new branch, builds a graphify knowledge graph (`graphify-out/`), runs `graphify benchmark`, gitignores graphify's machine-local files, wires a `## graphify` section into a fresh `CLAUDE.md` via `graphify claude install`, runs `/init` to fill out the rest (preserving the graphify section), generalizes Claude-specific phrasing, then renames the result to `AGENTS.md` with `CLAUDE.md` symlinked to it. Produces two commits.
- `/update-claudification [branch-name]` — refreshes a project previously set up by `/claudify-project`: re-extracts the graph incrementally (`--update`), regenerates the benchmark report, verifies/restores the `## graphify` wiring, refreshes `AGENTS.md` via `/init`, and commits only what actually changed.

Both are written as strict, ordered, stop-on-failure runbooks (verify tools → verify clean git state → confirm branch → do the work → commit) — if extending them, preserve that structure rather than collapsing steps.

## Settings notes (`misc/settings.json`)

- `permissions.defaultMode: "acceptEdits"` and `skipDangerousModePermissionPrompt: true` are set globally — this machine's Claude Code is configured to prompt less than default. Be mindful of this when reasoning about what "the user would be prompted for" versus what silently proceeds.
- `enabledPlugins` / `extraKnownMarketplaces` here must stay in sync with `claude_plugins` at the repo root; they are two representations of the same installed-plugin set (one for `install.sh`'s `claude plugin install` loop, one for the settings file itself).
