---
description: Bootstrap a project onto a new branch with AGENTS.md (CLAUDE.md symlink), a graphify knowledge graph, and a benchmark report
argument-hint: [new-branch-name]
---

# /claudify-project

Onboard the current project onto graphify + any AI coding agent: create a clean branch, build a graphify knowledge graph with a benchmark report, wire graphify into a fresh `CLAUDE.md`, generate the rest of the project documentation with graphify already wired in, generalize the file for any AI agent, rename it to `AGENTS.md` (with `CLAUDE.md` symlinked to it), and commit everything in two clean commits.

Follow these steps **in order**. Do not skip steps. Stop and tell the user if any step fails instead of pushing through.

## Step 1 - Verify required tools are installed

```bash
MISSING_TOOLS=""
command -v git >/dev/null 2>&1 || MISSING_TOOLS="$MISSING_TOOLS git"
command -v graphify >/dev/null 2>&1 || MISSING_TOOLS="$MISSING_TOOLS graphify"
echo "Missing:$MISSING_TOOLS"
```

This command needs `git` (branching/committing) and the `graphify` CLI (Steps 6 and 9 call `graphify benchmark` / `graphify claude install` directly).

- If nothing is missing: continue to Step 2.
- If `git` is missing: tell the user `git` is required and ask whether they want to install it now (e.g. `sudo apt install git`, `brew install git`, or whatever fits their platform). If they agree, run the install, then re-check `command -v git`. If they decline, or it's still missing afterward, **stop and abort the whole command** — do not continue to any later step.
- If `graphify` is missing: tell the user the `graphify` CLI is required and ask whether they want to install it now:
  ```bash
  command -v uv >/dev/null 2>&1 && uv tool install graphifyy || pip install graphifyy
  ```
  If they agree, run the install, then re-check `command -v graphify`. If they decline, or it's still missing afterward, **stop and abort the whole command** — do not continue to any later step.

Only proceed once every required tool is confirmed present.

## Step 2 - Verify git status allows a branch switch

```bash
git status --porcelain
git rev-parse --is-inside-work-tree 2>/dev/null || echo "NOT_A_REPO"
```

- If `NOT_A_REPO` prints: stop and tell the user this isn't a git repository (offer to `git init` if they want).
- If `git status --porcelain` prints anything (uncommitted changes, staged changes, or untracked files): stop. Show the user what's dirty and ask whether to commit, stash (`git stash -u`), or abort. Do **not** silently switch branches over dirty state.
- If the tree is clean: continue.

## Step 3 - Ask which branch to branch from

```bash
git branch --format='%(refname:short)' | cat
git symbolic-ref --short HEAD
```

Ask the user which existing branch should be the origin/base for the new branch (default to the current branch if they have no preference). Wait for their answer before continuing.

## Step 4 - Create the new branch

Determine the new branch name: use `$1` (the argument passed to this command) if given, otherwise default to `claudify-project`.

```bash
git checkout <base-branch>
git pull --ff-only 2>/dev/null || true
git checkout -b <new-branch-name>
```

If `<new-branch-name>` already exists, ask the user whether to reuse it, pick a different name, or abort.

## Step 5 - Build the graphify knowledge graph

Invoke the `graphify` skill with path `.` (equivalent to running `/graphify .`) on the project root. Let the full pipeline run (detection, extraction, clustering, labeling, HTML export) to completion.

## Step 6 - Run the graphify benchmark and save the report

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

Show the benchmark results to the user.

## Step 7 - Gitignore graphify's machine-local files

Append to `.gitignore` (create it if missing) only the files that encode this machine's local state — everything else in `graphify-out/` (graph.json, GRAPH_REPORT.md, BENCHMARK_REPORT.md, graph.html, manifest.json, cache/) is meant to be committed and shared:

```bash
touch .gitignore
grep -qxF '# graphify: machine-local state, not portable across checkouts' .gitignore || echo '# graphify: machine-local state, not portable across checkouts' >> .gitignore
grep -qxF 'graphify-out/.graphify_python' .gitignore || echo 'graphify-out/.graphify_python' >> .gitignore
grep -qxF 'graphify-out/.graphify_root' .gitignore || echo 'graphify-out/.graphify_root' >> .gitignore
grep -qxF 'graphify-out/cost.json' .gitignore || echo 'graphify-out/cost.json' >> .gitignore
```

## Step 8 - Commit the graphify graph, benchmark report, and gitignore

```bash
git add graphify-out .gitignore
git status --short
git commit -m "Add graphify knowledge graph and benchmark report"
```

Review the `git status --short` output before committing to make sure only the intended files are staged (no machine-local dotfiles, nothing unrelated).

## Step 9 - Wire graphify into a fresh CLAUDE.md

```bash
graphify claude install
```

`CLAUDE.md` does not exist yet at this point, so this creates it fresh containing only the `## graphify` section (instructing agents to check the graph before answering codebase questions and rebuild it after code changes). Confirm with `grep -n "## graphify" CLAUDE.md` that the section landed.

## Step 10 - Generate the rest of CLAUDE.md via /init, with graphify already in it

Invoke the `init` skill (equivalent to running `/init`) to generate the rest of the project guide. Let it fully scan the codebase and write into `CLAUDE.md` as it normally would, but instruct it to **preserve the existing `## graphify` section verbatim** rather than overwriting or removing it — the finished `CLAUDE.md` should read as one coherent document with graphify already wired in from the start, not bolted on afterward.

Verify with `grep -n "## graphify" CLAUDE.md` that the section is still present after `/init` runs.

## Step 11 - Generalize CLAUDE.md for any AI agent

Read through the full `CLAUDE.md` and rewrite any Claude- or Claude Code-specific phrasing (e.g. "Claude Code will...", "tell Claude to...") into generic language that applies to any AI coding agent (e.g. "the agent will...", "instruct the agent to..."). Preserve all factual content, commands, and the graphify section's meaning exactly — only generalize the phrasing so the file reads correctly once it becomes `AGENTS.md`.

## Step 12 - Rename to AGENTS.md and symlink CLAUDE.md

```bash
mv CLAUDE.md AGENTS.md
ln -s AGENTS.md CLAUDE.md
git add AGENTS.md CLAUDE.md
git commit -m "Add AGENTS.md project guide with graphify wired in (CLAUDE.md symlinked to it)"
```

Verify with `ls -la CLAUDE.md` that it shows up as a symlink pointing to `AGENTS.md` before committing.

## Step 13 - Summarize

Tell the user:
- The new branch name and what it was based on
- The graphify outputs available in `graphify-out/` (graph.html, GRAPH_REPORT.md, BENCHMARK_REPORT.md)
- That `AGENTS.md` was generated with graphify already wired in, generalized for any AI agent, with `CLAUDE.md` symlinked to it
- The two commits that were created
