"""Append hashtags to scheduled posts using a predefined 30-day calendar.

The schedule is based on the strategy provided: 3 posts per day for 30 days.
It keeps `#BuildInPublic` as the anchor hashtag and rotates supporting tags.

Running this script updates both ``data/post_queue.json`` and
``data/content_plan.json`` in-place so the text fields include the selected
hashtags.

Usage::

    python scripts/apply_hashtag_schedule.py

After running, review the modified JSON (and optionally commit the changes).
"""

from __future__ import annotations

import json
from pathlib import Path

from datetime import datetime
from zoneinfo import ZoneInfo

QUEUE_PATH = Path("data/post_queue.json")
PLAN_PATH = Path("data/content_plan.json")


HASHTAG_SCHEDULE = [
    [("BuildInPublic", "Startups"), ("BuildInPublic", "Learning"), ("BuildInPublic", "ProductDesign")],
    [("BuildInPublic", "Innovation"), ("BuildInPublic", "Mistakes"), ("BuildInPublic", "TechNews")],
    [("BuildInPublic", "Entrepreneurship"), ("BuildInPublic", "Process"), ("BuildInPublic", "StartupLife")],
    [("BuildInPublic", "Learning"), ("BuildInPublic", "BusinessGrowth"), ("BuildInPublic", "Innovation")],
    [("BuildInPublic", "ProductDesign"), ("BuildInPublic", "Mistakes"), ("BuildInPublic", "Startups")],
    [("BuildInPublic", "TechNews"), ("BuildInPublic", "Learning"), ("BuildInPublic", "Entrepreneurship")],
    [("BuildInPublic", "Process"), ("BuildInPublic", "BusinessGrowth"), ("BuildInPublic", "StartupLife")],
    [("BuildInPublic", "Innovation"), ("BuildInPublic", "Mistakes"), ("BuildInPublic", "Startups")],
    [("BuildInPublic", "ProductDesign"), ("BuildInPublic", "Learning"), ("BuildInPublic", "TechNews")],
    [("BuildInPublic", "Entrepreneurship"), ("BuildInPublic", "Process"), ("BuildInPublic", "Innovation")],
    [("BuildInPublic", "BusinessGrowth"), ("BuildInPublic", "Mistakes"), ("BuildInPublic", "Startups")],
    [("BuildInPublic", "Learning"), ("BuildInPublic", "ProductDesign"), ("BuildInPublic", "TechNews")],
    [("BuildInPublic", "Entrepreneurship"), ("BuildInPublic", "Process"), ("BuildInPublic", "Innovation")],
    [("BuildInPublic", "BusinessGrowth"), ("BuildInPublic", "Mistakes"), ("BuildInPublic", "StartupLife")],
    [("BuildInPublic", "Startups"), ("BuildInPublic", "Learning"), ("BuildInPublic", "ProductDesign")],
    [("BuildInPublic", "TechNews"), ("BuildInPublic", "Entrepreneurship"), ("BuildInPublic", "Innovation")],
    [("BuildInPublic", "Process"), ("BuildInPublic", "BusinessGrowth"), ("BuildInPublic", "Mistakes")],
    [("BuildInPublic", "Learning"), ("BuildInPublic", "StartupLife"), ("BuildInPublic", "TechNews")],
    [("BuildInPublic", "ProductDesign"), ("BuildInPublic", "Entrepreneurship"), ("BuildInPublic", "Startups")],
    [("BuildInPublic", "Innovation"), ("BuildInPublic", "Process"), ("BuildInPublic", "Learning")],
    [("BuildInPublic", "BusinessGrowth"), ("BuildInPublic", "Mistakes"), ("BuildInPublic", "TechNews")],
    [("BuildInPublic", "StartupLife"), ("BuildInPublic", "ProductDesign"), ("BuildInPublic", "Entrepreneurship")],
    [("BuildInPublic", "Learning"), ("BuildInPublic", "Startups"), ("BuildInPublic", "Innovation")],
    [("BuildInPublic", "Mistakes"), ("BuildInPublic", "TechNews"), ("BuildInPublic", "BusinessGrowth")],
    [("BuildInPublic", "Process"), ("BuildInPublic", "StartupLife"), ("BuildInPublic", "ProductDesign")],
    [("BuildInPublic", "Entrepreneurship"), ("BuildInPublic", "Learning"), ("BuildInPublic", "Innovation")],
    [("BuildInPublic", "Startups"), ("BuildInPublic", "TechNews"), ("BuildInPublic", "Mistakes")],
    [("BuildInPublic", "BusinessGrowth"), ("BuildInPublic", "ProductDesign"), ("BuildInPublic", "Process")],
    [("BuildInPublic", "StartupLife"), ("BuildInPublic", "Entrepreneurship"), ("BuildInPublic", "Learning")],
    [("BuildInPublic", "Innovation"), ("BuildInPublic", "TechNews"), ("BuildInPublic", "Startups")],
]


def format_hashtags(tags: tuple[str, str]) -> str:
    return ' '.join(f"#{tag}" if not tag.startswith('#') else tag for tag in tags)


def apply_schedule(queue: list[dict], plan_posts: list[dict]) -> None:
    ordered_indices = sorted(range(len(queue)), key=lambda i: queue[i]['scheduled_time'])
    for position, idx in enumerate(ordered_indices):
        schedule_day = position // 3
        slot_index = position % 3
        tags = HASHTAG_SCHEDULE[schedule_day % len(HASHTAG_SCHEDULE)][slot_index]
        hashtag_text = format_hashtags(tags)

        for collection in (queue[idx], plan_posts[idx]):
            text = collection['text'].rstrip()
            if hashtag_text.lower() in text.lower():
                continue
            collection['text'] = f"{text}\n\n{hashtag_text}"


def main() -> None:
    queue = json.loads(QUEUE_PATH.read_text(encoding='utf-8'))
    plan = json.loads(PLAN_PATH.read_text(encoding='utf-8'))

    if not isinstance(plan.get('posts'), list) or len(plan['posts']) != len(queue):
        raise SystemExit('Content plan and queue must contain matching number of posts.')

    apply_schedule(queue, plan['posts'])

    QUEUE_PATH.write_text(json.dumps(queue, indent=2) + '\n', encoding='utf-8')
    plan['generated_at'] = datetime.now(ZoneInfo('America/New_York')).isoformat()
    PLAN_PATH.write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')

    print(f"Updated {len(queue)} queue entries with scheduled hashtags.")


if __name__ == '__main__':
    main()
