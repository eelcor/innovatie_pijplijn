"""Shared helpers voor templates.

Ondersteunt reverse-proxy / subpad-deployments via APP_BASE_URL.
Bijv. APP_BASE_URL=http://example.com/innovatiepijplijn zorgt dat alle
generieke URL's het /innovatiepijplijn prefix krijgen.
"""

import html
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Configuratie: basis-URL en basis-pad van de applicatie ---

def get_base_url() -> str:
    """Haal de basis-URL op uit APP_BASE_URL of val terug op standaard."""
    return os.environ.get("APP_BASE_URL", "http://localhost:8000")


def get_base_path() -> str:
    """Haal het basis-pad op voor reverse-proxy / subpad support.

    Eerst APP_BASE_URL env var, dan FastAPI root_path, anders '/'.
    Retourneert bijv. '/innovatiepijplijn' of '/'.
    """
    # 1. Check APP_BASE_URL
    base_url = get_base_url()
    parsed = urlparse(base_url)
    path = parsed.path.rstrip('/')
    if path:
        return path

    # 2. Fallback op FastAPI root_path (wordt door sommige reverse proxies gezet)
    #    We kunnen dit niet hier direct ophalen, dus gebruiken we een env fallback
    root_path = os.environ.get("APP_ROOT_PATH", "").rstrip('/')
    if root_path:
        return root_path

    return '/'

# Route-naam → URL mapping (wordt gebruikt door url_for in templates)
# Format: route_name: (prefix, path_pattern)
# prefix wordt voorafgezet aan path_pattern
ROUTE_MAP = {
    # Dashboard
    "dashboard": ("", "/"),
    # Initiatieven
    "initiatives_list": ("/api/initiatieven", "/lijst"),
    "initiative_detail": ("/api/initiatieven", "/detail/{id}"),
    "initiatives_filter": ("/api/initiatieven", "/filter"),
    "initiatives_json": ("/api/initiatieven", "/json"),
    # Curaties
    "curations_list": ("/api/curaties", "/lijst"),
    "curation_detail": ("/api/curaties", "/detail/{id}"),
    # Centrale vragen
    "questions_list": ("/api/vragen", "/lijst"),
    "question_detail": ("/api/vragen", "/detail/{id}"),
    # MDS teams
    "mds_list": ("/api/mds", "/lijst"),
    "mds_detail": ("/api/mds", "/{id}"),
    # Tags
    "tags_list": ("/api/tags", "/lijst"),
    "tag_detail": ("/api/tags", "/{id}"),
    # Admin / Profiel
    "admin_page": ("", "/admin"),
    "login_page": ("", "/login"),
    "profile_page": ("", "/profiel"),
    # API endpoints (gebruikt door JavaScript)
    "api_auth_me": ("/api/auth", "/me"),
    "api_auth_login": ("/api/auth", "/login"),
    "api_auth_logout": ("/api/auth", "/logout"),
    "api_auth_csrf_token": ("/api/auth", "/csrf-token"),
    "api_admin_status": ("/api/admin", "/status"),
    "api_health": ("", "/health"),
    # Dossier
    "dossier_file_download": ("/api/dossier/files/download", "/{file_id}"),
    "dossier_files_upload": ("/api/dossier/files/upload", "/{initiative_id}"),
    "question_file_download": ("/api/vragen/{question_id}/files/download", "/{file_id}"),
    "question_files_upload": ("/api/vragen/{question_id}/files/upload", ""),
    # Export
    "export_excel": ("/api/export", "/excel"),
    # AI endpoints
    "ai_suggest_initiatives": ("/api/ai/curaties/{curation_id}", "/suggest-initiatives"),
    "ai_suggest_hypotheses": ("/api/ai/initiatieven/{initiative_id}", "/suggest-hypotheses"),
    "ai_narratief": ("/api/ai/curaties/{curation_id}", "/narratief"),
    "ai_onepager": ("/api/ai/initiatieven/{initiative_id}", "/one-pager"),
}


def _join_paths(*parts: str) -> str:
    """Voeg URL-pad delen samen met precies één slash tussen elk deel.

    /innovatiepijplijn + /api/auth + /me → /innovatiepijplijn/api/auth/me
    / + / → /
    """
    result = '/'
    for part in parts:
        # Haal leading/trailing slashes weg, voeg toe als er inhoud is
        stripped = part.strip('/')
        if stripped:
            result = result.rstrip('/') + '/' + stripped
    return result


def url_for(route_name: str, **kwargs) -> str:
    """Genereer een volledige URL voor een route-naam.

    Gebruik in templates als:
      {{ url_for('dashboard') }}           → /  of /innovatiepijplijn/
      {{ url_for('initiative_detail', id='abc-123') }}

    kwargs worden gebruikt om {placeholder} in het pad te vervangen.
    Het basis-pad (APP_BASE_URL path component) wordt automatisch voorafgezet.
    """
    route = ROUTE_MAP.get(route_name)
    if not route:
        return "#"
    prefix, path = route
    # Vervang placeholders met kwargs — zowel in prefix als path
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        prefix = prefix.replace(placeholder, str(value))
        path = path.replace(placeholder, str(value))

    # Voeg basis-pad + prefix + path samen
    base_path = get_base_path()
    return _join_paths(base_path, prefix, path)


