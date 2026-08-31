"""Application configuration loaded from environment / .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The .env file lives at the repository ROOT (alongside .env.example), NOT
# relative to the process CWD — so starting from backend/, the repo root, or a
# script all read the same file (P011 §5.4).
#   backend/app/core/config.py -> parents[0]=core, [1]=app, [2]=backend, [3]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_env_file(repo_root: Path | None = None) -> str | None:
    """Return the repo-root ``.env`` path (source layout) or ``None`` (container).

    The Docker image lays out the app as ``/app/app/core/config.py`` (COPY app
    ./app) and ships no ``.env`` — compose injects environment variables instead.
    In that layout ``<root>/backend/app`` does not exist, so we must degrade to
    env-vars-only (``None``) rather than hard-fail (P012: the Docker bring-up
    regression was a RuntimeError here). Extracted as a function so both layouts
    are unit-testable (R012 MINOR-002).
    """
    root = repo_root if repo_root is not None else _REPO_ROOT
    if (root / "backend" / "app").is_dir():
        return str(root / ".env")
    return None


_ENV_FILE = _resolve_env_file()


class Settings(BaseSettings):
    """Central runtime configuration.

    Values are read from environment variables (case-insensitive, highest
    priority) and the repository-root ``.env`` file. A missing ``.env`` falls
    back to defaults (SQLite) so a fresh clone needs nothing.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AI Test Workflow Automation"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"

    # PostgreSQL in Docker; SQLite as a zero-dependency local fallback.
    # e.g. postgresql+psycopg://user:pass@db:5432/ai_test_workflow
    database_url: str = "sqlite:///./ai_test_workflow.db"

    # Comma-separated list of allowed CORS origins.
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173,"
        "http://127.0.0.1:3000,http://127.0.0.1:5173"
    )

    # Root directory where run evidence will be written in later phases.
    # Layout is frozen as artifacts/<run_id>/...
    artifacts_dir: str = "artifacts"

    # --- LLM configuration (Phase 2) ---
    # Real DeepSeek (OpenAI-compatible) only — P013 removed the mock provider.
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    llm_retry_base_delay_seconds: float = 1.0
    llm_temperature: float = 0.0
    # Long-PRD segmentation threshold (characters). Segmenting kicks in above this.
    llm_max_input_chars: int = 12_000

    # --- Execution configuration (Phase 5) ---
    # Real Playwright browser only — P013 removed the fake driver.
    playwright_headless: bool = True
    playwright_action_timeout_ms: int = 15_000
    # Script files live under artifacts/<run_id>/<run_script_subdir>/<run_case_id>.py
    run_script_subdir: str = "scripts"

    # --- Evidence configuration (Phase 6) ---
    # Evidence retention (days) for the cleanup script; per-run volume warning cap.
    evidence_retention_days: int = 30
    evidence_max_run_bytes: int = 104_857_600  # 100 MB

    # --- Failure analysis configuration (Phase 7) ---
    failure_analysis_confidence_threshold: float = 0.7
    failure_rule_confidence: float = 0.93
    failure_context_max_chars: int = 8000

    # --- Report configuration (Phase 8) ---
    # Report files live outside per-run evidence dirs (D3: survive cleanup).
    reports_dir: str = "artifacts/reports"

    # --- API testing configuration (Phase 9) ---
    api_request_timeout_seconds: float = 10.0
    api_response_body_max_chars: int = 8192

    log_level: str = "INFO"
    debug: bool = False

    # --- Schema compatibility check (P011 hotfix) ---
    # Set SKIP_SCHEMA_CHECK=1 to bypass the startup schema check (escape hatch).
    skip_schema_check: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse the comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
