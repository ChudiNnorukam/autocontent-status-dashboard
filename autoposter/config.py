from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, BaseSettings, Field, SecretStr, validator


class XCredentials(BaseModel):
    api_key: SecretStr
    api_secret: SecretStr
    access_token: SecretStr
    access_token_secret: SecretStr


class OpenAIConfig(BaseModel):
    api_key: SecretStr
    model: str = Field(default="gpt-4o-mini")


class Settings(BaseSettings):
    """Runtime configuration loaded from env or `.env`."""

    username: str = Field(..., env=["X_HANDLE", "USERNAME"])
    timezone: str = Field(default="America/New_York")
    data_dir: Path = Field(default=Path("data"))
    voice_profile_path: Path = Field(default=Path("data/voice_profile.json"))
    content_plan_path: Path = Field(default=Path("data/content_plan.json"))
    post_queue_path: Path = Field(default=Path("data/post_queue.json"))
    scheduling_window_days: int = Field(default=7, ge=1, le=30)
    min_hours_between_posts: float = Field(default=6.0, ge=0.5)
    preferred_posting_hours: list[int] = Field(default_factory=lambda: [9, 12, 18])
    post_lead_time_minutes: int = Field(default=15, ge=0)

    x_api_key: SecretStr | None = Field(default=None, env=["X_API_KEY", "X_TWITTER_API_KEY"])
    x_api_secret: SecretStr | None = Field(default=None, env=["X_API_SECRET", "X_TWITTER_API_SECRET"])
    x_access_token: SecretStr | None = Field(default=None, env=["X_ACCESS_TOKEN", "X_TWITTER_ACCESS_TOKEN"])
    x_access_token_secret: SecretStr | None = Field(
        default=None,
        env=["X_ACCESS_TOKEN_SECRET", "X_TWITTER_ACCESS_TOKEN_SECRET"],
    )

    openai_api_key: SecretStr | None = Field(default=None, env=["OPENAI_API_KEY", "OPENAI_KEY"])
    openai_model: str | None = Field(default=None, env="OPENAI_MODEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("preferred_posting_hours", pre=True)
    def _ensure_int_hours(cls, value: Any) -> list[int]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [int(v) for v in parsed]
            except json.JSONDecodeError:
                pass
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        return [int(v) for v in value]

    @property
    def data_path(self) -> Path:
        return self.data_dir

    def ensure_data_paths(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.voice_profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.content_plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.post_queue_path.parent.mkdir(parents=True, exist_ok=True)

    def has_x_credentials(self) -> bool:
        return all(
            [
                self.x_api_key,
                self.x_api_secret,
                self.x_access_token,
                self.x_access_token_secret,
            ]
        )

    def require_x_credentials(self) -> XCredentials:
        if not self.has_x_credentials():
            raise ValueError("Missing X API credentials. Check your environment variables.")
        return XCredentials(
            api_key=self.x_api_key,  # type: ignore[arg-type]
            api_secret=self.x_api_secret,  # type: ignore[arg-type]
            access_token=self.x_access_token,  # type: ignore[arg-type]
            access_token_secret=self.x_access_token_secret,  # type: ignore[arg-type]
        )

    def get_openai_config(self) -> OpenAIConfig | None:
        if self.openai_api_key is None:
            return None
        return OpenAIConfig(
            api_key=self.openai_api_key,
            model=self.openai_model or "gpt-4o-mini",
        )


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    settings.ensure_data_paths()
    return settings
