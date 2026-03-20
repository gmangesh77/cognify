#!/usr/bin/env python3
"""Parse PROGRESS.md and generate a standalone HTML dashboard."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


def parse_progress(text: str) -> list[dict[str, object]]:
    """Extract epics and tickets from PROGRESS.md."""
    epics: list[dict[str, object]] = []
    current_epic: dict[str, object] | None = None

    for line in text.splitlines():
        epic_match = re.match(
            r"^## (Epic \d+): (.+)$", line,
        )
        if epic_match:
            current_epic = {
                "id": epic_match.group(1),
                "name": epic_match.group(2),
                "tickets": [],
            }
            epics.append(current_epic)
            continue

        if current_epic is None:
            continue

        ticket_match = re.match(
            r"^\| (\S+)\s+\| (.+?)\s+\| (\w[\w ]*\w)\s+\|",
            line,
        )
        if not ticket_match:
            continue
        ticket_id = ticket_match.group(1).strip()
        if ticket_id in ("Ticket", "---", "------"):
            continue
        tickets = current_epic["tickets"]
        assert isinstance(tickets, list)
        tickets.append({
            "id": ticket_id,
            "title": ticket_match.group(2).strip(),
            "status": ticket_match.group(3).strip(),
        })

    return epics


def parse_story_points(text: str) -> dict[str, int]:
    """Extract story points per ticket from BACKLOG.md."""
    points: dict[str, int] = {}
    current_ticket = ""
    for line in text.splitlines():
        ticket_match = re.match(
            r"^### (\S+):", line,
        )
        if ticket_match:
            current_ticket = ticket_match.group(1)
        sp_match = re.match(
            r"^- \*\*Story Points\*\*:\s*(\d+)",
            line,
        )
        if sp_match and current_ticket:
            points[current_ticket] = int(sp_match.group(1))
    return points


def compute_stats(
    epics: list[dict[str, object]],
    points: dict[str, int],
) -> dict[str, object]:
    """Compute overall project statistics."""
    total = 0
    done = 0
    in_progress = 0
    backlog = 0
    total_sp = 0
    done_sp = 0

    for epic in epics:
        tickets = epic["tickets"]
        assert isinstance(tickets, list)
        for t in tickets:
            assert isinstance(t, dict)
            total += 1
            status = str(t["status"])
            tid = str(t["id"])
            sp = points.get(tid, 0)
            total_sp += sp
            if status == "Done":
                done += 1
                done_sp += sp
            elif status == "In Progress":
                in_progress += 1
            else:
                backlog += 1

    return {
        "total": total,
        "done": done,
        "in_progress": in_progress,
        "backlog": backlog,
        "total_sp": total_sp,
        "done_sp": done_sp,
        "pct": round(done / total * 100) if total else 0,
        "sp_pct": round(done_sp / total_sp * 100) if total_sp else 0,
    }


def build_html(
    epics: list[dict[str, object]],
    points: dict[str, int],
    stats: dict[str, object],
) -> str:
    """Generate the full HTML dashboard."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    epic_cards = []
    for epic in epics:
        tickets = epic["tickets"]
        assert isinstance(tickets, list)
        total = len(tickets)
        done = sum(
            1 for t in tickets if str(t["status"]) == "Done"  # type: ignore[index]
        )
        pct = round(done / total * 100) if total else 0

        epic_complete = " complete" if done == total else ""
        bar_class = "bar-done" if done == total else "bar-partial"

        rows = []
        for t in tickets:
            assert isinstance(t, dict)
            status = str(t["status"])
            s_class = status.lower().replace(" ", "-")
            sp = points.get(str(t["id"]), 0)
            sp_display = f"{sp} SP" if sp else ""
            rows.append(
                f'<tr class="{s_class}">'
                f'<td class="ticket-id">{t["id"]}</td>'
                f'<td>{t["title"]}</td>'
                f'<td><span class="badge {s_class}">{status}</span></td>'
                f'<td class="sp">{sp_display}</td>'
                f"</tr>"
            )

        table_rows = "\n            ".join(rows)
        epic_cards.append(f"""
    <div class="epic-card{epic_complete}">
      <div class="epic-header">
        <div class="epic-title">
          <span class="epic-id">{epic["id"]}</span>
          {epic["name"]}
        </div>
        <span class="epic-count">{done}/{total}</span>
      </div>
      <div class="progress-bar">
        <div class="{bar_class}" style="width:{pct}%"></div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Ticket</th><th>Title</th>
            <th>Status</th><th>SP</th>
          </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
      </table>
    </div>""")

    cards_html = "\n".join(epic_cards)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cognify Progress Dashboard</title>
