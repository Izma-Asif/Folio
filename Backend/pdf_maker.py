import os
import logging
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from jinja2 import Template
except ImportError:
    Template = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

logger = logging.getLogger("folio.pdf_maker")

NEWSPAPER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Folio — {{ masthead.edition_date }}</title>
<style>
  @page {
    size: A4 portrait;
    margin: 15mm 15mm 15mm 15mm;
  }
  @media print {
    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .page-break { page-break-before: always; }
  }
  * { box-sizing: border-box; }
  body {
    font-family: 'Georgia', 'Times New Roman', serif;
    color: #1a1a1a;
    background-color: #fdfbf7;
    margin: 0;
    padding: 20px;
    line-height: 1.5;
  }
  
  /* Masthead Header */
  .header {
    text-align: center;
    border-bottom: 3px double #1a1a1a;
    padding-bottom: 8px;
    margin-bottom: 14px;
  }
  .sub-header-bar {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    font-family: 'Helvetica Neue', Arial, sans-serif;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-top: 1px solid #1a1a1a;
    border-bottom: 1px solid #1a1a1a;
    padding: 4px 6px;
    margin-bottom: 12px;
  }
  .title {
    font-family: 'Playfair Display', 'Times New Roman', serif;
    font-size: 48px;
    font-weight: 900;
    letter-spacing: 4px;
    margin: 0;
    text-transform: uppercase;
  }
  .tagline {
    font-size: 13px;
    font-style: italic;
    color: #555;
    margin: 2px 0 6px 0;
  }

  /* Editor's Note */
  .editor-box {
    background-color: #f3ede2;
    border-left: 4px solid #8b0000;
    padding: 12px 16px;
    margin-bottom: 16px;
    font-size: 13px;
  }
  .editor-box h4 {
    margin: 0 0 6px 0;
    font-family: 'Helvetica Neue', Arial, sans-serif;
    text-transform: uppercase;
    font-size: 12px;
    letter-spacing: 1px;
    color: #8b0000;
  }
  .editor-box p {
    margin: 0;
    line-height: 1.45;
  }

  /* Two Column Layout */
  .newspaper-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 18px;
  }

  /* Lead Article */
  .lead-article {
    border-bottom: 1px solid #ccc;
    padding-bottom: 14px;
    margin-bottom: 14px;
  }
  .lead-tag {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
    color: #8b0000;
    letter-spacing: 1px;
  }
  .lead-title {
    font-size: 26px;
    font-weight: bold;
    line-height: 1.2;
    margin: 4px 0 8px 0;
  }
  .lead-meta {
    font-size: 11px;
    color: #777;
    margin-bottom: 8px;
    font-family: 'Helvetica Neue', Arial, sans-serif;
  }
  .lead-img {
    width: 100%;
    max-height: 260px;
    object-fit: cover;
    border-radius: 2px;
    margin-bottom: 10px;
  }
  .lead-summary {
    font-size: 14px;
    line-height: 1.55;
    text-align: justify;
  }

  /* Section Articles */
  .section-title {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 12px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    border-bottom: 2px solid #1a1a1a;
    padding-bottom: 3px;
    margin: 14px 0 10px 0;
  }
  .article-card {
    border-bottom: 1px dotted #ccc;
    padding-bottom: 10px;
    margin-bottom: 10px;
  }
  .article-card:last-child {
    border-bottom: none;
  }
  .article-title {
    font-size: 16px;
    font-weight: bold;
    margin: 2px 0 4px 0;
    line-height: 1.25;
  }
  .article-meta {
    font-size: 10px;
    color: #888;
    margin-bottom: 4px;
    font-family: 'Helvetica Neue', Arial, sans-serif;
  }
  .article-text {
    font-size: 12px;
    line-height: 1.45;
    color: #333;
  }

  /* Briefs Sidebar */
  .sidebar {
    background-color: #faf7f0;
    border: 1px solid #e2ddd3;
    padding: 12px;
    border-radius: 3px;
  }
  .brief-item {
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid #eae5db;
  }
  .brief-title {
    font-size: 12px;
    font-weight: bold;
    margin-bottom: 2px;
  }
  .brief-text {
    font-size: 11px;
    line-height: 1.4;
    color: #444;
  }

  /* Footer */
  .footer {
    border-top: 1px solid #1a1a1a;
    margin-top: 20px;
    padding-top: 6px;
    font-size: 10px;
    font-family: 'Helvetica Neue', Arial, sans-serif;
    color: #666;
    display: flex;
    justify-content: space-between;
  }
