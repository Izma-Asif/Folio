"""
pdf_maker.py – Newspaper PDF generation using Playwright (sync) and Jinja2.

Requirements:
- Windows compatible: uses sync_playwright exclusively.
- Template at backend/templates/paper.html.
- A3 portrait newspaper broadsheet design:
    * Masthead with Playfair Display (Google Fonts), date, double rules.
    * Lead story: big headline, image, 2-column summary.
    * Sections with CSS column-count: 3, column-rule, small caps labels, Source Serif 4.
    * Articles: headline, source, 2-sentence summary, tiny italic why.
    * If story has angles: "Angles: Dawn - ..., BBC - ...".
    * Bordered "Three Things You Learned Today" box.
    * "What changed in your paper" box if changes is not empty.
    * Footer: "You're done for today. About N minutes."
    * visual_mode:
        - "reader": no images.
        - "visual": lead + 3 thumbnails.
        - other/broadsheet: lead image + thumbnails if visual.
    * Image timeout (3s) or onerror fallback to grey block; never breaks the PDF.
    * break-inside: avoid on articles.
"""

import os
import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    Environment = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

logger = logging.getLogger("folio.pdf_maker")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _get_jinja_env() -> Any:
    """Configures Jinja2 environment pointing to backend/templates."""
    if Environment is None:
        raise ImportError("jinja2 is required. Install with 'pip install jinja2'.")
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"])
    )


def render_edition_html(edition_data: Dict[str, Any]) -> str:
    """
    Renders the edition data dictionary into newspaper HTML using backend/templates/paper.html.
    Handles both raw DB row {id, content, ...} and raw content dict {lead, sections, ...}.
    """
    content = edition_data.get("content") if isinstance(edition_data.get("content"), dict) else edition_data

    # Resolve visual_mode from content or default
    masthead_str = content.get("masthead") or "The Morning Folio"
    # visual_mode may be in masthead or profile
    visual_mode = "broadsheet"
    if "reader" in masthead_str.lower():
        visual_mode = "reader"
    elif "visual" in masthead_str.lower():
        visual_mode = "visual"

    date_str = content.get("date") or datetime.now().strftime("%B %d, %Y")
    read_minutes = content.get("read_minutes", 6)
    lead = content.get("lead")
    sections = content.get("sections") or []
    explore = content.get("explore") or []
    three_things = content.get("three_things") or []
    changes = content.get("changes") or []

    # Configure image visibility flags according to visual_mode
    # reader = no images; visual = lead + 3 thumbnails; broadsheet/normal = lead image
    if visual_mode == "reader":
        lead_show_image = False
        allowed_thumbnails = 0
    elif visual_mode == "visual":
        lead_show_image = True
        allowed_thumbnails = 3
    else:
        # Default broadsheet / normal
        lead_show_image = True
        allowed_thumbnails = 1

    # Mark thumbnails across sections
    thumb_count = 0
    processed_sections = []
    for sec in sections:
        sec_arts = []
        for art in sec.get("articles", []):
            art_copy = dict(art)
            if (
                allowed_thumbnails > 0
                and thumb_count < allowed_thumbnails
                and art_copy.get("image_url")
            ):
                art_copy["show_thumbnail"] = True
                thumb_count += 1
            else:
                art_copy["show_thumbnail"] = False
            sec_arts.append(art_copy)
        processed_sections.append({
            "topic": sec.get("topic", "News"),
            "articles": sec_arts
        })

    # Explore articles thumbnail assignment if quota remains
    processed_explore = []
    for art in explore:
        art_copy = dict(art)
        if (
            allowed_thumbnails > 0
            and thumb_count < allowed_thumbnails
            and art_copy.get("image_url")
        ):
            art_copy["show_thumbnail"] = True
            thumb_count += 1
        else:
            art_copy["show_thumbnail"] = False
        processed_explore.append(art_copy)

    env = _get_jinja_env()
    template = env.get_template("paper.html")

    return template.render(
        masthead=masthead_str,
        date=date_str,
        read_minutes=read_minutes,
        lead=lead,
        lead_show_image=lead_show_image,
        sections=processed_sections,
        explore=processed_explore,
        three_things=three_things,
        changes=changes,
        edition_number=1
    )


def generate_edition_pdf(edition_data: Dict[str, Any], output_path: Optional[str] = None) -> bytes:
    """
    Renders newspaper HTML and compiles into an authentic A3 portrait PDF using Playwright (sync).
    FastAPI calls this in a worker thread via standard def function.
    Never crashes: falls back to rendered HTML bytes if Playwright fails or is unavailable.
    """
    html_content = render_edition_html(edition_data)

    if sync_playwright is None:
        logger.warning("Playwright is not installed. Returning HTML as bytes fallback.")
        return html_content.encode("utf-8")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            context = browser.new_context()
            page = context.new_page()

            # Set 3-second timeout for image network requests to prevent hanging
            page.set_default_timeout(3000)

            # Load HTML content (wait for domcontentloaded so broken external images don't block)
            page.set_content(html_content, wait_until="domcontentloaded", timeout=4000)

            # Generate authentic A3 portrait PDF
            pdf_bytes = page.pdf(
                format="A3",
                landscape=False,
                print_background=True,
                margin={
                    "top": "14mm",
                    "bottom": "14mm",
                    "left": "14mm",
                    "right": "14mm"
                }
            )
            browser.close()

            if output_path:
                with open(output_path, "wb") as f:
                    f.write(pdf_bytes)

            return pdf_bytes
    except Exception as e:
        logger.error(f"Playwright PDF generation failed: {e}. Falling back to HTML bytes.")
        return html_content.encode("utf-8")