<style>
  :root {{
    --bg: #0f1117;
    --card: #1a1d27;
    --border: #2a2d3a;
    --text: #e4e4e7;
    --muted: #71717a;
    --accent: #6366f1;
    --green: #22c55e;
    --yellow: #eab308;
    --blue: #3b82f6;
    --red: #ef4444;
    --bar-bg: #27272a;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
      Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    max-width: 1200px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 4px;
  }}
  .subtitle {{
    color: var(--muted);
    font-size: 13px;
    margin-bottom: 24px;
  }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
  }}
  .stat-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
  }}
  .stat-label {{
    font-size: 12px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
  }}
  .stat-value {{
    font-size: 28px;
    font-weight: 700;
  }}
  .stat-value.green {{ color: var(--green); }}
  .stat-value.yellow {{ color: var(--yellow); }}
  .stat-value.blue {{ color: var(--blue); }}
  .stat-value.accent {{ color: var(--accent); }}
  .overall-bar {{
    background: var(--bar-bg);
    border-radius: 8px;
    height: 12px;
    margin-bottom: 32px;
    overflow: hidden;
  }}
  .overall-fill {{
    height: 100%;
    border-radius: 8px;
    background: linear-gradient(90deg, var(--accent), var(--green));
    transition: width 0.5s;
  }}
  .epic-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 16px;
    overflow: hidden;
  }}
  .epic-card.complete {{
    border-color: #166534;
  }}
  .epic-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 16px;
  }}
  .epic-title {{
    font-weight: 600;
    font-size: 15px;
  }}
  .epic-id {{
    color: var(--accent);
    margin-right: 8px;
    font-size: 13px;
    font-weight: 500;
  }}
  .epic-count {{
    color: var(--muted);
    font-size: 13px;
    font-weight: 500;
  }}
  .progress-bar {{
    height: 4px;
    background: var(--bar-bg);
    margin: 0 16px 8px;
    border-radius: 2px;
    overflow: hidden;
  }}
  .bar-done {{
    height: 100%;
    background: var(--green);
    border-radius: 2px;
  }}
  .bar-partial {{
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  th {{
    text-align: left;
    padding: 6px 16px;
    color: var(--muted);
    font-weight: 500;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-top: 1px solid var(--border);
  }}
  td {{
    padding: 8px 16px;
    border-top: 1px solid var(--border);
  }}
  .ticket-id {{
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 12px;
    color: var(--muted);
    white-space: nowrap;
  }}
  .sp {{
    font-size: 12px;
    color: var(--muted);
    text-align: right;
    white-space: nowrap;
  }}
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }}
  .badge.done {{
    background: #166534;
    color: #86efac;
  }}
  .badge.in-progress {{
    background: #854d0e;
    color: #fde047;
  }}
  .badge.planned {{
    background: #1e3a5f;
    color: #93c5fd;
  }}
  .badge.backlog {{
    background: #27272a;
    color: #a1a1aa;
  }}
  tr.done td {{ opacity: 0.7; }}
  tr.backlog td {{ opacity: 0.5; }}
</style>
</head>
<body>
  <h1>Cognify Progress Dashboard</h1>
  <p class="subtitle">Generated {now} from PROGRESS.md</p>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">Completed</div>
      <div class="stat-value green">{stats["done"]}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">In Progress</div>
      <div class="stat-value yellow">{stats["in_progress"]}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Backlog</div>
      <div class="stat-value blue">{stats["backlog"]}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Total Tickets</div>
      <div class="stat-value">{stats["total"]}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Story Points Done</div>
      <div class="stat-value accent">{stats["done_sp"]}/{stats["total_sp"]}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Completion</div>
      <div class="stat-value green">{stats["pct"]}%</div>
    </div>
  </div>

  <div class="overall-bar">
    <div class="overall-fill" style="width:{stats["pct"]}%"></div>
  </div>

{cards_html}

</body>
</html>"""


def main() -> None:
    """Entry point: parse markdown files, generate dashboard."""
    base = Path(__file__).parent
    progress = (base / "PROGRESS.md").read_text(encoding="utf-8")
    backlog = (base / "BACKLOG.md").read_text(encoding="utf-8")

    epics = parse_progress(progress)
    points = parse_story_points(backlog)
    stats = compute_stats(epics, points)
    html = build_html(epics, points, stats)

    out = base / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"Dashboard generated: {out}")


if __name__ == "__main__":
    main()
