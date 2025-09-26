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
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)


class Settings(BaseSettings):
    """Runtime configuration loaded from env or `.env`."""

    username: str = Field(..., env=["X_HANDLE", "USERNAME"])
    timezone: str = Field(default="America/New_York")
    data_dir: Path = Field(default=Path("data"))
    voice_profile_path: Path = Field(default=Path("data/voice_profile.json"))
    content_plan_path: Path = Field(default=Path("data/content_plan.json"))
    post_queue_path: Path = Field(default=Path("data/post_queue.json"))
    queue_db_path: Path = Field(default=Path("data/queue.db"))
    sent_history_path: Path = Field(default=Path("data/sent_history.json"))
    scheduling_window_days: int = Field(default=7, ge=1, le=30)
    min_hours_between_posts: float = Field(default=6.0, ge=0.5)
    preferred_posting_hours: list[int] | None = Field(default=None)
    preferred_posting_times: list[str] = Field(
        default_factory=lambda: ["06:00", "10:00", "15:00", "20:00", "23:30"]
    )
    post_lead_time_minutes: int = Field(default=15, ge=0)
    jit_generation: bool = Field(default=True, env="JIT_GENERATION")

    x_api_key: SecretStr | None = Field(default=None, env=["X_API_KEY", "X_TWITTER_API_KEY"])
    x_api_secret: SecretStr | None = Field(default=None, env=["X_API_SECRET", "X_TWITTER_API_SECRET"])
    x_access_token: SecretStr | None = Field(default=None, env=["X_ACCESS_TOKEN", "X_TWITTER_ACCESS_TOKEN"])
    x_access_token_secret: SecretStr | None = Field(
        default=None,
        env=["X_ACCESS_TOKEN_SECRET", "X_TWITTER_ACCESS_TOKEN_SECRET"],
    )

    openai_api_key: SecretStr | None = Field(default=None, env=["OPENAI_API_KEY", "OPENAI_KEY"])
    openai_model: str | None = Field(default=None, env="OPENAI_MODEL")
    openai_temperature: float | None = Field(default=None, env="OPENAI_TEMPERATURE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("preferred_posting_hours", pre=True)
    def _parse_posting_hours(cls, value: Any) -> list[int] | None:
        if value in (None, "", []):
            return None
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [int(v) for v in parsed]
            except json.JSONDecodeError:
                pass
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        return [int(v) for v in value]

    @validator("preferred_posting_times", pre=True)
    def _parse_posting_times(cls, value: Any, values: dict[str, Any]) -> list[str]:
        if values.get("preferred_posting_hours"):
            return [f"{hour:02d}:00" for hour in values["preferred_posting_hours"]]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    value = parsed
            except json.JSONDecodeError:
                value = [part.strip() for part in value.split(",") if part.strip()]
        return [str(v) for v in value]

    @property
    def data_path(self) -> Path:
        return self.data_dir

    def ensure_data_paths(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.voice_profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.content_plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.post_queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.queue_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.sent_history_path.parent.mkdir(parents=True, exist_ok=True)

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
            temperature=float(self.openai_temperature) if self.openai_temperature is not None else 0.3,
        )


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    settings.ensure_data_paths()
    return settings
