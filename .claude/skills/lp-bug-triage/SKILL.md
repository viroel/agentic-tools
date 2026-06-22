---
name: lp-bug-triage
description: Launchpad bug triage helper for any OpenStack project. Two commands: default lists bugs missing Status or Importance (untriaged); "critical" lists High/Critical bugs that are unassigned or stale in-progress (no update >14 days). Defaults to watcher and watcher-tempest-plugin. Uses the lp-bug MCP server when available, falls back to local scripts otherwise.
argument-hint: "[critical] [watcher|watcher-tempest-plugin|all|<project>]"
user-invocable: true
allowed-tools: ["mcp__lp-bug__search_bugs", "mcp__lp-bug__scrub_report", "Bash"]
context: fork
---

Launchpad bug triage helper. Two commands share this skill, selected by the
first argument.

## Driver

This skill uses the **lp-bug MCP server** from `../openstack-lp-bug-manager`
as its primary data source. If MCP tools are unavailable, fall back to the
local scripts in `scripts/` as described in the Fallback sections.

## Routing

Parse the user's arguments to decide which command to run:

- First argument is `critical` → **Command: critical** (strip `critical`,
  remaining args are projects)
- Otherwise → **Command: untriaged** (all args are projects)

Default projects (when none are given): `watcher watcher-tempest-plugin`.

---

## Command: untriaged (default)

Lists bugs where Status is still `New` (not reviewed) and/or Importance is
still `Undecided` (not set).

### Argument mapping

| User invocation | Projects |
|---|---|
| `/lp-bug-triage` | `watcher watcher-tempest-plugin` |
| `/lp-bug-triage all` | `watcher watcher-tempest-plugin` |
| `/lp-bug-triage watcher` | `watcher` |
| `/lp-bug-triage nova` | `nova` |

### Via MCP (preferred)

For each project, issue two calls in parallel:

1. `mcp__lp-bug__search_bugs(project=<project>, status=["New"], max_results=75)`
2. `mcp__lp-bug__search_bugs(project=<project>, importance=["Undecided"], max_results=75)`

Merge by bug ID and classify into three groups:

| Group | Criteria |
|---|---|
| **Both unset** | status=New AND importance=Undecided |
| **Status not set** | status=New, importance already assigned |
| **Importance not set** | status≠New (triaged), importance=Undecided |

### Via Fallback scripts

```bash
SKILL_DIR="$(find ~/.claude -path "*/skills/lp-bug-triage" -type d 2>/dev/null | head -1)"
python3 "$SKILL_DIR/scripts/lp_untriaged_bugs.py" <project> [project ...]
```

### Output format

```
## watcher — N untriaged bugs

### Both unset (Status=New, Importance=Undecided)
- Bug #NNNNNN — Summary
  https://bugs.launchpad.net/watcher/+bug/NNNNNN
  Created: YYYY-MM-DD

### Status not set (Status=New, Importance already assigned)
  (none)

### Importance not set (Status triaged, Importance=Undecided)
- Bug #NNNNNN — Summary
  ...
```

Separator `---` between projects. Final line:
`Total: N untriaged bugs across M projects.`

---

## Command: critical

Lists High and Critical bugs (active statuses only) that need attention:

1. **Unassigned** — no assignee, regardless of status
2. **Stale In Progress** — status is `In Progress` and not updated for >14 days

### Argument mapping

| User invocation | Projects |
|---|---|
| `/lp-bug-triage critical` | `watcher watcher-tempest-plugin` |
| `/lp-bug-triage critical all` | `watcher watcher-tempest-plugin` |
| `/lp-bug-triage critical watcher` | `watcher` |
| `/lp-bug-triage critical nova` | `nova` |

### Via MCP (preferred)

For each project:

```
mcp__lp-bug__search_bugs(
    project=<project>,
    importance=["High", "Critical"],
    max_results=75
)
```

From the results:
- Discard terminal statuses: `Fix Released`, `Fix Committed`, `Won't Fix`, `Invalid`
- **Unassigned**: `assignee` is null or empty
- **Stale In Progress**: `status == "In Progress"` AND `updated` older than 14 days

### Via Fallback scripts

```bash
SKILL_DIR="$(find ~/.claude -path "*/skills/lp-bug-triage" -type d 2>/dev/null | head -1)"
python3 "$SKILL_DIR/scripts/lp_critical_bugs.py" <project> [project ...]
```

### Output format

```
## watcher — N High/Critical bug(s) needing attention

### Unassigned (N)
- Bug #NNNNNN [High] — Summary
  Status: Triaged
  https://bugs.launchpad.net/watcher/+bug/NNNNNN
  Created: YYYY-MM-DD

### Stale In Progress — no update for >14 days (N)
- Bug #NNNNNN [Critical] — Summary
  Last updated: YYYY-MM-DD (N days ago) | Assignee: username
  https://bugs.launchpad.net/watcher/+bug/NNNNNN
  Created: YYYY-MM-DD
```

A bug may appear in both sections if it is both unassigned and stale.

---

## Constraints

- **Read-only**: never call any write MCP tool or API method that modifies a bug.
- If a project request fails, report the error and continue with remaining projects.
