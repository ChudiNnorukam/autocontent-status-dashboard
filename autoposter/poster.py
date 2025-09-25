from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import tweepy

from .config import XCredentials, get_settings


@dataclass
class PostResult:
    success: bool
    tweet_id: str | None = None
    error: str | None = None
    dry_run: bool = False


class XPoster:
    """Handles posting tweets via the X API."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        settings = get_settings()
        self.client: tweepy.Client | None = None

        # Dry runs should not require API credentials so developers can test
        # the full workflow without configuring secrets. If credentials are
        # present we still initialize the client so duplicate detection works
        # against the live history when available.
        if dry_run:
            if settings.has_x_credentials():
                self.client = self._build_client(settings.require_x_credentials())
            return

        credentials = settings.require_x_credentials()
        self.client = self._build_client(credentials)

    @staticmethod
    def _build_client(credentials: XCredentials) -> tweepy.Client:
        return tweepy.Client(
            consumer_key=credentials.api_key.get_secret_value(),
            consumer_secret=credentials.api_secret.get_secret_value(),
            access_token=credentials.access_token.get_secret_value(),
            access_token_secret=credentials.access_token_secret.get_secret_value(),
        )

    def post(self, text: str, in_reply_to_id: Optional[str] = None) -> PostResult:
        if self.dry_run:
            return PostResult(success=True, tweet_id=None, dry_run=True)
        if self.client is None:  # pragma: no cover - defensive safety
            raise RuntimeError("Twitter client is not initialized.")
        try:
            response = self.client.create_tweet(
                text=text,
                in_reply_to_tweet_id=in_reply_to_id,
            )
            tweet_id = None
            if hasattr(response, "data") and isinstance(response.data, dict):
                tweet_id = str(response.data.get("id")) if response.data.get("id") else None
            return PostResult(success=True, tweet_id=tweet_id)
        except Exception as exc:  # pragma: no cover - network errors etc
            return PostResult(success=False, error=str(exc))
