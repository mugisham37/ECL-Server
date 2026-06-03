"""Email client — extend with fastapi-mail for production SMTP."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_template_dir = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_template_dir)))


def render_template(name: str, **context: object) -> str:
    template = _env.get_template(name)
    return template.render(**context)
