# Personalized X / Twitter Autoposter

A Python toolkit that learns the voice of `@chudinnorukam`, drafts new posts that stay on brand, schedules them automatically, and can publish them to X/Twitter.

## Features
- **Voice training**: scrapes historical tweets and builds a reusable style profile.
- **Content generation**: produces new tweets aligned with the voice profile using OpenAI (if configured) or an offline fallback template system.
- **Scheduling**: assigns posts to future time slots that respect quiet hours and minimum gaps between tweets.
- **Autoposting**: pushes scheduled posts live through the X API, with optional dry-run mode for safety.
- **CLI workflows**: one-line commands to train, generate, schedule, and run the scheduler loop.

## Quick Start
1. **Install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Create a `.env` file** (see [Environment Variables](#environment-variables)).

3. **Train the voice profile**
   ```bash
   x-autoposter train --limit 400 --include-replies
   ```

4. **Generate and schedule posts**
   ```bash
   x-autoposter schedule --topic "AI branding" --topic "Founder lessons" --count 6
   ```

5. **Run the scheduler (dry run first!)**
   ```bash
   x-autoposter run --dry-run
   ```
   Remove `--dry-run` when you are ready to publish for real.

## CLI Overview
| Command | Purpose |
| --- | --- |
| `x-autoposter train` | Fetch tweets and rebuild the voice profile. |
| `x-autoposter generate` | Generate posts and save them as a content plan. |
| `x-autoposter schedule` | Generate posts (if needed) and enqueue them for posting. |
| `x-autoposter queue` | View the current posting queue. |
| `x-autoposter process` | Process due posts one time (useful for cron jobs). |
| `x-autoposter run` | Launch the continuous scheduler loop. |
| `x-autoposter orchestrate` | Run train → generate → schedule sequentially. |

## Environment Variables
Create a `.env` file in the project root with these keys:

```dotenv
# Required
X_HANDLE=chudinnorukam

# Required for posting
X_API_KEY=...
X_API_SECRET=...
X_ACCESS_TOKEN=...
X_ACCESS_TOKEN_SECRET=...

# Optional: unlocks LLM-powered generation
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini

# Optional scheduling tweaks
TIMEZONE=America/New_York
PREFERRED_POSTING_HOURS=[9,12,18]
MIN_HOURS_BETWEEN_POSTS=6
```

> Tip: the CLI automatically creates `data/` and stores artifacts like the voice profile, content plan, queue, and exports of historical tweets.

## Architectural Notes
- **`autoposter/config.py`** centralizes environment configuration with validation.
- **`autoposter/data_fetcher.py`** uses `snscrape` to collect tweets without rate limits.
- **`autoposter/voice_model.py`** extracts voice metrics, high-performing examples, and style cues.
- **`autoposter/content_generator.py`** produces candidate tweets with an LLM-first, template-fallback strategy.
- **`autoposter/scheduler.py`** manages the posting queue, assigns time slots, and runs a polling scheduler.
- **`autoposter/poster.py`** wraps Tweepy for authenticated posting (with dry-run support).
- **`autoposter/workflows.py`** stitches the components into higher-level pipelines for the CLI.

## Context Engineering Best Practices
- **Fresh training data**: re-run `train` weekly so the voice profile keeps up with new themes.
- **Topic framing**: pass focused `--topic` prompts to guide each batch (e.g., product launch, founder mindset, AI trends).
- **Human-in-the-loop**: inspect `data/content_plan.json` and `data/post_queue.json` before going live; tweak text or schedule where needed.
- **Staggered rollouts**: use `--dry-run` on the scheduler until you trust the outputs, then flip it live.
- **Version the voice**: store dated copies of the voice profile to compare how your tone evolves.

## Safety Checklist
- Test with `--dry-run` to verify queue processing without posting.
- Lock down your `.env` (never commit credentials).
- Monitor X API rate limits if you automate aggressive posting cadences.
- Consider adding sentiment or NSFW filters before publishing.

## Next Steps
- Add analytics (likes, engagement deltas) to inform future generations.
- Expand the generator with long-form threads or media attachments.
- Connect to additional LLM providers or fine-tuned models for tighter voice control.
