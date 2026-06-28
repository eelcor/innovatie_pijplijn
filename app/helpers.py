"""Shared helpers voor templates."""

import html
import os
import re
from datetime import datetime, timedelta

from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))


# --- Jinja2 globale functies ---

def phase_label(phase: str) -> str:
    """Fase-naam in leesbare vorm."""
    labels = {
        "verkenning": "Verkenning",
        "experiment": "Experiment",
        "pilot": "Pilot",
        "opschaling": "Opschaling",
    }
    return labels.get(phase, phase)


def horizon_label(h: str) -> str:
    """Horizon-code in leesbare vorm."""
    labels = {"h1": "H1", "h2": "H2", "h3": "H3"}
    return labels.get(h, h or "")


def status_label(status: str) -> str:
    """Status in leesbare vorm."""
    labels = {
        "actief": "Actief",
        "gestopt": "Gestopt",
        "afgerond": "Afgerond",
    }
    return labels.get(status, status)


def hypothesis_type_label(htype: str) -> str:
    """Hypothese-type in leesbare vorm."""
    labels = {
        "value": "Value",
        "growth": "Growth",
        "compliance": "Compliance",
    }
    return labels.get(htype, htype)


def hypothesis_status_label(status: str) -> str:
    """Hypothese-status in leesbare vorm."""
    labels = {
        "open": "Open",
        "bevestigd": "Bevestigd",
        "weerlegd": "Weerlegd",
        "vervallen": "Vervallen",
    }
    return labels.get(status, status)


def ai_type_label(type_val: str) -> str:
    """Type AI-gebruik in leesbare vorm."""
    labels = {
        "bouwen_met_ai": "Bouwen met AI",
        "ai_in_bouwsels": "AI in bouwsels",
        "ai_in_bestaande_tools": "AI in bestaande tools",
        "persoonlijke_productiviteit": "Persoonlijke productiviteit",
        "mix": "Mix",
    }
    return labels.get(type_val, type_val or "")


def format_date(iso_string: str | None) -> str:
    """Formatteer een ISO-datum naar leesbaar Nederlands."""
    if not iso_string:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo or None)
        diff = now - dt
        days = diff.days

        if days == 0:
            return "Vandaag"
        if days == 1:
            return "Gisteren"
        if days < 7:
            return f"{days} dagen geleden"
        if days < 30:
            weeks = days // 7
            return f"{weeks} week{'en' if weeks > 1 else ''} geleden"

        return dt.strftime("%d-%m-%Y")
    except (ValueError, TypeError):
        return "-"


def format_file_size(bytes_val: int) -> str:
    """Formatteer bytes naar leesbare formaat."""
    if not bytes_val:
        return "0 B"
    if bytes_val < 1024:
        return f"{bytes_val} B"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    return f"{bytes_val / (1024 * 1024):.1f} MB"


def _safe_url(url: str) -> str:
    """Validateer een URL voor gebruik in een link. Blokkeer javascript: en andere gevaarlijke schemes."""
    stripped = url.strip().lower()
    if stripped.startswith(('javascript:', 'vbscript:', 'data:text/html')):
        return '#'
    return html.escape(url, quote=True)


def render_markdown(text: str) -> str:
    """Eenvoudige server-side markdown renderer voor Jinja2 templates.

    Ondersteunt: headings, bold, italic, code, lijsten, links, line breaks.
    Escapt HTML in de input om XSS te voorkomen.
    """
    if not text:
        return ""

    # Eerst alle HTML-karakters escappen om XSS te voorkomen
    out = html.escape(text)

    # Headings (### ## #)
    out = re.sub(r'^### (.+)$', r'<h3>\1</h3>', out, flags=re.MULTILINE)
    out = re.sub(r'^## (.+)$', r'<h2>\1</h2>', out, flags=re.MULTILINE)
    out = re.sub(r'^# (.+)$', r'<h1>\1</h1>', out, flags=re.MULTILINE)

    # Bold (**text** or __text__)
    out = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', out)
    out = re.sub(r'__(.+?)__', r'<strong>\1</strong>', out)

    # Italic (*text* or _text_)
    out = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'<em>\1</em>', out)
    out = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<em>\1</em>', out)

    # Inline code (`code`) — al geëscapt door html.escape hierboven
    out = re.sub(r'`([^`]+)`', r'<code>\1</code>', out)

    # Links [text](url) — URL wordt gevalideerd en geëscapt
    def _replace_link(m):
        link_text = m.group(1)
        raw_url = m.group(2)
        safe_url = _safe_url(raw_url)
        return f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{link_text}</a>'

    out = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _replace_link, out)

    # Unordered lists (- item or * item) — convert consecutive lines
    lines = out.split('\n')
    result_lines = []
    in_list = False
    for line in lines:
        list_match = re.match(r'^[\-\*] (.+)$', line)
        if list_match:
            if not in_list:
                result_lines.append('<ul>')
                in_list = True
            result_lines.append(f'<li>{list_match.group(1)}</li>')
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            result_lines.append(line)
    if in_list:
        result_lines.append('</ul>')
    out = '\n'.join(result_lines)

    # Paragraph breaks (double newlines → </p><p>)
    out = out.replace('\n\n', '</p><p>')
    # Single newlines → <br>
    out = out.replace('\n', '<br>')

    # Wrap in paragraph if not already wrapped with a tag
    if not out.startswith('<'):
        out = '<p>' + out + '</p>'

    return f'<div class="markdown-body">' + out + '</div>'


# Registreer functies bij Jinja2 environment
templates.env.globals["phaseLabel"] = phase_label
templates.env.globals["horizonLabel"] = horizon_label
templates.env.globals["statusLabel"] = status_label
templates.env.globals["hypothesisTypeLabel"] = hypothesis_type_label
templates.env.globals["hypothesisStatusLabel"] = hypothesis_status_label
templates.env.globals["aiTypeLabel"] = ai_type_label
templates.env.globals["formatDate"] = format_date
templates.env.globals["formatFileSize"] = format_file_size
templates.env.globals["renderMarkdown"] = render_markdown


def render_template(template_name: str, request, **context):
    """Render een Jinja2 template met standaard context.

    Starlette 1.0 API: TemplateResponse(request, name, context)
    """
    ctx = {
        "phases": ["verkenning", "experiment", "pilot", "opschaling"],
        "statuses": ["actief", "gestopt", "afgerond"],
        "horizons": ["h1", "h2", "h3"],
        **context,
    }
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=ctx,
    )
