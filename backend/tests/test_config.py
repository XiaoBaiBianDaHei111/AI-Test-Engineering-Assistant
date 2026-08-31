"""Configuration tests (P2-002, P012 Docker-layout). Real mode (P013)."""

from app.core.config import Settings, _REPO_ROOT, _resolve_env_file


def test_llm_defaults():
    settings = Settings(_env_file=None)
    assert settings.llm_model == "deepseek-chat"
    assert settings.llm_timeout_seconds == 60.0
    assert settings.llm_max_retries == 2
    assert settings.llm_retry_base_delay_seconds == 1.0
    assert settings.llm_temperature == 0.0
    assert settings.llm_max_input_chars == 12_000


def test_cors_origin_list_parses():
    settings = Settings(_env_file=None, cors_origins="http://a:1, http://b:2")
    assert settings.cors_origin_list == ["http://a:1", "http://b:2"]


def test_resolve_env_file_repo_layout():
    # Source layout has backend/app -> reads the repo-root .env.
    assert _resolve_env_file(_REPO_ROOT) == str(_REPO_ROOT / ".env")


def test_resolve_env_file_container_layout(tmp_path):
    # Container layout (/app/app/...) has no backend/app -> env-vars only (None).
    assert _resolve_env_file(tmp_path) is None
