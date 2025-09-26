from __future__ import annotations

import json
import random
from dataclasses import dataclass
from textwrap import dedent
from typing import List, Sequence

from .config import get_settings
from .voice_model import VoiceProfile

try:  # Optional because OpenAI SDK might not be installed
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore


@dataclass
class GeneratedPost:
    text: str
    topic: str | None = None
    notes: str | None = None


SYSTEM_PROMPT = """You are an assistant that writes X/Twitter posts.
Keep tweets within 280 characters, high-signal, and aligned to the provided voice profile.
Use the provided examples as inspiration but do not copy them verbatim.
"""


FALLBACK_TEMPLATES = [
    "{hook} {insight} {cta}",
    "{hook}\n\n{insight}\n\n{cta}",
    "{insight} {proof} {cta}",
]

FALLBACK_HOOKS = [
    "New lesson from building my brand:",
    "I used to think X was about Y. Not anymore.",
    "Most people forget this:",
]

FALLBACK_INSIGHTS = [
    "Consistency beats inspiration.",
    "Deep work compounds when you make it public.",
    "Every ambitious move starts with a tiny uncomfortable test.",
]

FALLBACK_PROOF = [
    "Shipping threads weekly unlocked two dream partnerships.",
    "Audience growth climbed 40% after leaning into video snippets.",
    "Every viral post mapped to audience research I almost skipped.",
]

FALLBACK_CTA = [
    "Try it this week and tell me how it lands.",
    "More experiments coming—stay tuned.",
    "Share this with someone chasing the same goal.",
]


def _llm_generate(profile: VoiceProfile, topics: Sequence[str], count: int, temperature: float | None = None) -> List[GeneratedPost]:
    settings = get_settings()
    openai_config = settings.get_openai_config()
    if openai_config is None or OpenAI is None:
        raise RuntimeError("OpenAI client is not configured.")

    client = OpenAI(api_key=openai_config.api_key.get_secret_value())
    temp = temperature if temperature is not None else getattr(openai_config, "temperature", 0.3)

    topic_block = "\n".join(f"- {topic}" for topic in topics) if topics else "- General updates"
    examples = "\n\n".join(profile.high_performing_examples)

    response = client.chat.completions.create(
        model=openai_config.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": dedent(
                    f"""
                    Voice profile summary:
                    {profile.summary}

                    Engagement metrics: {profile.metrics}
                    Signature hashtags: {', '.join(profile.hashtags[:5]) or 'None'}
                    Common emoji: {' '.join(profile.emoji[:5]) or 'None'}

                    High performing examples:
                    {examples or 'None provided'}

                    Please craft {count} distinct X posts for these topics:
                    {topic_block}

                    Return JSON keyed by 'posts' -> list[{{text, topic, notes}}].
                    """
                ).strip(),
            },
        ],
        temperature=temp,
        response_format={"type": "json_object"},
    )

    content_block = response.choices[0].message.content or ""
    payload = json.loads(content_block)
    posts_payload = payload.get("posts") if isinstance(payload, dict) else payload

    posts: List[GeneratedPost] = []
    for item in posts_payload or []:
        if not isinstance(item, dict):
            continue
        text = item.get("text", "").strip()
        if not text:
            continue
        posts.append(
            GeneratedPost(
                text=text,
                topic=item.get("topic"),
                notes=item.get("notes"),
            )
        )

    return posts


def _fallback_generate(profile: VoiceProfile, topics: Sequence[str], count: int) -> List[GeneratedPost]:
    posts: List[GeneratedPost] = []
    topics_cycle = list(topics) or [None]

    for index in range(count):
        topic = topics_cycle[index % len(topics_cycle)] if topics_cycle and topics_cycle[0] else None
        template = random.choice(FALLBACK_TEMPLATES)
        tweet = template.format(
            hook=random.choice(FALLBACK_HOOKS),
            insight=random.choice(FALLBACK_INSIGHTS),
            proof=random.choice(FALLBACK_PROOF),
            cta=random.choice(FALLBACK_CTA),
        )
        if topic:
            tweet = f"{tweet}\n\n#{topic.replace(' ', '')}"
        posts.append(GeneratedPost(text=tweet.strip(), topic=topic))

    return posts


def generate_posts(
    profile: VoiceProfile,
    topics: Sequence[str] | None = None,
    count: int = 5,
    prefer_llm: bool = True,
    temperature: float | None = None,
) -> List[GeneratedPost]:
    topics = list(topics or [])
    if prefer_llm:
        try:
            llm_posts = _llm_generate(profile, topics, count, temperature=temperature)
            if llm_posts:
                return llm_posts
        except Exception:
            pass
    return _fallback_generate(profile, topics, count)
