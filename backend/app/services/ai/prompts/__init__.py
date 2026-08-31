"""Versioned YAML prompt loading (ADOPT ai-nlt prompt_specs).

Each YAML has ``schema_version``, ``system`` and ``template``. ``schema_version``
must stay in sync with ``app.schemas.ai.SCHEMA_VERSION`` (a unit test enforces it).
"""

from pathlib import Path

import yaml

_PROMPT_DIR = Path(__file__).parent


def load_prompt(name: str) -> dict:
    path = _PROMPT_DIR / f"{name}.yaml"
    with open(path, encoding="utf-8") as file:
        return yaml.safe_load(file)


def render_prompt(name: str, **kwargs) -> tuple[str, str, int]:
    """Return ``(system, user, schema_version)``.

    ``{placeholder}`` in the template is replaced via ``str.replace`` (safe even
    when the substituted value contains braces).
    """
    spec = load_prompt(name)
    system = str(spec["system"]).strip()
    template = str(spec["template"]).strip()
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", str(value))
    schema_version = int(spec.get("schema_version", 1))
    return system, template, schema_version
