from __future__ import annotations

from contextlib import closing
from hashlib import sha256
from datetime import datetime

import typer

from .config import get_settings
from .scheduler import process_queue_once, start_scheduler
from .storage import QueueRepository, bootstrap_from_json
from .workflows import (
    end_to_end_run,
    generate_content_plan,
    schedule_generated_posts,
    train_voice,
)
from .data_fetcher import fetch_user_tweets

app = typer.Typer(add_completion=False, help="Personalized X/Twitter autoposter CLI")


@app.command()
def train(
    limit: int = typer.Option(500, help="Number of tweets to fetch for training."),
    include_retweets: bool = typer.Option(False, help="Include retweets in the voice model."),
    include_replies: bool = typer.Option(False, help="Include replies in the voice model."),
) -> None:
    """Fetch latest tweets and refresh the voice profile."""

    profile = train_voice(limit=limit, include_retweets=include_retweets, include_replies=include_replies)
    typer.echo("Voice profile saved to: " + str(get_settings().voice_profile_path))
    typer.echo("Summary: " + profile.summary)


@app.command()
def generate(
    topics: list[str] = typer.Option(
        [],
        help="Topic(s) to guide generation.",
        show_default=False,
    ),
    count: int = typer.Option(5, help="Number of posts to generate."),
    prefer_llm: bool = typer.Option(True, help="Use OpenAI if credentials are configured."),
) -> None:
    """Generate posts aligned with the trained voice and store the content plan."""

    posts = generate_content_plan(topics=topics or None, count=count, prefer_llm=prefer_llm)
    typer.echo(f"Generated {len(posts)} posts. Saved plan to {get_settings().content_plan_path}")


@app.command()
def schedule(
    topics: list[str] = typer.Option(
        [],
        help="Topic(s) for the batch.",
        show_default=False,
    ),
    count: int = typer.Option(5, help="Number of posts to create and schedule."),
    prefer_llm: bool = typer.Option(True, help="Use OpenAI if available."),
) -> None:
    """Generate posts (if needed) and schedule them into the posting queue."""

    posts = generate_content_plan(topics=topics or None, count=count, prefer_llm=prefer_llm)
    scheduled = schedule_generated_posts(posts)
    typer.echo(f"Scheduled {len(scheduled)} posts. Queue at {get_settings().post_queue_path}")


@app.command("queue")
def show_queue() -> None:
    """Display the current posting queue."""

    settings = get_settings()
    repo = QueueRepository(settings.queue_db_path)
    bootstrap_from_json(repo, settings.post_queue_path)

    with closing(repo._connect()) as conn:
        rows = conn.execute("SELECT * FROM posts ORDER BY scheduled_at ASC").fetchall()
    if not rows:
        typer.echo("Queue is empty. Schedule posts first.")
        raise typer.Exit(code=0)

    for row in rows:
        typer.echo(
            f"[{row['status']}] {row['scheduled_at']} - {row['text'][:100]}"
        )


@app.command()
def process(
    dry_run: bool = typer.Option(True, help="Do not post, just mark items as processed."),
) -> None:
    """Process any posts that are due right now."""

    process_queue_once(dry_run=dry_run)
    typer.echo("Queue processed.")


@app.command()
def backfill(
    limit: int = typer.Option(200, help="Number of recent posts to scan from your timeline."),
    include_retweets: bool = typer.Option(False, help="Include retweets in backfill."),
    include_replies: bool = typer.Option(False, help="Include replies in backfill."),
    dry_run: bool = typer.Option(True, help="Preview without writing to sent_history."),
) -> None:
    """Backfill sent_history from your public timeline to improve de-duplication.

    Uses snscrape to fetch recent posts for the configured username and records
    their text hashes into the sent_history table. This helps the scheduler
    detect duplicates even in clean CI environments.
    """
    settings = get_settings()
    username = settings.username
    tweets = fetch_user_tweets(
        username=username,
        limit=limit,
        include_retweets=include_retweets,
        include_replies=include_replies,
    )
    repo = QueueRepository(settings.queue_db_path)
    # ensure tables exist
    bootstrap_from_json(repo, settings.post_queue_path)

    added = 0
    skipped = 0
    for t in tweets:
        text = (t.content or "").strip()
        if not text:
            skipped += 1
            continue
        h = sha256(text.encode("utf-8")).hexdigest()
        if dry_run:
            # count if it would be new
            if repo.has_sent_hash(h):
                skipped += 1
            else:
                added += 1
        else:
            # Upsert; record_sent_history handles conflict on hash
            repo.record_sent_history(
                post_id=str(t.id),
                text=text,
                hash_value=h,
                posted_at=t.date,
            )
            added += 1
    typer.echo(
        f"Backfill {'(dry-run) ' if dry_run else ''}complete. username={username} scanned={len(tweets)} would_add={added if dry_run else added} skipped={skipped}"
    )


@app.command("run")
def run_scheduler(
    poll_seconds: int = typer.Option(60, help="How frequently to check for due posts."),
    dry_run: bool = typer.Option(True, help="Log posts instead of publishing."),
) -> None:
    """Launch the persistent scheduler loop."""

    typer.echo("Starting scheduler. Press Ctrl+C to stop.")
    start_scheduler(poll_seconds=poll_seconds, dry_run=dry_run)


@app.command()
def orchestrate(
    topics: list[str] = typer.Option(
        [],
        help="Topics to cover.",
        show_default=False,
    ),
    count: int = typer.Option(5, help="Number of posts to generate and schedule."),
    prefer_llm: bool = typer.Option(True, help="Use OpenAI if configured."),
    include_retweets: bool = typer.Option(False, help="Include retweets when training."),
    include_replies: bool = typer.Option(False, help="Include replies when training."),
) -> None:
    """Run train + generate + schedule in one command."""

    scheduled = end_to_end_run(
        topics=topics or None,
        count=count,
        prefer_llm=prefer_llm,
        include_retweets=include_retweets,
        include_replies=include_replies,
    )
    typer.echo(f"End-to-end complete. Scheduled {len(scheduled)} posts.")


if __name__ == "__main__":
    app()