def url_for_full(route_name: str, **kwargs) -> str:
    """Genereer een volledige URL inclusief basis-URL (voor JS/extern gebruik)."""
    return get_base_url() + url_for(route_name, **kwargs)


templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))


# --- Jinja2 globale functies ---

def phase_label(phase: str) -> str:
    """Fase-naam in leesbare vorm."""
    labels = {
        "idee": "Idee",
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


# --- v0.2: Nieuwe label functies ---

def cluster_label(cluster: str) -> str:
    """Cluster-naam in korte vorm."""
    labels = {
        "Beheer": "Beheer",
        "Interne Dienstverlening en Advisering": "Dienstverlening",
        "Participatie en Maatschappelijke Ontwikkeling": "Participatie",
        "Publiekszaken Handhaving en Veiligheid": "Publiekszaken",
        "Stedelijke Ontwikkeling": "Stedelijke Ontw.",
    }
    return labels.get(cluster, cluster or "")


def cluster_css_class(cluster: str) -> str:
    """CSS class voor cluster badge."""
    mapping = {
        "Beheer": "cluster-beheer",
        "Interne Dienstverlening en Advisering": "cluster-dienstverlening",
        "Participatie en Maatschappelijke Ontwikkeling": "cluster-participatie",
        "Publiekszaken Handhaving en Veiligheid": "cluster-publiekszaken",
        "Stedelijke Ontwikkeling": "cluster-stedelijke",
    }
    return mapping.get(cluster, "")


def potentie_label(val: str) -> str:
    labels = {"hoog": "Hoog", "midden": "Midden", "onbekend": "Onbekend"}
    return labels.get(val, val or "")


def risico_label(val: str) -> str:
    labels = {"hoog": "Hoog", "midden": "Midden", "laag": "Laag"}
    return labels.get(val, val or "")


def capaciteit_label(val: str) -> str:
    labels = {"hoog": "Hoog", "midden": "Midden", "laag": "Laag", "onbekend": "Onbekend"}
    return labels.get(val, val or "")


def betrokkenheid_label(val: str) -> str:
    labels = {
        "actief_begeleidend": "Actief begeleidend",
        "passief_volgend": "Passief volgend",
        "nog_niet_betrokken": "Nog niet betrokken",
    }
    return labels.get(val, val or "")


def bron_label(val: str) -> str:
    """Bron initiatief in leesbare vorm."""
    labels = {
        "intern": "Intern",
        "idee interne medewerker": "Ideë interne medewerker",
        "intern (gok)": "Intern (gok)",
        "andere gemeente": "Andere gemeente",
        "externe leverancier": "Externe leverancier",
        "externe leverancier + intern (Griffie)": "Extern + Intern",
        "samenwerking partner": "Samenwerking partner",
        "Functioneel beheer": "Functioneel beheer",
        "Hersenspinsel kernteam": "Hersenspinsel kernteam",
    }
    return labels.get(val, val or "")


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
templates.env.globals["base_path"] = get_base_path
templates.env.globals["url_for"] = url_for
templates.env.globals["url_for_full"] = url_for_full
templates.env.globals["base_url"] = get_base_url
templates.env.globals["phaseLabel"] = phase_label
templates.env.globals["horizonLabel"] = horizon_label
templates.env.globals["statusLabel"] = status_label
templates.env.globals["hypothesisTypeLabel"] = hypothesis_type_label
templates.env.globals["hypothesisStatusLabel"] = hypothesis_status_label
templates.env.globals["aiTypeLabel"] = ai_type_label
templates.env.globals["formatDate"] = format_date
templates.env.globals["formatFileSize"] = format_file_size
templates.env.globals["renderMarkdown"] = render_markdown

# v0.2: nieuwe helpers
templates.env.globals["clusterLabel"] = cluster_label
templates.env.globals["clusterCssClass"] = cluster_css_class
templates.env.globals["potentieLabel"] = potentie_label
templates.env.globals["risicoLabel"] = risico_label
templates.env.globals["capaciteitLabel"] = capaciteit_label
templates.env.globals["betrokkenheidLabel"] = betrokkenheid_label
templates.env.globals["bronLabel"] = bron_label


def render_template(template_name: str, request, **context):
    """Render een Jinja2 template met standaard context.

    Starlette 1.0 API: TemplateResponse(request, name, context)
    """
    ctx = {
        "phases": ["idee", "verkenning", "experiment", "pilot", "opschaling"],
        "statuses": ["actief", "gestopt", "afgerond", "onduidelijk", "pauze", "idee"],
        "horizons": ["h1", "h2", "h3"],
        # v0.2: nieuwe opties voor dropdowns
        "potenties": ["hoog", "midden", "onbekend"],
        "capaciteitsvragen": ["hoog", "midden", "laag", "onbekend"],
        "risico_levels": ["hoog", "midden", "laag"],
        "betrokkenheid_iv_levels": ["actief_begeleidend", "passief_volgend", "nog_niet_betrokken"],
        **context,
    }
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=ctx,
    )
