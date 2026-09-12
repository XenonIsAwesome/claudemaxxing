---
description: Bootstrap a project onto a new branch with AGENTS.md (CLAUDE.md symlink), a graphify knowledge graph, and a benchmark report
argument-hint: [new-branch-name]
---

# /claudify-project

Onboard the current project onto graphify + any AI coding agent: create a clean branch, build a graphify knowledge graph with a benchmark report, wire graphify into a fresh `CLAUDE.md`, generate the rest of the project documentation with graphify already wired in, generalize the file for any AI agent, rename it to `AGENTS.md` (with `CLAUDE.md` symlinked to it), and commit everything in two clean commits. Safe to run on a project that already has a graphify graph and/or a `CLAUDE.md`/`AGENTS.md` — it detects existing state at each point and asks how to handle it rather than silently rebuilding or overwriting.

Follow these steps **in order**. Do not skip steps. Stop and tell the user if any step fails instead of pushing through.

## Step 1 - Verify required tools are installed

```bash
MISSING_TOOLS=""
command -v git >/dev/null 2>&1 || MISSING_TOOLS="$MISSING_TOOLS git"
command -v graphify >/dev/null 2>&1 || MISSING_TOOLS="$MISSING_TOOLS graphify"
echo "Missing:$MISSING_TOOLS"
```

This command needs `git` (branching/committing) and the `graphify` CLI (Steps 7 and 10 call `graphify benchmark` / `graphify claude install` directly).

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

## Step 5 - Check whether this project is already claudified

Run this only now, after checking out the base branch in Step 4 — the base branch the user picked may not be the branch that was checked out when this command started, so its `graphify-out/` and `CLAUDE.md`/`AGENTS.md` state can differ from what an earlier look would have shown.

```bash
ls graphify-out/graph.json 2>/dev/null && echo "GRAPH_EXISTS" || echo "NO_GRAPH"
if [ -L CLAUDE.md ] && [ "$(readlink CLAUDE.md)" = "AGENTS.md" ]; then echo "ALREADY_SYMLINKED"; else echo "NOT_SYMLINKED"; fi
```

If **both** `GRAPH_EXISTS` and `ALREADY_SYMLINKED` print: this project has already been through `/claudify-project` (or `update-claudification`) before. Tell the user this and ask how to proceed:
- Run `update-claudification` instead (Recommended) — refreshes the existing graph, benchmark, and `AGENTS.md` in place rather than creating a parallel onboarding branch.
- Continue anyway with a fresh `/claudify-project` run on this new branch — e.g. redoing the onboarding from scratch, or the user has a specific reason to re-run it.
- Abort.

