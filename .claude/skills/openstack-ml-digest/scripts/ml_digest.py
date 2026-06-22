#!/usr/bin/env python3
"""OpenStack Discuss mailing list digest builder.

Fetches threads from lists.openstack.org and outputs a structured
markdown summary for the given date range and optional filters.
"""

import argparse
import re
import sys
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta


BASE_URL = "https://lists.openstack.org"
LIST_ADDR = "openstack-discuss@lists.openstack.org"
LIST_PATH = f"/archives/list/{LIST_ADDR}"


def fetch_url(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "ml-digest/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} fetching {url}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None


def parse_month_threads(html):
    """Parse HyperKitty monthly archive HTML to extract thread metadata.

    Actual HyperKitty HTML structure (v1.3.12):
      <div class="thread">
        <a name="THREAD_ID" href="...thread/THREAD_ID/" class="thread-title">
          <i ...></i>
          Subject Text
        </a>
        <span class="sender-name align-center">by Author Name</span>
        <span class="thread-date pull-right" title="Weekday, DD Month YYYY HH:MM:SS">
          ...
        </span>
        <div class="list-stats pull-right">
          <span class="badge bg-secondary"><i ...></i>N<!-- participants --></span>
          <span class="badge bg-secondary"><i ...></i>N<!-- comments --></span>
        </div>
    """
    threads = []

    # Each thread block starts with <div class="thread"> (class may include "unread")
    chunks = re.split(r'(?=<div class="thread(?:\s[^"]*)?">)', html)

    for chunk in chunks:
        # Find the thread-title anchor — href and class can appear in any order
        link_m = re.search(r'<a\s[^>]*class="[^"]*thread-title[^"]*"[^>]*>', chunk, re.DOTALL)
        if not link_m:
            continue

        link_tag = link_m.group()
        href_m = re.search(r'href="([^"]+)"', link_tag)
        if not href_m:
            continue
        url = href_m.group(1)

        # Subject is the text content after the link opening tag, strip HTML
        after_link = chunk[link_m.end():]
        close_a = after_link.find("</a>")
        inner_html = after_link[:close_a] if close_a != -1 else after_link[:200]
        subject = re.sub(r"<[^>]+>", "", inner_html).strip()
        subject = re.sub(r"\s+", " ", subject)
        if not subject:
            continue

        # Date: title attribute has "Weekday, DD Month YYYY HH:MM:SS"
        date_val = None
        dm = re.search(
            r'<span[^>]+class="[^"]*thread-date[^"]*"[^>]+title="([^"]*)"', chunk
        )
        if dm:
            raw_title = dm.group(1)
            # Strip weekday prefix "Wednesday, " -> "17 June 2026 05:19:25"
            date_part = re.sub(r"^\w+,\s*", "", raw_title)
            for fmt in ("%d %B %Y %H:%M:%S", "%d %B %Y"):
                try:
                    date_val = datetime.strptime(date_part, fmt).date()
                    break
                except ValueError:
                    pass
        if date_val is None:
            # Fallback: visible text "17 Jun '26"
            dm2 = re.search(r"(\d+)\s+(\w+)\s+'(\d\d)", chunk)
            if dm2:
                try:
                    date_val = datetime.strptime(
                        f"{dm2.group(1)} {dm2.group(2)} 20{dm2.group(3)}", "%d %b %Y"
                    ).date()
                except ValueError:
                    pass

        # Author: "by Author Name" inside sender-name span
        author = ""
        sm = re.search(
            r'<span[^>]+class="[^"]*sender-name[^"]*"[^>]*>(.*?)</span>',
            chunk,
            re.DOTALL,
        )
        if sm:
            author = re.sub(r"<[^>]+>", "", sm.group(1)).strip()
            author = re.sub(r"^by\s+", "", author)

        # Reply/participant counts from badge spans inside list-stats
        stats_m = re.search(r'<div[^>]+class="[^"]*list-stats[^"]*"[^>]*>(.*?)</div>', chunk, re.DOTALL)
        participants = 0
        replies = 0
        if stats_m:
            badges = re.findall(
                r'<span[^>]+class="[^"]*badge[^"]*"[^>]*>.*?(\d+)\s*<!--\s*(participants|comments)',
                stats_m.group(1),
                re.DOTALL,
            )
            for val, kind in badges:
                if "participant" in kind:
                    participants = int(val)
                else:
                    replies = int(val)

        # Thread ID from URL or name attribute
        tid_m = re.search(r"/thread/([^/]+)/", url)
        thread_id = tid_m.group(1) if tid_m else ""

        threads.append(
            {
                "subject": subject,
                "url": BASE_URL + url if url.startswith("/") else url,
                "thread_id": thread_id,
                "date": date_val,
                "author": author,
                "participants": participants,
                "replies": replies,
            }
        )

    return threads


def fetch_thread_emails(thread_id, max_emails=3):
    """Fetch a thread page and extract the first N email bodies."""
    url = f"{BASE_URL}{LIST_PATH}/thread/{thread_id}/"
    html = fetch_url(url, timeout=25)
    if not html:
        return []

    # HyperKitty wraps email content in <div class="email-body">
    # Each email block is <div class="email ..."><div class="email-body">...</div>
    bodies = re.findall(
        r'<div[^>]+class="[^"]*email-body[^"]*"[^>]*>(.*?)(?=<div[^>]+class="[^"]*email|</div>\s*</div>\s*(?:</div>|<div[^>]+class="[^"]*email))',
        html,
        re.DOTALL,
    )

    if not bodies:
        # Looser fallback
        bodies = re.findall(
            r'<div[^>]+class="[^"]*email-body[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL
        )

    summaries = []
    for body_html in bodies[:max_emails]:
        text = re.sub(r"<[^>]+>", "", body_html)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        # Strip quoted lines (lines starting with ">")
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith(">")]
        text = "\n".join(lines).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) > 600:
            text = text[:600].rsplit("\n", 1)[0] + "\n[...]"
        summaries.append(text)

    return summaries


