"""Curated Curiosities orchestrator.

The agents in `.claude/agents/*.md` run as Claude Code subagents — there is no
Anthropic-API code here. This package only holds:

- `work_dir`: canonical path conventions for agent outputs.
- `schemas`: hand-rolled validators (stdlib-only) for each agent's output.

The dashboard's "next action" CTAs and the worker's file watcher (Phase 4)
both reach into `work_dir` for paths and `schemas` for validation.
"""
