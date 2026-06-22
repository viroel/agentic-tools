# CLAUDE.md

Agents: explore the repo directly

## Purpose

This repository is the canonical home for Claude Code skills, agents, and
tooling used across OpenStack-related development work. It is **not specific
to any single OpenStack project**.

New skills and agents are authored here first, then referenced from
project-specific repos.

## Repo Layout

```text
.claude/
  agents/
    ptl-tracker.md        — Release deadlines and PTL duties for any OpenStack project
  skills/
    lp-bug-triage/        — Launchpad bug triage (untriaged + critical)
    openstack-ml-digest/  — Summarise the openstack-discuss mailing list
```

Each skill directory contains a self-contained `SKILL.md` and optionally
`scripts/` and other assets.

## Sibling Repo Convention

All OpenStack-related repositories are expected to live as siblings of this repo under the same
parent directory. Paths to files in those repos use the `../repo-name/` prefix relative to this
working directory. For example, `../watcher/` or `../agentic-workflows/`.

## Additional Skills, Knowledge, and Agents from Sibling Repos

### repo: agentic-workflows (https://review.opendev.org/openstack/agentic-workflows)

- Use `../agentic-workflows/knowledge/overlays/language/python.md` for distilled OpenStack Python
  context. Use project docs, `../agentic-workflows/knowledge/reference/hacking.md`, and
  `../agentic-workflows/knowledge/reference/pep8.md` when deeper policy detail is needed.
- Use `../agentic-workflows/knowledge/overlays/topic/python-typing.md` for Python typing construct,
  annotation mechanics, semantics, and compatibility guidance.
- Use `../agentic-workflows/.agents/skills/python-typing-reference/` for focused Python typing
  annotation and construct-selection questions.
- Use `../agentic-workflows/.agents/skills/openstack-typing-rollout/` when progressively adding
  mypy, `py.typed`, or type hints to OpenStack Python projects.
- Use `../agentic-workflows/knowledge/overlays/topic/commit-message.md` and
  `../agentic-workflows/.agents/skills/commit-msg-refiner/` for OpenStack commit-message work.
- Use `../agentic-workflows/.agents/skills/skill-designer/` for creating or revising skills,
  including quick stubs, knowledge routing, evals, and guardrails.
- Use `../agentic-workflows/.agents/skills/running-tempest/` when running Tempest on any live
  OpenStack cloud or selecting test suites.

### repo: openstack-ai-style-guide (https://github.com/SeanMooney/openstack-ai-style-guide)

- Use `../openstack-ai-style-guide/docs/comprehensive-guide.md` for additional instructions on how to
  generate Python code for OpenStack projects.
- Use `../openstack-ai-style-guide/docs/quick-rules.md` for quick rules on Python code generation for
  OpenStack projects.
- Use `../openstack-ai-style-guide/agents/code-review-agent.md` when reviewing a gerrit change.

### repo: openstack-lp-bug-manager (https://github.com/gouthampacha/openstack-lp-bug-manager)

- Use the **lp-bug MCP server** (`mcp__lp-bug__*` tools) for all Launchpad
  bug operations: searching, filing, updating, triage, cycle analytics, and
  VMT workflows.
- The `lp-bug-triage` skill in this repo uses these MCP tools as its primary
  driver.
- See `../openstack-lp-bug-manager/.claude/commands/lp-bug.md` for the full tool-to-command
  mapping.

### repo: devskills (https://github.com/openstack-k8s-operators/devskills)

- Use `../devskills/skills/jira/SKILL.md` to inspect any Jira OSPRH-related ticket.
- Use `../devskills/skills/feature/SKILL.md` to navigate Feature issue types.
- Use `../devskills/skills/task-executor/SKILL.md` for posting comments into Jira issues and for
  breakdown and refinements of Features and Epics.

## Jira Integration

- **MCP available**: Use the **atlassian** MCP server
  (`https://mcp.atlassian.com/v1/mcp`). Jira instance: `redhat.atlassian.net`.
  Default project: **OSPRH**.
- **Fallback**: If MCP is unavailable, use pasted ticket content and produce
  **ready-to-paste** Jira comments and transition notes for the user.
- Do NOT update any Jira without user's permission.

## Operational Guardrails

- Git read-only operations such as `git log`, `git diff`, and `git status` are
  fine. Mutating operations such as `add`, `commit`, `reset`, `checkout`,
  `push`, `stash`, `merge`, or `branch` require explicit user approval.