def months_in_range(start, end):
    """Return list of (year, month) tuples covering start..end inclusive."""
    months = []
    cur = date(start.year, start.month, 1)
    stop = date(end.year, end.month, 1)
    while cur <= stop:
        months.append((cur.year, cur.month))
        cur = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    return months


def subject_matches(subject, projects, tags):
    """Return True if subject contains any project name or bracketed tag.

    Tag matching handles both exact [tag] and prefixed [TAG-2026-001] forms,
    so 'ossa' matches both '[OSSA]' and '[OSSA-2026-022]'.
    """
    if not projects and not tags:
        return True
    sl = subject.lower()
    for proj in projects:
        if proj.lower() in sl:
            return True
    for tag in tags:
        t = tag.lower()
        # Match [TAG] exactly or [TAG-...] with suffix (e.g. [OSSA-2026-001])
        if re.search(rf"\[{re.escape(t)}(?:[^\]]*)\]", sl):
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="OpenStack Discuss mailing list digest")
    ap.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    ap.add_argument(
        "--projects",
        default="",
        help="Comma-separated project names to highlight (e.g. nova,watcher)",
    )
    ap.add_argument(
        "--tags",
        default="",
        help="Comma-separated bracketed subject tags to filter (e.g. nova,tc,release)",
    )
    ap.add_argument("--top", type=int, default=20, help="Max threads to list (default: 20)")
    ap.add_argument(
        "--detail",
        type=int,
        default=5,
        help="Number of top threads to fetch email content for (default: 5)",
    )
    ap.add_argument(
        "--no-detail",
        action="store_true",
        help="Skip fetching thread email content (faster)",
    )
    args = ap.parse_args()

    today = date.today()
    start_date = today - timedelta(days=args.days)

    projects = [p.strip() for p in args.projects.split(",") if p.strip()]
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    print(f"# OpenStack Discuss Digest")
    print(f"**Period:** {start_date} → {today} (past {args.days} days)\n")

    if projects:
        print(f"**Projects filter:** {', '.join(projects)}")
    if tags:
        print(f"**Tags filter:** {', '.join(f'[{t}]' for t in tags)}")
    if projects or tags:
        print()

    # Collect threads from all relevant months
    all_threads = []
    for year, month in months_in_range(start_date, today):
        url = f"{BASE_URL}{LIST_PATH}/{year}/{month}/?count=200"
        print(f"Fetching archive {year}/{month:02d}...", file=sys.stderr)
        html = fetch_url(url, timeout=30)
        if html:
            month_threads = parse_month_threads(html)
            print(f"  Found {len(month_threads)} threads", file=sys.stderr)
            all_threads.extend(month_threads)

    # Filter by date range
    threads = [
        t
        for t in all_threads
        if t["date"] is not None and start_date <= t["date"] <= today
    ]

    # Filter by project/tag
    if projects or tags:
        threads = [t for t in threads if subject_matches(t["subject"], projects, tags)]

    # Sort by activity score, deduplicate
    threads.sort(key=lambda t: t["replies"] + t["participants"], reverse=True)
    seen_ids = set()
    unique = []
    for t in threads:
        key = t["thread_id"] or t["subject"]
        if key not in seen_ids:
            seen_ids.add(key)
            unique.append(t)
    threads = unique[: args.top]

    if not threads:
        print("No threads found in the specified period.\n")
        print("Try increasing `--days` or removing `--projects`/`--tags` filters.")
        return

    total = len(threads)
    print(f"## Overview — {total} thread{'s' if total != 1 else ''}\n")

    # Table overview
    print("| # | Subject | Date | Author | Replies | Participants |")
    print("|---|---------|------|--------|---------|--------------|")
    for i, t in enumerate(threads, 1):
        ds = t["date"].strftime("%b %d") if t["date"] else "?"
        subj = t["subject"]
        if len(subj) > 65:
            subj = subj[:62] + "..."
        print(f"| {i} | {subj} | {ds} | {t['author']} | {t['replies']} | {t['participants']} |")

    print()

    # Detailed section for most active threads
    if args.no_detail or args.detail == 0:
        return

    detail_n = min(args.detail, len(threads))
    print(f"## Thread Details (top {detail_n} by activity)\n")

    for i, t in enumerate(threads[:detail_n], 1):
        ds = t["date"].strftime("%Y-%m-%d") if t["date"] else "?"
        print(f"### {i}. {t['subject']}")
        print(f"- **Date:** {ds} | **Author:** {t['author']}")
        print(
            f"- **Replies:** {t['replies']} | **Participants:** {t['participants']}"
        )
        print(f"- **URL:** {t['url']}")
        print()

        if t["thread_id"]:
            print(f"Fetching thread content...", file=sys.stderr)
            emails = fetch_thread_emails(t["thread_id"], max_emails=3)
            if emails:
                for j, body in enumerate(emails):
                    label = "**Opening message:**" if j == 0 else f"**Reply {j}:**"
                    print(label)
                    print()
                    # Indent body lines for readability
                    for line in body.splitlines():
                        print(f"  {line}")
                    print()
            else:
                print(f"*(could not fetch email content)*\n")


if __name__ == "__main__":
    main()
