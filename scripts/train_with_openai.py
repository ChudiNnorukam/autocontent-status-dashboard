"""Generate a synthetic voice profile using the OpenAI Responses API.

Fallback option for environments where snscrape/Twitter APIs are unavailable.
The script asks the LLM to infer a brand voice for @chudinnorukam and writes
the resulting profile to ``data/voice_profile.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "OpenAI SDK not installed. Run `pip install openai` inside the virtualenv."
    ) from exc

from autoposter.config import get_settings
from autoposter.voice_model import VoiceProfile, save_voice_profile


SYSTEM_PROMPT = """You are an editorial analyst that reverse-engineers social media voice profiles.
You respond with clean JSON only (utf-8 safe, no trailing commentary).
"""

USER_PROMPT = """You are auditing the public X/Twitter presence of Chudi Nnorukam (@chudinnorukam).
Construct a plausible voice profile using your knowledge of startup founders, AI branding, and creator-led growth.

Requirements:
- Provide a concise `summary` (~3 sentences) capturing tone, positioning, and recurring themes.
- `metrics` must include numeric fields: `avg_length`, `median_length`, `avg_like`, `avg_engagement`, `tweet_count` (use reasonable estimates, floats allowed).
- List at least 5 items for `hashtags` (strings without #), `mentions` (handle names without @), and `emoji` (single characters or short combos).
- Supply 5 high-performing example tweets under `high_performing_examples`, each <= 280 chars, high-signal, grounded in AI branding, founder lessons, or audience-building tactics.

Respond with a JSON object matching this schema:
{
  "summary": string,
  "metrics": {
    "avg_length": number,
    "median_length": number,
    "avg_like": number,
    "avg_engagement": number,
    "tweet_count": integer
  },
  "hashtags": [string, ...],
  "mentions": [string, ...],
  "emoji": [string, ...],
  "high_performing_examples": [string, ...]
}

Do not include the @ or # characters in the list values. Keep JSON valid.
"""


def main() -> None:
    load_dotenv()
    settings = get_settings()
    openai_config = settings.get_openai_config()
    if openai_config is None:
        raise SystemExit("OPENAI_API_KEY not configured. Populate it in your .env file.")

    client = OpenAI(api_key=openai_config.api_key.get_secret_value())

    response = client.chat.completions.create(
        model=openai_config.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    try:
        content_block = response.choices[0].message.content or ""
        payload = json.loads(content_block)
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Unexpected response payload: {exc}") from exc

    profile = VoiceProfile(
        summary=payload.get("summary", ""),
        metrics=payload.get("metrics", {}),
        hashtags=payload.get("hashtags", []),
        mentions=payload.get("mentions", []),
        emoji=payload.get("emoji", []),
        high_performing_examples=payload.get("high_performing_examples", []),
    )

    save_voice_profile(profile, settings.voice_profile_path)

    print("Voice profile saved to", settings.voice_profile_path)
    print("Summary:", profile.summary)
    print("High-performing sample:", profile.high_performing_examples[:1])


if __name__ == "__main__":  # pragma: no cover
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