</style>
</head>
<body>

  <!-- Masthead -->
  <div class="header">
    <h1 class="title">FOLIO</h1>
    <div class="tagline">The Bespoke Daily Newspaper • Tailored for Clarity & Intellect</div>
    <div class="sub-header-bar">
      <span>EDITION: {{ masthead.edition_date }}</span>
      <span>ESTIMATED READING: {{ masthead.reading_time or 6 }} MINS</span>
      <span>MODE: {{ masthead.visual_mode | upper }}</span>
    </div>
  </div>

  <!-- Editor's Note -->
  {% if editor_note and editor_note.note %}
  <div class="editor-box">
    <h4>From the Editor-in-Chief</h4>
    <p>{{ editor_note.note }}</p>
  </div>
  {% endif %}

  <!-- Main Newspaper Body -->
  <div class="newspaper-grid">
    <!-- Left Main Column -->
    <div>
      {% if lead %}
      <div class="lead-article">
        <div class="lead-tag">Front Page Focus • {{ lead.topic | upper }}</div>
        <div class="lead-title">{{ lead.title }}</div>
        <div class="lead-meta">{{ lead.source }} • {{ lead.published_at[:10] if lead.published_at else '' }}</div>
        {% if lead.image_url %}
        <img class="lead-img" src="{{ lead.image_url }}" alt="Lead Image" onerror="this.style.display='none'"/>
        {% endif %}
        <div class="lead-summary">
          {{ lead.ai_summary or lead.summary }}
        </div>
      </div>
      {% endif %}

      <!-- Focus Deep Dives -->
      {% if focus and focus|length > 0 %}
      <div class="section-title">In-Depth Analyses</div>
      {% for art in focus %}
      <div class="article-card">
        <div class="lead-tag">{{ art.topic | upper }}</div>
        <div class="article-title">{{ art.title }}</div>
        <div class="article-meta">{{ art.source }}</div>
        <div class="article-text">{{ art.ai_summary or art.summary }}</div>
      </div>
      {% endfor %}
      {% endif %}

      <!-- World & Society -->
      {% if world_society and world_society|length > 0 %}
      <div class="section-title">World & General Pulse</div>
      {% for art in world_society %}
      <div class="article-card">
        <div class="article-title">{{ art.title }}</div>
        <div class="article-meta">{{ art.source }} • {{ art.topic | upper }}</div>
        <div class="article-text">{{ art.ai_summary or art.summary }}</div>
      </div>
      {% endfor %}
      {% endif %}
    </div>

    <!-- Right Sidebar Column -->
    <div>
      {% if serendipity %}
      <div class="sidebar" style="margin-bottom: 14px; border-left: 3px solid #2a52be;">
        <div class="lead-tag" style="color: #2a52be;">Serendipity & Discovery</div>
        <div class="article-title" style="font-size: 14px;">{{ serendipity.title }}</div>
        <div class="article-meta">{{ serendipity.source }} • {{ serendipity.topic }}</div>
        <div class="article-text" style="font-size: 11px;">{{ serendipity.ai_summary or serendipity.summary }}</div>
      </div>
      {% endif %}

      <!-- Briefs Column -->
      <div class="sidebar">
        <div class="section-title" style="margin-top: 0;">Signals & Briefs</div>
        {% for b in briefs %}
        <div class="brief-item">
          <div class="brief-title">{{ b.title }}</div>
          <div class="article-meta">{{ b.source }}</div>
          <div class="brief-text">{{ b.ai_summary or b.summary }}</div>
        </div>
        {% endfor %}
      </div>
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    <span>FOLIO DAILY CHRONICLE</span>
    <span>PERSONALIZED INTELLIGENCE • ALL RIGHTS RESERVED</span>
    <span>PAGE 1 OF 1</span>
  </div>

</body>
</html>
"""


def render_edition_html(edition_data: Dict[str, Any]) -> str:
    """Renders edition dictionary into newspaper broadsheet HTML."""
    if Template is None:
        raise ImportError("jinja2 is required. Install with 'pip install jinja2'.")

    template = Template(NEWSPAPER_HTML_TEMPLATE)
    content = edition_data.get("content", edition_data)

    masthead = content.get("masthead", {
        "edition_date": datetime.now().strftime("%B %d, %Y"),
        "visual_mode": "broadsheet",
        "reading_time": 6
    })

    rendered = template.render(
        masthead=masthead,
        editor_note=content.get("editor_note", {}),
        lead=content.get("lead"),
        focus=content.get("focus", []),
        world_society=content.get("world_society", []),
        serendipity=content.get("serendipity"),
        briefs=content.get("briefs", [])
    )
    return rendered


def generate_edition_pdf(edition_data: Dict[str, Any], output_path: Optional[str] = None) -> bytes:
    """
    Renders newspaper HTML and converts to PDF via Playwright.
    If Playwright browser is unavailable, falls back gracefully.
    """
    html_content = render_edition_html(edition_data)

    if sync_playwright is None:
        logger.warning("Playwright is not installed. Returning HTML as bytes fallback.")
        return html_content.encode("utf-8")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"}
            )
            browser.close()

            if output_path:
                with open(output_path, "wb") as f:
                    f.write(pdf_bytes)

            return pdf_bytes
    except Exception as e:
        logger.error(f"Playwright PDF generation failed: {e}. Returning rendered HTML.")
        # Return HTML bytes as fallback so client still gets printable document
        return html_content.encode("utf-8")
