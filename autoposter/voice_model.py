from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

HASHTAG_PATTERN = re.compile(r'(?i)#\w+')
MENTION_PATTERN = re.compile(r'(?i)@\w+')
EMOJI_PATTERN = re.compile(
    '[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]',
    flags=re.UNICODE,
)


@dataclass
class VoiceProfile:
    summary: str
    metrics: dict
    hashtags: list[str]
    mentions: list[str]
    emoji: list[str]
    high_performing_examples: list[str]

    def to_json(self) -> str:
        return json.dumps(
            {
                'summary': self.summary,
                'metrics': self.metrics,
                'hashtags': self.hashtags,
                'mentions': self.mentions,
                'emoji': self.emoji,
                'high_performing_examples': self.high_performing_examples,
            },
            indent=2,
            ensure_ascii=False,
        )

    def to_dict(self) -> dict:
        return json.loads(self.to_json())


def _extract_top_items(counter: Counter[str], top_k: int = 10) -> list[str]:
    return [item for item, _ in counter.most_common(top_k)]


def build_voice_profile(df: pd.DataFrame, top_k: int = 10) -> VoiceProfile:
    if df.empty:
        raise ValueError('No tweets available to build voice profile.')

    hashtags = Counter()
    mentions = Counter()
    emoji_counter = Counter()

    for text in df['content'].astype(str):
        hashtags.update([token.lower() for token in HASHTAG_PATTERN.findall(text)])
        mentions.update([token.lower() for token in MENTION_PATTERN.findall(text)])
        emoji_counter.update(EMOJI_PATTERN.findall(text))

    avg_length = df['content'].str.len().mean()
    median_length = df['content'].str.len().median()
    avg_like = df['like_count'].mean()
    avg_engagement = (df['like_count'] + df['reply_count'] + df['retweet_count']).mean()

    top_hashtags = _extract_top_items(hashtags, top_k)
    top_mentions = _extract_top_items(mentions, top_k)
    top_emoji = _extract_top_items(emoji_counter, top_k)

    high_performing = (
        df.assign(engagement=df['like_count'] + df['reply_count'] + df['retweet_count'])
        .sort_values('engagement', ascending=False)
        .head(5)['content']
        .tolist()
    )

    summary_parts = [
        f'Average post length ~{avg_length:.0f} characters (median {median_length:.0f}).',
        f'Average engagement score {avg_engagement:.1f} (likes + replies + RTs).',
    ]

    if top_hashtags:
        summary_parts.append('Frequent hashtags: ' + ', '.join(top_hashtags[:5]))
    if top_mentions:
        summary_parts.append('Often mentions: ' + ', '.join(top_mentions[:5]))
    if top_emoji:
        summary_parts.append('Common emoji: ' + ' '.join(top_emoji[:5]))

    summary = ' '.join(summary_parts)

    metrics = {
        'avg_length': avg_length,
        'median_length': median_length,
        'avg_like': avg_like,
        'avg_engagement': avg_engagement,
        'tweet_count': len(df),
    }

    return VoiceProfile(
        summary=summary,
        metrics=metrics,
        hashtags=top_hashtags,
        mentions=top_mentions,
        emoji=top_emoji,
        high_performing_examples=high_performing,
    )


def save_voice_profile(profile: VoiceProfile, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.to_json(), encoding='utf-8')


def load_voice_profile(path: Path) -> VoiceProfile:
    data = json.loads(path.read_text(encoding='utf-8'))
    return VoiceProfile(
        summary=data.get('summary', ''),
        metrics=data.get('metrics', {}),
        hashtags=data.get('hashtags', []),
        mentions=data.get('mentions', []),
        emoji=data.get('emoji', []),
        high_performing_examples=data.get('high_performing_examples', []),
    )
