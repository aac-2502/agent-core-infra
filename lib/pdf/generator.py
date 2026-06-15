"""
PDF generator — agent-core-infra
WeasyPrint wrapper with Jinja2 template rendering.
"""
import os
import jinja2
from weasyprint import HTML, CSS

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
_STYLES_DIR = os.path.join(os.path.dirname(__file__), "styles")

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_TEMPLATES_DIR),
    autoescape=jinja2.select_autoescape(["html"]),
)


def render_pdf(
    template_name: str,
    context: dict,
    extra_css: str | None = None,
) -> bytes:
    """Render a Jinja2 HTML template to PDF bytes."""
    html_str = _env.get_template(template_name).render(**context)
    base_css_path = os.path.join(_STYLES_DIR, "base.css")
    stylesheets = [CSS(filename=base_css_path)]
    if extra_css:
        stylesheets.append(CSS(string=extra_css))
    return HTML(string=html_str, base_url=_TEMPLATES_DIR).write_pdf(
        stylesheets=stylesheets
    )


def render_report(context: dict, extra_css: str | None = None) -> bytes:
    """Render a report-style PDF (scores, metrics, analysis sections)."""
    return render_pdf("report.html", context, extra_css)


def render_document(context: dict, extra_css: str | None = None) -> bytes:
    """Render a document-style PDF (contracts, structured long-form text)."""
    return render_pdf("document.html", context, extra_css)
