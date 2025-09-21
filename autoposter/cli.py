from __future__ import annotations

import json


import typer
from .config import get_settings
from .scheduler import process_queue_once, start_scheduler
from .workflows import (
    end_to_end_run,
    generate_content_plan,
    schedule_generated_posts,
    train_voice,
)

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
    path = settings.post_queue_path
    if not path.exists():
        typer.echo("Queue file does not exist yet. Run the schedule command first.")
        raise typer.Exit(code=0)

    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data:
        typer.echo(
            f"[{item.get('status', 'pending')}] {item.get('scheduled_time')} - {item.get('text')[:100]}"
        )


@app.command()
def process(
    dry_run: bool = typer.Option(False, help="Do not post, just mark items as processed."),
) -> None:
    """Process any posts that are due right now."""

    process_queue_once(dry_run=dry_run)
    typer.echo("Queue processed.")


@app.command("run")
def run_scheduler(
    poll_seconds: int = typer.Option(60, help="How frequently to check for due posts."),
    dry_run: bool = typer.Option(False, help="Log posts instead of publishing."),
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
