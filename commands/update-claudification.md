---
description: Refresh an already-claudified project's graphify knowledge graph, benchmark report, and AGENTS.md, then commit the changes into the tree
argument-hint: [branch-name]
---

# /update-claudification

Refresh a project that was previously bootstrapped by `/claudify-project`: re-extract the graphify knowledge graph, regenerate the benchmark report, confirm the `## graphify` wiring in `AGENTS.md`/`CLAUDE.md` is intact, refresh the rest of the documentation to match the current codebase, and commit the results directly into the tree. Unlike `/claudify-project`, this does **not** bootstrap a new setup from scratch — it expects one to already exist.

Follow these steps **in order**. Do not skip steps. Stop and tell the user if any step fails instead of pushing through.

## Step 1 - Verify required tools are installed

```bash
MISSING_TOOLS=""
command -v git >/dev/null 2>&1 || MISSING_TOOLS="$MISSING_TOOLS git"
command -v graphify >/dev/null 2>&1 || MISSING_TOOLS="$MISSING_TOOLS graphify"
echo "Missing:$MISSING_TOOLS"
```

- If nothing is missing: continue to Step 2.
- If `git` is missing: tell the user `git` is required and ask whether they want to install it now. If they decline, or it's still missing afterward, **stop and abort**.
- If `graphify` is missing: tell the user the `graphify` CLI is required and ask whether they want to install it now:
  ```bash
  command -v uv >/dev/null 2>&1 && uv tool install graphifyy || pip install graphifyy
  ```
  If they decline, or it's still missing afterward, **stop and abort**.

## Step 2 - Verify the project is already claudified

```bash
git rev-parse --is-inside-work-tree 2>/dev/null || echo "NOT_A_REPO"
test -f AGENTS.md && echo "AGENTS_OK" || echo "AGENTS_MISSING"
test -L CLAUDE.md && [ "$(readlink CLAUDE.md)" = "AGENTS.md" ] && echo "SYMLINK_OK" || echo "SYMLINK_MISSING"
test -f graphify-out/graph.json && echo "GRAPH_OK" || echo "GRAPH_MISSING"
```

- If `NOT_A_REPO` prints: stop and tell the user this isn't a git repository.
- If any of `AGENTS_MISSING`, `SYMLINK_MISSING`, or `GRAPH_MISSING` prints: stop. Tell the user this project doesn't look like it was set up with `/claudify-project` yet, and suggest running that command instead. Do not try to patch a partial setup here.
- If all checks pass: continue.

## Step 3 - Verify git status allows an in-place update

```bash
git status --porcelain
```

- If this prints anything (uncommitted changes, staged changes, or untracked files): stop. Show the user what's dirty and ask whether to commit, stash (`git stash -u`), or abort. Do **not** silently fold unrelated pre-existing changes into this command's commit(s).
- If the tree is clean: continue.

## Step 4 - Confirm the branch

```bash
git symbolic-ref --short HEAD
```

- If `$1` (an argument) was given: treat it as a branch to create and switch to before updating, same as `/claudify-project` does — `git checkout -b <branch-name>` (or ask to reuse/rename/abort if it already exists).
- If no argument was given: stay on the current branch. Show the user which branch that is and confirm it's where they want the update committed before continuing.

## Step 5 - Re-extract the graphify knowledge graph

Invoke the `graphify` skill with path `.` and the `--update` flag (equivalent to running `/graphify . --update`) so only new/changed files are re-extracted rather than rebuilding from scratch. Let the full pipeline run to completion.

## Step 6 - Re-run the graphify benchmark and overwrite the report

```bash
mkdir -p graphify-out
{
  echo "# Graphify Benchmark Report"
  echo
  echo "Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
  echo
  echo '```'
  graphify benchmark
  echo '```'
} > graphify-out/BENCHMARK_REPORT.md
cat graphify-out/BENCHMARK_REPORT.md
```

Show the refreshed benchmark results to the user.

## Step 7 - Confirm gitignore entries for graphify's machine-local files are still present

```bash
touch .gitignore
grep -qxF '# graphify: machine-local state, not portable across checkouts' .gitignore || echo '# graphify: machine-local state, not portable across checkouts' >> .gitignore
grep -qxF 'graphify-out/.graphify_python' .gitignore || echo 'graphify-out/.graphify_python' >> .gitignore
grep -qxF 'graphify-out/.graphify_root' .gitignore || echo 'graphify-out/.graphify_root' >> .gitignore
grep -qxF 'graphify-out/cost.json' .gitignore || echo 'graphify-out/cost.json' >> .gitignore
```

## Step 8 - Commit the refreshed graph, benchmark report, and gitignore

```bash
git add graphify-out .gitignore
git status --short
```

If `git status --short` shows nothing staged, skip the commit (the graph and benchmark didn't change) and say so. Otherwise:

```bash
git commit -m "Update graphify knowledge graph and benchmark report"
```

Review the staged files first to make sure nothing unintended is included.

## Step 9 - Confirm the `## graphify` wiring is still intact

```bash
grep -n "## graphify" AGENTS.md
```

- If the section is present: nothing to do here, continue to Step 10.
- If it's missing (unexpected drift): run `graphify claude install` to restore it, then re-run the grep to confirm it landed. Note for the user that the wiring had gone missing and was restored.

## Step 10 - Refresh the rest of AGENTS.md to match the current codebase

Invoke the `init` skill (equivalent to running `/init`) targeting `CLAUDE.md`. Since `CLAUDE.md` is a symlink to `AGENTS.md`, a normal file write follows the symlink and updates `AGENTS.md`'s contents in place while leaving the symlink itself untouched — instruct the step to **preserve the existing `## graphify` section verbatim** rather than overwriting or removing it, same as `/claudify-project` does on first generation.

After it runs:

```bash
ls -la CLAUDE.md
grep -n "## graphify" AGENTS.md
```

- Confirm `CLAUDE.md` still shows as a symlink pointing to `AGENTS.md`. If the write broke the symlink (`CLAUDE.md` became a regular file), restore it: move the regenerated content back into `AGENTS.md` and re-link (`ln -sf AGENTS.md CLAUDE.md`).
- Confirm the `## graphify` section is still present.

## Step 11 - Generalize any newly introduced Claude-specific phrasing

Read through `AGENTS.md` and rewrite any Claude- or Claude Code-specific phrasing the refresh in Step 10 may have introduced (e.g. "Claude Code will...", "tell Claude to...") into generic language that applies to any AI coding agent. Preserve all factual content and the graphify section's meaning exactly.

## Step 12 - Commit the refreshed documentation

```bash
git add AGENTS.md CLAUDE.md
git status --short
```

If nothing is staged, skip the commit and say so. Otherwise:

```bash
git commit -m "Refresh AGENTS.md project guide"
```

## Step 13 - Summarize

Tell the user:
- Which branch the update was committed to
- What changed in the graphify outputs (new/changed files picked up, updated benchmark numbers)
- Whether the `## graphify` wiring needed restoring
- Whether `AGENTS.md` content changed, and what commit(s) were created (there may be zero, one, or two, depending on what actually changed)
