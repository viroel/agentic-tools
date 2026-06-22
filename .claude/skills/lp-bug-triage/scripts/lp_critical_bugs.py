#!/usr/bin/env python3
"""Find High and Critical Launchpad bugs needing attention.

Reports bugs that:
  1. Have no assignee (all active statuses)
  2. Are In Progress but have not been updated for more than STALE_DAYS days

Uses the public Launchpad REST API; no authentication required.

Usage:
    python3 lp_critical_bugs.py <project> [project ...]

Exit codes:
    0  success
    1  no project specified, or all project requests failed
"""

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

LP_API = "https://api.launchpad.net/1.0"
PAGE_SIZE = 75
STALE_DAYS = 14

ACTIVE_STATUSES = {"New", "Incomplete", "Confirmed", "Triaged", "In Progress"}
IMPORTANCE_ORDER = {"Critical": 0, "High": 1}


@dataclass
class BugTask:
    bug_id: str
    status: str
    importance: str
    title: str
    web_link: str
    bug_link: str
    date_created: str
    assignee_link: str | None

    @property
    def summary(self) -> str:
        for sep in ('": "', ': "'):
            if sep in self.title:
                return self.title.split(sep, 1)[1].rstrip('"')
        return self.title

    @property
    def created_date(self) -> str:
        return self.date_created[:10]

    @property
    def assignee_name(self) -> str | None:
        if self.assignee_link is None:
            return None
        return self.assignee_link.rstrip("/").rsplit("~", 1)[-1]


def _fetch_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc.reason}") from exc


def _fetch_all_tasks(base_url: str) -> list[dict]:
    entries: list[dict] = []
    start = 0
    while True:
        data = _fetch_json(f"{base_url}&ws.start={start}&ws.size={PAGE_SIZE}")
        entries.extend(data["entries"])
        start += PAGE_SIZE
        if start >= data["total_size"]:
            break
    return entries


def _entry_to_bug(entry: dict) -> BugTask:
    return BugTask(
        bug_id=entry["web_link"].split("/+bug/")[1],
        status=entry["status"],
        importance=entry["importance"],
        title=entry["title"],
        web_link=entry["web_link"],
        bug_link=entry["bug_link"],
        date_created=entry["date_created"],
        assignee_link=entry.get("assignee_link"),
    )


def _fetch_last_updated(bug_link: str) -> datetime | None:
    try:
        raw = _fetch_json(bug_link).get("date_last_updated")
        return datetime.fromisoformat(raw) if raw else None
    except RuntimeError:
        return None


def _importance_key(bug: BugTask) -> tuple:
    return (IMPORTANCE_ORDER.get(bug.importance, 99), bug.bug_id)


def analyze(project: str) -> tuple[
    list[BugTask],
    list[tuple[BugTask, datetime]],
    str | None,
]:
    """Return (unassigned, stale_in_progress, error)."""
    try:
        base = (
            f"{LP_API}/{project}?ws.op=searchTasks"
            f"&importance=High&importance=Critical"
        )
        bugs: dict[str, BugTask] = {}
        for entry in _fetch_all_tasks(base):
            if entry["status"] not in ACTIVE_STATUSES:
                continue
            bug = _entry_to_bug(entry)
            bugs[bug.bug_id] = bug
    except RuntimeError as exc:
        return [], [], str(exc)

    now = datetime.now(tz=timezone.utc)
    threshold = now - timedelta(days=STALE_DAYS)

    unassigned = sorted(
        [b for b in bugs.values() if b.assignee_link is None],
        key=_importance_key,
    )

    stale: list[tuple[BugTask, datetime]] = []
    for bug in bugs.values():
        if bug.status != "In Progress":
            continue
        last_updated = _fetch_last_updated(bug.bug_link)
        if last_updated and last_updated < threshold:
            stale.append((bug, last_updated))
    stale.sort(key=lambda x: x[1])  # oldest first

    return unassigned, stale, None


def _print_bug(bug: BugTask, detail: str = "") -> None:
    print(f"- Bug #{bug.bug_id} [{bug.importance}] — {bug.summary}")
    if detail:
        print(f"  {detail}")
    print(f"  {bug.web_link}")
    print(f"  Created: {bug.created_date}")


def _print_project(
    project: str,
    unassigned: list[BugTask],
    stale: list[tuple[BugTask, datetime]],
    error: str | None,
) -> None:
    if error:
        print(f"\n## {project} — ERROR: {error}")
        return

    now = datetime.now(tz=timezone.utc)
    total = len({b.bug_id for b in unassigned} | {b.bug_id for b, _ in stale})
    print(f"\n## {project} — {total} High/Critical bug(s) needing attention")

    print(f"\n### Unassigned ({len(unassigned)})")
    if unassigned:
        for bug in unassigned:
            _print_bug(bug, f"Status: {bug.status}")
    else:
        print("  (none)")

    print(f"\n### Stale In Progress — no update for >{STALE_DAYS} days ({len(stale)})")
    if stale:
        for bug, last_updated in stale:
            days = (now - last_updated).days
            assignee = bug.assignee_name or "unassigned"
            _print_bug(
                bug,
                f"Last updated: {last_updated.date()} ({days} days ago)"
                f" | Assignee: {assignee}",
            )
    else:
        print("  (none)")


def main(projects: list[str]) -> int:
    results = [(*analyze(p), p) for p in projects]

    for i, (unassigned, stale, error, project) in enumerate(results):
        _print_project(project, unassigned, stale, error)
        if i < len(results) - 1:
            print("\n---")

    successful = [(u, s) for u, s, e, _ in results if e is None]
    total = sum(
        len({b.bug_id for b in u} | {b.bug_id for b, _ in s})
        for u, s in successful
    )
    print(f"\nTotal: {total} bug(s) needing attention across {len(successful)} project(s).")
    return 0 if successful else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: lp_critical_bugs.py <project> [project ...]", file=sys.stderr)
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
