#!/usr/bin/env python3
"""Fetch untriaged bugs from Launchpad for one or more projects.

Untriaged = Status is "New" and/or Importance is "Undecided".
Uses the public Launchpad REST API; no authentication required.

Usage:
    python3 lp_untriaged_bugs.py <project> [project ...]

Exit codes:
    0  success (even if zero bugs found)
    1  no project specified, or all project requests failed
"""

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field

LP_API = "https://api.launchpad.net/1.0"
PAGE_SIZE = 75


@dataclass
class BugTask:
    bug_id: str
    status: str
    importance: str
    title: str
    web_link: str
    date_created: str

    @property
    def summary(self) -> str:
        # title format: 'Bug #NNNN in project: "Summary here"'
        for sep in ('": "', ': "'):
            if sep in self.title:
                return self.title.split(sep, 1)[1].rstrip('"')
        return self.title

    @property
    def created_date(self) -> str:
        return self.date_created[:10]

    @property
    def is_status_unset(self) -> bool:
        return self.status == "New"

    @property
    def is_importance_unset(self) -> bool:
        return self.importance == "Undecided"


@dataclass
class ProjectResult:
    project: str
    bugs: dict[str, BugTask] = field(default_factory=dict)
    error: str | None = None

    @property
    def both_unset(self) -> list[BugTask]:
        return sorted(
            [b for b in self.bugs.values() if b.is_status_unset and b.is_importance_unset],
            key=lambda b: b.bug_id,
        )

    @property
    def status_unset(self) -> list[BugTask]:
        return sorted(
            [b for b in self.bugs.values() if b.is_status_unset and not b.is_importance_unset],
            key=lambda b: b.bug_id,
        )

    @property
    def importance_unset(self) -> list[BugTask]:
        return sorted(
            [b for b in self.bugs.values() if not b.is_status_unset and b.is_importance_unset],
            key=lambda b: b.bug_id,
        )


def _fetch_page(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc.reason}") from exc


def fetch_tasks(project: str, **filters) -> list[dict]:
    """Fetch all bug task entries for a project with the given filter params."""
    query = "&".join(f"{k}={v}" for k, v in filters.items())
    base = f"{LP_API}/{project}?ws.op=searchTasks&{query}&ws.size={PAGE_SIZE}"

    entries: list[dict] = []
    start = 0
    while True:
        data = _fetch_page(f"{base}&ws.start={start}")
        entries.extend(data["entries"])
        total = data["total_size"]
        start += PAGE_SIZE
        if start >= total:
            break
    return entries


def _entry_to_bug(entry: dict) -> BugTask:
    bug_id = entry["web_link"].split("/+bug/")[1]
    return BugTask(
        bug_id=bug_id,
        status=entry["status"],
        importance=entry["importance"],
        title=entry["title"],
        web_link=entry["web_link"],
        date_created=entry["date_created"],
    )


def fetch_untriaged(project: str) -> ProjectResult:
    result = ProjectResult(project=project)
    try:
        for entry in fetch_tasks(project, status="New"):
            bug = _entry_to_bug(entry)
            result.bugs[bug.bug_id] = bug

        for entry in fetch_tasks(project, importance="Undecided"):
            if entry["status"] == "New":
                continue  # already collected above
            bug = _entry_to_bug(entry)
            result.bugs[bug.bug_id] = bug

    except RuntimeError as exc:
        result.error = str(exc)

    return result


def _print_group(label: str, bugs: list[BugTask]) -> None:
    print(f"\n### {label}")
    if not bugs:
        print("  (none)")
        return
    for bug in bugs:
        print(f"- Bug #{bug.bug_id} — {bug.summary}")
        print(f"  {bug.web_link}")
        print(f"  Created: {bug.created_date}")


def print_result(result: ProjectResult) -> None:
    if result.error:
        print(f"\n## {result.project} — ERROR: {result.error}")
        return

    count = len(result.bugs)
    noun = "untriaged bug" if count == 1 else "untriaged bugs"
    print(f"\n## {result.project} — {count} {noun}")

    _print_group("Both unset (Status=New, Importance=Undecided)", result.both_unset)
    _print_group("Status not set (Status=New, Importance already assigned)", result.status_unset)
    _print_group("Importance not set (Status triaged, Importance=Undecided)", result.importance_unset)


def main(projects: list[str]) -> int:
    results = [fetch_untriaged(p) for p in projects]

    for result in results:
        print_result(result)
        if len(results) > 1:
            print("\n---")

    successful = [r for r in results if r.error is None]
    total_bugs = sum(len(r.bugs) for r in successful)
    print(f"\nTotal: {total_bugs} untriaged bugs across {len(successful)} project(s).")

    return 0 if successful else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: lp_untriaged_bugs.py <project> [project ...]", file=sys.stderr)
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