If the user picks `update-claudification`, invoke that skill instead and stop following this command. If they choose to abort, stop here. Otherwise (continue anyway, or only one/neither of the two conditions held — a partial state is not full claudification and isn't a reason to redirect) proceed to Step 6; Steps 6 and 10 handle each piece's existing state on its own.

## Step 6 - Build the graphify knowledge graph

Check whether `graphify-out/graph.json` already exists (it may, if Step 5 found a partial state, or the user chose to continue anyway despite a full match).

- If it does **not** exist: invoke the `graphify` skill with path `.` (equivalent to running `/graphify .`) on the project root. Let the full pipeline run (detection, extraction, clustering, labeling, HTML export) to completion.
- If it **does** exist: tell the user and ask how to proceed before touching it:
  - Rebuild fully (Recommended) — discard the existing graph and run the full `/graphify .` pipeline from scratch, so the graph reflects the current codebase and this onboarding branch has a clean baseline.
  - Incremental update — run `/graphify . --update` to re-extract only new/changed files and refresh clustering on top of the existing graph (faster, but may carry over stale community labels from before).
  - Reuse as-is — skip rebuilding entirely and use the existing `graphify-out/graph.json` for the benchmark (Step 7) and report as they stand.

  Wait for the user's answer before continuing. Whichever option is chosen, make sure `graphify-out/graph.json` exists before moving on to Step 7.

## Step 7 - Run the graphify benchmark and save the report

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

Show the benchmark results to the user. If `graphify benchmark` errors (e.g. "No matching nodes found for sample questions" — its generic sample questions assume a web/service-shaped codebase and can miss a small or domain-specific corpus entirely), don't just leave the literal error in the report: tell the user what happened and ask whether to (a) substitute questions tailored to this project's actual graph vocabulary via the Python API (`graphify.benchmark.run_benchmark(graph_path, questions=[...])`) so the report shows real numbers — recommended — (b) keep the literal error as an honest but unhelpful report, or (c) skip the benchmark report entirely. Save whichever outcome to `graphify-out/BENCHMARK_REPORT.md`, noting in the file itself when custom questions were substituted and why.

## Step 8 - Gitignore graphify's machine-local files and cache

Append to `.gitignore` (create it if missing) the files/dirs that are local to this machine or this specific build — everything else in `graphify-out/` (graph.json, GRAPH_REPORT.md, BENCHMARK_REPORT.md, graph.html, manifest.json) is meant to be committed and shared:

```bash
touch .gitignore
grep -qxF '# graphify: machine-local state, not portable across checkouts' .gitignore || echo '# graphify: machine-local state, not portable across checkouts' >> .gitignore
grep -qxF 'graphify-out/.graphify_python' .gitignore || echo 'graphify-out/.graphify_python' >> .gitignore
grep -qxF 'graphify-out/.graphify_root' .gitignore || echo 'graphify-out/.graphify_root' >> .gitignore
grep -qxF 'graphify-out/cost.json' .gitignore || echo 'graphify-out/cost.json' >> .gitignore
grep -qxF 'graphify-out/cache' .gitignore || echo 'graphify-out/cache' >> .gitignore
```

`graphify-out/cache/` holds the AST/semantic extraction cache for this build. It can grow large, doesn't help anyone else's clone (a fresh clone, or `graphify update`, just rebuilds what it needs), and its contents are keyed to file hashes rather than anything a reviewer would want to read — it is gitignored, not committed.

If this project has been through an earlier version of this command and `graphify-out/cache/` is already tracked from a prior commit, untrack it too so the new ignore rule actually takes effect:

```bash
git ls-files graphify-out/cache | head -1 >/dev/null && git rm -r --cached graphify-out/cache >/dev/null && echo "untracked graphify-out/cache"
```

When appending to an existing `.gitignore` that doesn't end in a newline, make sure the new lines don't get concatenated onto its last line — add a leading blank line first if needed, and check the result with `cat .gitignore` before moving on.

## Step 9 - Commit the graphify graph, benchmark report, and gitignore

```bash
git add graphify-out .gitignore
git status --short
git commit -m "Add graphify knowledge graph and benchmark report"
```

Review the `git status --short` output before committing to make sure only the intended files are staged — no machine-local dotfiles, no `graphify-out/cache/` entries (it's gitignored now, so none should appear), nothing unrelated.

## Step 10 - Wire graphify into CLAUDE.md

```bash
ls CLAUDE.md 2>/dev/null && echo "CLAUDE_EXISTS" || echo "NO_CLAUDE"
ls AGENTS.md 2>/dev/null && echo "AGENTS_EXISTS" || echo "NO_AGENTS"
```

If **neither** file exists: run `graphify claude install` as-is — it creates `CLAUDE.md` fresh with just the `## graphify` section — and continue to Step 11.

If `CLAUDE.md` and/or `AGENTS.md` already exist with real content (Step 5 already redirected the fully-claudified symlink case, so anything found here is independent content, not a stale symlink): tell the user what exists and ask how to handle it before running `graphify claude install` — otherwise a fresh `graphify claude install` would create a second, disconnected `CLAUDE.md`, and Step 13's rename would silently overwrite whichever of `AGENTS.md`/`CLAUDE.md` is left over:
- Merge into new CLAUDE.md first (Recommended) — copy the existing file's content into `CLAUDE.md` (if only `AGENTS.md` exists: `cp AGENTS.md CLAUDE.md`; if `CLAUDE.md` already has content, leave it in place) so `graphify claude install`'s idempotent section-append preserves it, and Step 11's `/init` pass merges/refreshes it into one coherent document instead of losing it.
- Overwrite it — proceed with a fresh `CLAUDE.md`, discarding the old content (Step 13 will overwrite `AGENTS.md` with it).
- Back up the existing file(s) first, then overwrite — copy each existing file to `<name>.bak` before proceeding as in "Overwrite it".

Wait for the user's answer before continuing. Then run `graphify claude install` and confirm with `grep -n "## graphify" CLAUDE.md` that the section landed.

## Step 11 - Generate the rest of CLAUDE.md via /init, with graphify already in it

Invoke the `init` skill (equivalent to running `/init`) to generate the rest of the project guide. Let it fully scan the codebase and write into `CLAUDE.md` as it normally would, but instruct it to:
- **preserve the existing `## graphify` section verbatim** rather than overwriting or removing it, and
- if Step 10 carried forward pre-existing content (the user chose "merge into new CLAUDE.md first"), **incorporate that content** rather than discarding it — merge/refresh it as part of the generated guide so the finished file reads as one coherent document with graphify wired in from the start, not two documents stapled together.

Verify with `grep -n "## graphify" CLAUDE.md` that the section is still present after `/init` runs.

## Step 12 - Generalize CLAUDE.md for any AI agent

Read through the full `CLAUDE.md` and rewrite any Claude- or Claude Code-specific phrasing (e.g. "Claude Code will...", "tell Claude to...") into generic language that applies to any AI coding agent (e.g. "the agent will...", "instruct the agent to..."). Preserve all factual content, commands, and the graphify section's meaning exactly — only generalize the phrasing so the file reads correctly once it becomes `AGENTS.md`.

## Step 13 - Rename to AGENTS.md and symlink CLAUDE.md

```bash
mv CLAUDE.md AGENTS.md
ln -s AGENTS.md CLAUDE.md
git add AGENTS.md CLAUDE.md
git commit -m "Add AGENTS.md project guide with graphify wired in (CLAUDE.md symlinked to it)"
```

`mv` overwrites any `AGENTS.md` left over from before Step 10 — that's expected: Step 10 already resolved what happens to its content (merged in, backed up, or discarded) based on the user's choice, so nothing is silently lost here.

Verify with `ls -la CLAUDE.md` that it shows up as a symlink pointing to `AGENTS.md` before committing.

## Step 14 - Summarize

Tell the user:
- The new branch name and what it was based on
- Whether the graphify graph was built fresh, updated incrementally, or reused as-is (Step 6), and whether any pre-existing `CLAUDE.md`/`AGENTS.md` content was merged, overwritten, or backed up (Step 10)
- The graphify outputs available in `graphify-out/` (graph.html, GRAPH_REPORT.md, BENCHMARK_REPORT.md) — note that `graphify-out/cache/` is gitignored and won't show up in the repo
- That `AGENTS.md` was generated with graphify already wired in, generalized for any AI agent, with `CLAUDE.md` symlinked to it
- The two commits that were created
