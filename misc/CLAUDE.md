# graphify
- **graphify** (`~/.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.
# subagent default model
When invoking the Agent tool (spawning subagents/Task calls), always pass `model: "haiku"` unless the user explicitly requests a different model for that agent or task, or the task clearly requires stronger reasoning that the user would want upgraded (use judgment, but default to haiku otherwise). This does not apply to `subagent_type: "fork"` calls, since forks always inherit the parent model regardless of any override.
