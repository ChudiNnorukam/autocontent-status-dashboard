from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import snscrape.modules.twitter as sntwitter


@dataclass
class TweetSample:
    """Lightweight representation of an X post."""

    id: int
    date: datetime
    content: str
    like_count: int
    reply_count: int
    retweet_count: int
    url: str
    is_retweet: bool
    is_reply: bool

    def to_dict(self) -> dict:
        return asdict(self)


def fetch_user_tweets(
    username: str,
    limit: int = 500,
    include_retweets: bool = False,
    include_replies: bool = False,
) -> List[TweetSample]:
    """Fetch tweets for the provided username using snscrape."""

    query = f"from:{username}"
    scraper = sntwitter.TwitterSearchScraper(query)
    tweets: List[TweetSample] = []

    for index, tweet in enumerate(scraper.get_items()):
        if limit and index >= limit:
            break

        is_retweet = getattr(tweet, "retweetedTweet", None) is not None
        is_reply = tweet.inReplyToTweetId is not None

        if not include_retweets and is_retweet:
            continue
        if not include_replies and is_reply:
            continue

        tweets.append(
            TweetSample(
                id=int(tweet.id),
                date=tweet.date.replace(tzinfo=None),
                content=str(tweet.content).strip(),
                like_count=int(tweet.likeCount or 0),
                reply_count=int(tweet.replyCount or 0),
                retweet_count=int(tweet.retweetCount or 0),
                url=str(tweet.url),
                is_retweet=is_retweet,
                is_reply=is_reply,
            )
        )

    return tweets


def tweets_to_dataframe(tweets: Iterable[TweetSample]) -> pd.DataFrame:
    """Convert tweet samples to a pandas DataFrame sorted by date."""

    data = [tweet.to_dict() for tweet in tweets]
    df = pd.DataFrame(data)
    if not df.empty:
        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


def export_tweets_to_csv(tweets: Iterable[TweetSample], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = tweets_to_dataframe(tweets)
    df.to_csv(path, index=False)
