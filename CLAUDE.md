# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Source of truth for setup, workflow, style, and architecture: @AGENTS.md.

When wrapping up or merging a feature branch, use the `finish-branch` skill
(`.claude/skills/finish-branch/`): distil any durable decision into an ADR under
`docs/adr/`, then clean up the branch's plans/specs before merge. See the
"Decisions and finishing a branch" section of @AGENTS.md.
