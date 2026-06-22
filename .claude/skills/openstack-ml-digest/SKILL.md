---
name: openstack-ml-digest
description: >
  Fetch and summarize the openstack-discuss mailing list archive. Builds a
  digest of recent threads with filtering by project name or subject tag.
  Use when asked to: summarize the mailing list, check recent ML activity,
  find discussions about a project, read the openstack-discuss digest.
argument-hint: "[--days N] [--projects p1,p2] [--tags t1,t2] [--top N] [--detail N] [--no-detail]"
user-invocable: true
allowed-tools: ["Bash"]
context: fork
---

Reads the OpenStack Discuss mailing list archive at
`lists.openstack.org` via HyperKitty's monthly archive pages and
outputs a structured markdown digest. The driver script handles all
HTTP fetching and HTML parsing; Claude reads the output and presents
the summary.

## Driver

**Script:** `.claude/skills/openstack-ml-digest/scripts/ml_digest.py`

Run it with the user's parameters, then present the output as the
digest. The script writes progress to stderr and the markdown digest
to stdout.

## Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--days N` | 7 | How many days back to look |
| `--projects p1,p2` | (none) | Filter by project name in subject (e.g. `nova,watcher`) |
| `--tags t1,t2` | (none) | Filter by bracketed subject tag (e.g. `tc,release`) — matches `[tc]`, `[release]` |
| `--top N` | 20 | Max threads to list in the overview table |
| `--detail N` | 5 | Number of top-activity threads to fetch email content for |
| `--no-detail` | off | Skip email fetching entirely (faster, overview table only) |

## Invocation

```bash
SKILL_DIR="$(find ~/.claude "${PWD}" "${PWD%/*}" -maxdepth 6 -path "*/skills/openstack-ml-digest" -type d 2>/dev/null | head -1)"

# Default: past 7 days, top 20 threads, detail for top 5
python "$SKILL_DIR/scripts/ml_digest.py" --days 7

# Quick overview only (no email body fetching)
python "$SKILL_DIR/scripts/ml_digest.py" --days 14 --no-detail

# Filter to specific projects
python "$SKILL_DIR/scripts/ml_digest.py" --days 30 --projects nova,watcher

# Filter by subject tags
python "$SKILL_DIR/scripts/ml_digest.py" --days 7 --tags tc,release,ossa

# Combined filters
python "$SKILL_DIR/scripts/ml_digest.py" --days 30 --projects watcher --tags release,tc --top 15 --detail 3
```

## Output structure

The script outputs:
1. **Overview table** — all matching threads sorted by `replies + participants`
2. **Thread details** — top N threads with opening message body (quoted lines stripped)

Parse both sections and present them to the user. For a "quick digest"
without `--projects`/`--tags`, group threads by topic area if helpful.

## Argument parsing from user input

Map the user's natural language request to flags:

| User says | Flags |
|-----------|-------|
| "past 2 weeks" / "last 14 days" | `--days 14` |
| "about nova" / "nova discussions" | `--projects nova` |
| "TC threads" / "[tc] topics" | `--tags tc` |
| "security advisories" | `--tags ossa,ossn` |
| "release-related" | `--tags release` |
| "just give me a summary" | `--no-detail` |
| "show me the emails" | omit `--no-detail` (default) |

## Gotchas

- **Thread counting**: The archive page shows aggregate stats (e.g. "63 discussions"
  for the whole month). `--top` limits what's shown in the digest, not what's fetched.
- **Date filtering**: Threads are filtered strictly within the `--days` window. A thread
  started before the window but still active won't appear (HyperKitty dates threads
  by their start date, not last activity).
- **Email body parsing**: Only the first 3 messages per thread are fetched. Quoted
  reply lines (starting with `>`) are stripped. Email bodies over 600 chars are
  truncated with `[...]`.
- **Multi-month ranges**: When `--days` spans a month boundary, multiple monthly
  archive pages are fetched sequentially.
- **No auth needed**: The archive is fully public. No login required.
