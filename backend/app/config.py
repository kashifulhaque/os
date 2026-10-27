"""Application settings, read from the environment or a `.env` file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Caddy injects this secret header only after Authelia forward_auth
    # succeeds; the app rejects identity headers without a matching secret.
    sso_proxy_secret: str = ""
    # Preserve existing progress identities when portal usernames differ,
    # e.g. "ifkash:enderboi,ananya:michu". Unmapped users keep their own name.
    sso_users: str = ""

    @property
    def sso_names(self) -> dict[str, str]:
        pairs = (item.split(":", 1) for item in self.sso_users.split(",") if ":" in item)
        return {
            sso.strip().lower(): name.strip()
            for sso, name in pairs
            if sso.strip() and name.strip()
        }


    # Paths
    data_dir: Path = REPO_ROOT / "data"
    content_dir: Path = REPO_ROOT / "content"
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"

    # Execution
    runner: str = "local"
    local_timeout_ceiling: int = 180
    # Zero leaves RLIMIT_AS off and lets the container's cgroup bound memory.
    local_memory_mb: int = 0
    local_workers: int = 4

    git_sha: str = "unknown"


    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
