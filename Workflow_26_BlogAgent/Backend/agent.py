# agent.py
# LangGraph HITL blog-writing workflow.
# Generates blogs and saves them as structured HTML/CSS/JS into the Blogs/ folder.
#
# Directory layout written by this module:
#   Blogs/
#     images/                         ← home-page images (manual)
#     contents/
#       images/<slug>/                ← per-blog generated images
#       css/<slug>.css
#       js/<slug>.js
#       html/<slug>.html
#     index.html   ← updated on every approval
#     style.css    ← home-page styles  (created once if missing)
#     script.js    ← home-page scripts (created once if missing)

from __future__ import annotations

import re
import time
import operator
from datetime import datetime
from pathlib import Path
from typing import TypedDict, List, Annotated, Literal, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, interrupt
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_tavily import TavilySearch

from google import genai
import google.genai.types as types

from current_datetime import get_current_datetime

# ── Internal imports ──────────────────────────────────────────
from config import (
    OLLAMA_MODEL, OLLAMA_TEMPERATURE,
    GOOGLE_API_KEY, BLOGS_DIR,
)
from logger import get_logger
from prompts import (
    ROUTER_SYSTEM, RESEARCH_SYSTEM, ORCH_SYSTEM,
    WORKER_SYSTEM, DECIDE_IMAGE_SYSTEM,
)

logger = get_logger("Agent")

# ──────────────────────────────────────────────────────────────
# LLM — single instance
# ──────────────────────────────────────────────────────────────

logger.debug("[SETUP] Initialising LLM...")
llm = ChatOllama(
    model=OLLAMA_MODEL,
    temperature=OLLAMA_TEMPERATURE,
)
logger.debug(f"[SETUP] LLM ready: model='{OLLAMA_MODEL}'")

# ──────────────────────────────────────────────────────────────
# Gemini client (image generation)
# ──────────────────────────────────────────────────────────────

_gemini_client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None


# ──────────────────────────────────────────────────────────────
# Pydantic Schemas
# ──────────────────────────────────────────────────────────────

class Task(BaseModel):
    id: int
    title: str
    goal: str = Field(..., description="One sentence describing the section goal.")
    bullets: List[str] = Field(..., min_length=3, max_length=5)
    target_words: int
    tags: List[str]           = Field(default_factory=list)
    requires_research: bool   = False
    requires_citations: bool  = False
    requires_code: bool       = False


class Plan(BaseModel):
    blog_title: str
    audience: str
    tone: str
    blog_kind: Literal["explainer", "tutorial", "news_roundup", "comparison", "system_design"] = "explainer"
    constraints: List[str] = Field(default_factory=list)
    tasks: List[Task]      = Field(default_factory=list)


class EvidenceItem(BaseModel):
    title: str
    url: str
    published_at: Optional[str] = None
    snippet: Optional[str]      = None
    source: Optional[str]       = None


class RouterDecision(BaseModel):
    needs_research: bool = False
    mode: Literal["closed_book", "hybrid", "open_book"] = "closed_book"
    queries: List[str] = Field(default_factory=list)


class EvidencePack(BaseModel):
    evidence: List[EvidenceItem] = Field(default_factory=list)


class ImageSpec(BaseModel):
    placeholder: str = Field(
        ...,
        description=(
            "Exact placeholder token. MUST be one of: "
            "[[IMAGE_1]], [[IMAGE_2]], [[IMAGE_3]]."
        )
    )
    insert_after_heading: str = Field(
        ...,
        description=(
            "The exact ## heading text (without '## ') after whose first "
            "paragraph this image is inserted."
        )
    )
    filename: str
    alt: str
    caption: str
    prompt: str
    size: Literal["1024x1024", "1024x1536", "1536x1024"] = "1024x1024"
    quality: Literal["low", "medium", "high"]            = "medium"


class GlobalImagePlan(BaseModel):
    images: List[ImageSpec] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────────

class State(TypedDict):
    topic: str

    # routing / research
    mode: str
    needs_research: bool
    queries: List[str]
    evidence: List[EvidenceItem]
    plan: Optional[Plan]

    # workers
    sections: Annotated[List[tuple[int, str]], operator.add]

    # reducer / image
    merged_md: str
    md_with_placeholders: str
    image_specs: List[dict]
    final: str

    # HITL
    approval_status: Optional[str]   # "approved" | "rejected"
    rejection_reason: Optional[str]


# ──────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────

_PLACEHOLDER_RE = re.compile(r'\[{1,2}IMAGE_(\d+)[^\]]*\]{1,2}')


def _sanitize_filename(name: str) -> str:
    """Convert a blog title into a safe filesystem slug."""
    sanitized = re.sub(r'[\\/:*?"<>|]', '-', name)
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = re.sub(r'-+', '-', sanitized).strip(' -_')
    return sanitized


def _tavily_search(query: str, max_results: int = 6) -> List[dict]:
    logger.debug(f"[RESEARCH] Tavily search — query='{query}'")
    tool = TavilySearch(max_results=max_results)
    try:
        response = tool.invoke({"query": query})
    except Exception as e:
        logger.error(f"[RESEARCH] Tavily search failed for query='{query}': {e}", exc_info=True)
        return []

    if isinstance(response, dict):
        results = response.get("results") or []
    elif isinstance(response, list):
        results = response
    else:
        logger.warning(f"[RESEARCH] Unexpected Tavily response type: {type(response)}")
        results = []

    return [
        {
            "title":        r.get("title") or "",
            "url":          r.get("url") or "",
            "snippet":      r.get("content") or r.get("snippet") or "",
            "published_at": r.get("published_date") or r.get("published_at"),
            "source":       r.get("source"),
        }
        for r in results
    ]


def _inject_placeholders(merged_md: str, images: list) -> str:
    """Insert [[IMAGE_N]] tokens into merged_md at the correct heading positions."""

    def _build_heading_index(lines: list) -> dict:
        return {
            line[3:].strip(): i
            for i, line in enumerate(lines)
            if line.startswith("## ")
        }

    ordered = sorted(
        images,
        key=lambda x: int(_PLACEHOLDER_RE.search(x.placeholder).group(1))
        if _PLACEHOLDER_RE.search(x.placeholder) else 999
    )

    result = merged_md.split("\n")

    for img in ordered:
        target_heading = img.insert_after_heading.strip()
        if target_heading.startswith("## "):
            target_heading = target_heading[3:].strip()

        canonical = (
            f"[[IMAGE_{_PLACEHOLDER_RE.search(img.placeholder).group(1)}]]"
            if _PLACEHOLDER_RE.search(img.placeholder) else img.placeholder
        )

        heading_index = _build_heading_index(result)
        idx = heading_index.get(target_heading)
        if idx is None:
            for h, i in heading_index.items():
                if h.lower() == target_heading.lower():
                    idx = i
                    break

        if idx is None:
            logger.warning(f"[IMAGES] Could not find heading '{target_heading}'. Appending at end.")
            result.append("")
            result.append(canonical)
            continue

        insert_at = idx + 1
        while insert_at < len(result) and result[insert_at].strip():
            insert_at += 1

        result.insert(insert_at, canonical)
        result.insert(insert_at, "")
        logger.debug(f"[IMAGES] Injected '{canonical}' after heading '{target_heading}'")

    return "\n".join(result)


def _gemini_generate_image_bytes(prompt: str) -> bytes:
    IMAGE_MODEL = "gemini-2.5-flash-image"
    if _gemini_client is None:
        raise RuntimeError("GOOGLE_API_KEY is not set.")

    response = _gemini_client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_ONLY_HIGH",
                )
            ],
        ),
    )

    parts = getattr(response, "parts", None)
    if not parts and getattr(response, "candidates", None):
        try:
            parts = response.candidates[0].content.parts
        except Exception:
            parts = None

    if not parts:
        raise RuntimeError("No image content returned (safety/quota/SDK change).")

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            return inline.data

    raise RuntimeError("No inline image bytes found in response.")


# ──────────────────────────────────────────────────────────────
# HTML / CSS / JS generation helpers
# ──────────────────────────────────────────────────────────────

def _md_to_html(text: str) -> str:
    """
    Convert Markdown to HTML.
    Requires: pip install markdown
    Falls back to a basic regex-based converter if the package is missing.
    """
    try:
        import markdown
        return markdown.markdown(
            text,
            extensions=["fenced_code", "tables", "nl2br"],
        )
    except ImportError:
        logger.warning(
            "[HTML] 'markdown' package not found — using basic converter. "
            "Install it with: pip install markdown"
        )
        return _md_to_html_basic(text)


def _md_to_html_basic(text: str) -> str:
    """Minimal markdown → HTML fallback (no external deps)."""
    lines   = text.split("\n")
    output  = []
    in_code = False
    in_list = False

    for line in lines:
        # Fenced code blocks
        if line.startswith("```"):
            if in_code:
                output.append("</code></pre>")
                in_code = False
            else:
                lang = line[3:].strip()
                output.append(f'<pre><code class="language-{lang}">')
                in_code = True
            continue

        if in_code:
            output.append(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            continue

        # Close list if needed
        if in_list and not line.startswith("- ") and not line.startswith("* "):
            output.append("</ul>")
            in_list = False

        # Headings
        if line.startswith("### "):
            output.append(f"<h3>{_inline_md(line[4:])}</h3>")
        elif line.startswith("## "):
            output.append(f"<h2>{_inline_md(line[3:])}</h2>")
        elif line.startswith("# "):
            output.append(f"<h1>{_inline_md(line[2:])}</h1>")
        # Unordered list
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{_inline_md(line[2:])}</li>")
        # Blank line → paragraph break
        elif line.strip() == "":
            output.append("")
        # Normal paragraph
        else:
            output.append(f"<p>{_inline_md(line)}</p>")

    if in_list:
        output.append("</ul>")
    if in_code:
        output.append("</code></pre>")

    return "\n".join(output)


def _inline_md(text: str) -> str:
    """Apply inline Markdown (bold, italic, code, links, images)."""
    # Images  ![alt](src)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1">', text)
    # Links  [text](href)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    # Bold   **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__',     r'<strong>\1</strong>', text)
    # Italic  *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_',   r'<em>\1</em>', text)
    # Inline code
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def _get_excerpt(md_content: str, max_chars: int = 200) -> str:
    """Extract the first non-heading text paragraph from markdown."""
    for line in md_content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("!") and not line.startswith("["):
            clean = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
            clean = re.sub(r'\*(.+?)\*', r'\1', clean)
            clean = re.sub(r'`(.+?)`', r'\1', clean)
            if len(clean) > max_chars:
                clean = clean[:max_chars].rsplit(" ", 1)[0] + "..."
            return clean
    return ""


def _estimate_reading_time(md_content: str) -> int:
    """Return estimated reading time in minutes (avg 200 wpm)."""
    words = len(md_content.split())
    return max(1, round(words / 200))


def _build_blog_css(slug: str) -> str:
    return f"""\
/* {slug}.css — Blog post stylesheet */

:root {{
  --bg:          #ffffff;
  --fg:          #1a1a2e;
  --muted:       #6b7280;
  --accent:      #4f46e5;
  --accent-light:#eef2ff;
  --border:      #e5e7eb;
  --code-bg:     #f3f4f6;
  --font-body:   'Segoe UI', system-ui, -apple-system, sans-serif;
  --font-mono:   'Fira Code', 'Cascadia Code', Consolas, monospace;
  --max-width:   760px;
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  background: var(--bg);
  color: var(--fg);
  font-family: var(--font-body);
  font-size: 1.0625rem;
  line-height: 1.75;
  padding: 0 1rem 4rem;
}}

/* ── Reading progress bar ── */
#readingBar {{
  position: fixed;
  top: 0; left: 0;
  height: 3px;
  width: 0%;
  background: var(--accent);
  z-index: 1000;
  transition: width .1s linear;
}}

/* ── Navigation ── */
.site-header {{
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 1.25rem 0;
}}

.breadcrumb a {{
  color: var(--accent);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
}}
.breadcrumb a:hover {{ text-decoration: underline; }}

/* ── Article ── */
.blog-article {{
  max-width: var(--max-width);
  margin: 0 auto;
}}

.article-header {{
  padding: 2rem 0 2.5rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 2.5rem;
}}

.topic-tag {{
  display: inline-block;
  background: var(--accent-light);
  color: var(--accent);
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .06em;
  padding: .2rem .65rem;
  border-radius: 999px;
  margin-bottom: 1rem;
}}

.article-title {{
  font-size: clamp(1.75rem, 4vw, 2.5rem);
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: 1rem;
  color: var(--fg);
}}

.article-meta {{
  display: flex;
  gap: 1.25rem;
  color: var(--muted);
  font-size: 0.875rem;
}}

/* ── Body typography ── */
.article-body h2 {{
  font-size: 1.5rem;
  font-weight: 700;
  margin: 2.5rem 0 .75rem;
  padding-bottom: .4rem;
  border-bottom: 2px solid var(--accent-light);
  color: var(--fg);
}}

.article-body h3 {{
  font-size: 1.2rem;
  font-weight: 600;
  margin: 2rem 0 .5rem;
  color: var(--fg);
}}

.article-body p {{
  margin-bottom: 1.25rem;
  color: var(--fg);
}}

.article-body ul,
.article-body ol {{
  margin: 0 0 1.25rem 1.5rem;
}}

.article-body li {{ margin-bottom: .4rem; }}

.article-body a {{
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 3px;
}}

/* ── Images ── */
.article-body img {{
  max-width: 100%;
  border-radius: 8px;
  margin: 1.5rem 0 .5rem;
  border: 1px solid var(--border);
}}

.article-body em {{
  display: block;
  text-align: center;
  color: var(--muted);
  font-size: .875rem;
  margin-bottom: 1.25rem;
}}

/* ── Code ── */
.article-body code {{
  font-family: var(--font-mono);
  font-size: .9em;
  background: var(--code-bg);
  padding: .15em .4em;
  border-radius: 4px;
  color: #c026d3;
}}

.article-body pre {{
  background: #1e1e2e;
  color: #cdd6f4;
  border-radius: 10px;
  padding: 1.25rem 1.5rem;
  overflow-x: auto;
  margin: 1.5rem 0;
  position: relative;
}}

.article-body pre code {{
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: .875rem;
  line-height: 1.65;
}}

.copy-btn {{
  position: absolute;
  top: .6rem;
  right: .6rem;
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.15);
  color: #cdd6f4;
  font-size: .75rem;
  padding: .3rem .65rem;
  border-radius: 6px;
  cursor: pointer;
  transition: background .2s;
}}
.copy-btn:hover {{ background: rgba(255,255,255,.18); }}

/* ── Blockquote ── */
.article-body blockquote {{
  border-left: 4px solid var(--accent);
  background: var(--accent-light);
  padding: 1rem 1.25rem;
  border-radius: 0 8px 8px 0;
  margin: 1.5rem 0;
  color: #374151;
}}

/* ── Table ── */
.article-body table {{
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
  font-size: .9rem;
}}
.article-body th,
.article-body td {{
  border: 1px solid var(--border);
  padding: .6rem .9rem;
  text-align: left;
}}
.article-body th {{
  background: var(--accent-light);
  font-weight: 600;
  color: var(--accent);
}}
.article-body tr:nth-child(even) {{ background: #f9fafb; }}

/* ── Footer ── */
.site-footer {{
  max-width: var(--max-width);
  margin: 3rem auto 0;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border);
  font-size: .9rem;
}}

.site-footer a {{
  color: var(--accent);
  text-decoration: none;
}}
.site-footer a:hover {{ text-decoration: underline; }}

@media (max-width: 600px) {{
  .article-meta {{ flex-direction: column; gap: .5rem; }}
}}
"""


def _build_blog_js(slug: str) -> str:
    return f"""\
// {slug}.js — Blog post interactivity

(function () {{
  'use strict';

  // ── Reading progress bar ──────────────────────────────────
  const bar = document.getElementById('readingBar');
  if (bar) {{
    window.addEventListener('scroll', function () {{
      const scrollTop    = window.scrollY;
      const docHeight    = document.documentElement.scrollHeight - window.innerHeight;
      const pct          = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      bar.style.width    = Math.min(pct, 100) + '%';
    }}, {{ passive: true }});
  }}

  // ── Copy-code buttons ─────────────────────────────────────
  document.querySelectorAll('pre').forEach(function (pre) {{
    const btn       = document.createElement('button');
    btn.className   = 'copy-btn';
    btn.textContent = 'Copy';
    pre.style.position = 'relative';
    pre.appendChild(btn);

    btn.addEventListener('click', function () {{
      const code = pre.querySelector('code');
      const text = code ? code.innerText : pre.innerText;
      navigator.clipboard.writeText(text).then(function () {{
        btn.textContent = 'Copied!';
        setTimeout(function () {{ btn.textContent = 'Copy'; }}, 2000);
      }}).catch(function () {{
        btn.textContent = 'Error';
        setTimeout(function () {{ btn.textContent = 'Copy'; }}, 2000);
      }});
    }});
  }});

  // ── Smooth-scroll for anchor links ───────────────────────
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {{
    anchor.addEventListener('click', function (e) {{
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {{
        e.preventDefault();
        target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      }}
    }});
  }});
}})();
"""


def _build_blog_html(
    title: str,
    topic: str,
    slug: str,
    content_html: str,
    excerpt: str,
    reading_time: int,
    created_at: datetime,
) -> str:
    iso_date      = created_at.strftime("%Y-%m-%dT%H:%M:%S")
    formatted_date = created_at.strftime("%B %d, %Y")

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{excerpt}">
  <title>{title}</title>
  <link rel="stylesheet" href="../css/{slug}.css">
</head>
<body>

  <!-- Reading-progress bar -->
  <div id="readingBar"></div>

  <header class="site-header">
    <nav class="breadcrumb">
      <a href="../../index.html">← All Blogs</a>
    </nav>
  </header>

  <article class="blog-article">
    <header class="article-header">
      <span class="topic-tag">{topic}</span>
      <h1 class="article-title">{title}</h1>
      <div class="article-meta">
        <time datetime="{iso_date}">{formatted_date}</time>
        <span class="reading-time">~{reading_time} min read</span>
      </div>
    </header>

    <div class="article-body">
      {content_html}
    </div>
  </article>

  <footer class="site-footer">
    <a href="../../index.html">← Back to All Blogs</a>
  </footer>

  <script src="../js/{slug}.js"></script>
</body>
</html>
"""


def _build_index_html() -> str:
    return """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Blog</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>

  <header class="site-header">
    <div class="header-inner">
      <div class="logo">📝 Blog</div>
      <p class="tagline">Thoughts, ideas, and deep-dives worth reading.</p>
    </div>
  </header>

  <main class="main-content">
    <div class="blog-grid" id="blogGrid">
      <!-- BLOG_ENTRIES_START -->
      <!-- BLOG_ENTRIES_END -->
    </div>
  </main>

  <footer class="page-footer">
    <p>Powered by AI · Human-approved content</p>
  </footer>

  <script src="script.js"></script>
</body>
</html>
"""


def _build_index_css() -> str:
    return """\
/* style.css — Blog home page */

:root {
  --bg:          #f9fafb;
  --fg:          #111827;
  --muted:       #6b7280;
  --accent:      #4f46e5;
  --accent-light:#eef2ff;
  --border:      #e5e7eb;
  --card-bg:     #ffffff;
  --font:        'Segoe UI', system-ui, -apple-system, sans-serif;
  --max-width:   1100px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--fg);
  font-family: var(--font);
  line-height: 1.6;
}

/* ── Header ── */
.site-header {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  color: #fff;
  padding: 3.5rem 1rem 3rem;
  text-align: center;
}

.header-inner { max-width: var(--max-width); margin: 0 auto; }

.logo {
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -.03em;
  margin-bottom: .5rem;
}

.tagline {
  font-size: 1.0625rem;
  opacity: .85;
}

/* ── Blog grid ── */
.main-content {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 3rem 1rem 4rem;
}

.blog-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.75rem;
}

/* ── Card ── */
.blog-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: box-shadow .2s, transform .2s;
}

.blog-card:hover {
  box-shadow: 0 8px 28px rgba(79,70,229,.12);
  transform: translateY(-3px);
}

.card-body {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.tag {
  display: inline-block;
  background: var(--accent-light);
  color: var(--accent);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .07em;
  padding: .18rem .6rem;
  border-radius: 999px;
  margin-bottom: .9rem;
  align-self: flex-start;
}

.card-title {
  font-size: 1.15rem;
  font-weight: 700;
  line-height: 1.35;
  margin-bottom: .75rem;
  color: var(--fg);
}

.card-title a {
  color: inherit;
  text-decoration: none;
}
.card-title a:hover { color: var(--accent); }

.card-excerpt {
  color: var(--muted);
  font-size: .9rem;
  flex: 1;
  margin-bottom: 1.25rem;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: .8125rem;
  color: var(--muted);
}

.read-btn {
  background: var(--accent);
  color: #fff;
  text-decoration: none;
  padding: .35rem .85rem;
  border-radius: 8px;
  font-size: .8125rem;
  font-weight: 600;
  transition: background .2s;
}
.read-btn:hover { background: #4338ca; }

/* ── Empty state ── */
.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 4rem 1rem;
  color: var(--muted);
}
.empty-state p { font-size: 1.1rem; }

/* ── Footer ── */
.page-footer {
  text-align: center;
  padding: 1.5rem;
  color: var(--muted);
  font-size: .85rem;
  border-top: 1px solid var(--border);
}

@media (max-width: 640px) {
  .blog-grid { grid-template-columns: 1fr; }
  .logo { font-size: 1.6rem; }
}
"""


def _build_index_js() -> str:
    return """\
// script.js — Blog home page

(function () {
  'use strict';

  // Animate cards on scroll
  const cards = document.querySelectorAll('.blog-card');
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 }
    );
    cards.forEach(function (card) {
      card.style.opacity = '0';
      card.style.transform = 'translateY(16px)';
      card.style.transition = 'opacity .4s ease, transform .4s ease';
      io.observe(card);
    });
  }
})();
"""


# ──────────────────────────────────────────────────────────────
# Blog file I/O
# ──────────────────────────────────────────────────────────────

def _ensure_blogs_scaffold() -> Path:
    """
    Create the Blogs/ directory scaffold if it doesn't exist.
    Returns the root Blogs/ Path object.
    """
    root = Path(BLOGS_DIR)
    (root / "images").mkdir(parents=True, exist_ok=True)
    (root / "contents" / "images").mkdir(parents=True, exist_ok=True)
    (root / "contents" / "css").mkdir(parents=True, exist_ok=True)
    (root / "contents" / "js").mkdir(parents=True, exist_ok=True)
    (root / "contents" / "html").mkdir(parents=True, exist_ok=True)

    # Write home-page files only if they don't already exist
    index_path = root / "index.html"
    if not index_path.exists():
        index_path.write_text(_build_index_html(), encoding="utf-8")
        logger.info(f"[BLOGS] Created {index_path}")

    style_path = root / "style.css"
    if not style_path.exists():
        style_path.write_text(_build_index_css(), encoding="utf-8")
        logger.info(f"[BLOGS] Created {style_path}")

    script_path = root / "script.js"
    if not script_path.exists():
        script_path.write_text(_build_index_js(), encoding="utf-8")
        logger.info(f"[BLOGS] Created {script_path}")

    return root


def _save_blog_html_files(
    plan: Plan,
    topic: str,
    slug: str,
    final_md: str,
    created_at: datetime,
) -> None:
    """
    Convert the final markdown to HTML and write HTML / CSS / JS files
    into the Blogs/contents/ directories.  Does NOT touch index.html.
    """
    root    = _ensure_blogs_scaffold()
    img_dir = root / "contents" / "images" / slug
    img_dir.mkdir(parents=True, exist_ok=True)

    # Rewrite image paths for HTML context
    # Markdown uses:  images/filename.png
    # HTML needs:    ../images/<slug>/filename.png
    html_md = final_md.replace("](images/", f"](../images/{slug}/")

    content_html = _md_to_html(html_md)
    excerpt      = _get_excerpt(final_md)
    reading_time = _estimate_reading_time(final_md)

    # HTML
    html_content = _build_blog_html(
        title=plan.blog_title,
        topic=topic,
        slug=slug,
        content_html=content_html,
        excerpt=excerpt,
        reading_time=reading_time,
        created_at=created_at,
    )
    html_path = root / "contents" / "html" / f"{slug}.html"
    html_path.write_text(html_content, encoding="utf-8")

    # CSS
    css_path = root / "contents" / "css" / f"{slug}.css"
    css_path.write_text(_build_blog_css(slug), encoding="utf-8")

    # JS
    js_path = root / "contents" / "js" / f"{slug}.js"
    js_path.write_text(_build_blog_js(slug), encoding="utf-8")

    logger.info(f"[BLOGS] Saved blog files: {html_path}")


def _update_index_html(
    plan: Plan,
    topic: str,
    slug: str,
    final_md: str,
    created_at: datetime,
) -> None:
    """
    Prepend a new blog card to Blogs/index.html.
    Called only on approval so the blog becomes publicly listed.
    """
    root       = _ensure_blogs_scaffold()
    index_path = root / "index.html"

    iso_date       = created_at.strftime("%Y-%m-%dT%H:%M:%S")
    formatted_date = created_at.strftime("%b %d, %Y")
    excerpt        = _get_excerpt(final_md)

    card_html = f"""\
      <article class="blog-card" data-date="{iso_date}">
        <div class="card-body">
          <span class="tag">{topic}</span>
          <h2 class="card-title">
            <a href="contents/html/{slug}.html">{plan.blog_title}</a>
          </h2>
          <p class="card-excerpt">{excerpt}</p>
          <div class="card-footer">
            <time datetime="{iso_date}">{formatted_date}</time>
            <a class="read-btn" href="contents/html/{slug}.html">Read →</a>
          </div>
        </div>
      </article>"""

    content = index_path.read_text(encoding="utf-8")
    marker  = "<!-- BLOG_ENTRIES_START -->"

    if marker not in content:
        logger.warning("[BLOGS] BLOG_ENTRIES_START marker not found in index.html — appending marker.")
        content = content.replace(
            "</main>",
            f'  <div class="blog-grid" id="blogGrid">\n      {marker}\n      <!-- BLOG_ENTRIES_END -->\n    </div>\n  </main>'
        )

    updated = content.replace(marker, f"{marker}\n{card_html}")
    index_path.write_text(updated, encoding="utf-8")
    logger.info(f"[BLOGS] index.html updated with '{plan.blog_title}'")


def _get_current_time_info():
    """Returns dict with current date, time, month_year, year in IST."""
    dt = get_current_datetime(return_ist=True)
    return {
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "month_year": dt.strftime("%B %Y"),
        "year": dt.year
    }

# ──────────────────────────────────────────────────────────────
# Graph Nodes
# ──────────────────────────────────────────────────────────────

def router_node(state: State) -> dict:
    topic = state["topic"]
    logger.info(f"[ROUTER] ── Entering router node ──────────────────────────")

    # Get current datetime in IST and format strings
    current_ist = _get_current_time_info()
    current_date_str = current_ist["date"]
    current_time_str = current_ist["time"]
    current_month_year = current_ist["month_year"]
    current_year = current_ist["year"]
    logger.info(f"[ROUTER] Current date (IST): {current_date_str} | Time: {current_time_str} | Year: {current_year}")

    # Format ONLY ROUTER_SYSTEM
    time_aware_router_system = ROUTER_SYSTEM.format(
        current_date=current_date_str,
        current_time=current_time_str,
        current_month_year=current_month_year,
        current_year=current_year
    )

    decider = llm.with_structured_output(RouterDecision)
    try:
        decision = decider.invoke([
            SystemMessage(content=time_aware_router_system),
            HumanMessage(content=f"Topic: {topic}"),
        ])
    except Exception as e:
        logger.error(f"[ROUTER] LLM invocation failed: {e}", exc_info=True)
        raise

    needs_research = decision.needs_research or bool(decision.queries)
    logger.info(f"[ROUTER]   mode='{decision.mode}' | needs_research={needs_research} | queries={len(decision.queries)}")
    logger.info(f"[ROUTER] ── Router node complete ────────────────────────────")

    return {
        "needs_research": needs_research,
        "mode":           decision.mode,
        "queries":        decision.queries,
    }

def route_next(state: State) -> str:
    next_node = "research" if state["needs_research"] else "orchestrator"
    logger.info(f"[ROUTER] Routing → '{next_node}'")
    return next_node


def research_node(state: State) -> dict:
    queries = state.get("queries", []) or []
    logger.info(f"[RESEARCH] ── Entering research node ({len(queries)} queries) ──")

    raw_results: List[dict] = []
    search_start = datetime.now()

    with ThreadPoolExecutor(max_workers=min(len(queries), 10)) as pool:
        future_to_q = {pool.submit(_tavily_search, q): q for q in queries}
        for future in as_completed(future_to_q):
            q = future_to_q[future]
            try:
                results = future.result()
                raw_results.extend(results)
            except Exception as e:
                logger.error(f"[RESEARCH] Query FAILED: '{q}': {e}", exc_info=True)

    elapsed = (datetime.now() - search_start).total_seconds()
    logger.info(f"[RESEARCH] Total raw results: {len(raw_results)} ({elapsed:.2f}s)")

    if not raw_results:
        logger.warning("[RESEARCH] No raw results — returning empty evidence.")
        return {"evidence": []}

    extractor = llm.with_structured_output(EvidencePack)
    try:
        pack = extractor.invoke([
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(content=f"Raw results:\n{raw_results}"),
        ])
    except Exception as e:
        logger.error(f"[RESEARCH] LLM evidence extraction failed: {e}", exc_info=True)
        raise

    dedup = {e.url: e for e in pack.evidence if e.url}
    logger.info(f"[RESEARCH] Evidence after deduplication: {len(dedup)} items")
    logger.info(f"[RESEARCH] ── Research node complete ───────────────────────────")
    return {"evidence": list(dedup.values())}


def orchestrator_node(state: State) -> dict:
    logger.info(f"[ORCH] ── Entering orchestrator node ──────────────────────")
    
    planner  = llm.with_structured_output(Plan)
    evidence = state.get("evidence", [])
    mode     = state.get("mode", "closed_book")
    evidence_dump = [e.model_dump() for e in evidence][:16]

    # Get current datetime in IST and format strings
    current_ist = _get_current_time_info()
    current_date_str = current_ist["date"]
    current_time_str = current_ist["time"]
    current_month_year = current_ist["month_year"]
    current_year = current_ist["year"]
    logger.info(f"[ORCH] Current date (IST): {current_date_str} | Time: {current_time_str} | Year: {current_year}")

    # Format ONLY ORCH_SYSTEM here
    time_aware_orch_system = ORCH_SYSTEM.format(
        current_date=current_date_str,
        current_time=current_time_str,
        current_month_year=current_month_year,
        current_year=current_year
    )

    messages = [
        SystemMessage(content=time_aware_orch_system),   # Correct place
        HumanMessage(content=(
            f"Topic: {state['topic']}\n"
            f"Mode: {mode}\n\n"
            f"Evidence (ONLY use for fresh claims; may be empty):\n"
            f"{evidence_dump}"
        )),
    ]

    plan = None
    for attempt in range(1, 4):
        logger.info(f"[ORCH] Planning attempt {attempt}/3...")
        try:
            plan = planner.invoke(messages)
        except Exception as e:
            logger.error(f"[ORCH] LLM failed on attempt {attempt}: {e}", exc_info=True)
            if attempt == 3:
                raise
            continue

        if plan and plan.tasks:
            logger.info(f"[ORCH] Plan accepted — {len(plan.tasks)} tasks | '{plan.blog_title}'")
            break

        logger.warning(f"[ORCH] Attempt {attempt} returned empty tasks. Retrying...")
        messages = [
            SystemMessage(content=time_aware_orch_system),
            HumanMessage(content=(
                f"Topic: {state['topic']}\nMode: {mode}\n\n"
                "IMPORTANT: You returned an empty tasks list. This is invalid.\n"
                "You MUST include at least 5 task objects in the tasks array.\n\n"
                f"Evidence:\n{evidence_dump}"
            )),
        ]

    if not (plan and plan.tasks):
        logger.error("[ORCH] All 3 attempts returned empty tasks.")

    logger.info(f"[ORCH] ── Orchestrator node complete ─────────────────────────")
    return {"plan": plan}


def sub_worker(state: State):
    logger.info(f"[DISPATCHER] Dispatching workers...")
    if not state.get("plan") or not state["plan"].tasks:
        raise ValueError("Orchestrator produced no tasks. Cannot generate blog sections.")

    return [
        Send("worker", {
            "task":     task.model_dump(),
            "topic":    state["topic"],
            "mode":     state["mode"],
            "plan":     state["plan"].model_dump(),
            "evidence": [e.model_dump() for e in state.get("evidence", [])],
        })
        for task in state["plan"].tasks
    ]


def worker_node(payload: dict) -> dict:
    task     = Task(**payload["task"])
    plan     = Plan(**payload["plan"])
    evidence = [EvidenceItem(**e) for e in payload.get("evidence", [])]
    topic    = payload["topic"]
    mode     = payload.get("mode", "closed_book")

    logger.info(f"[WORKER] ── Task {task.id}: '{task.title}'")

    # Get current datetime in IST and format strings
    current_ist = _get_current_time_info()
    current_date_str = current_ist["date"]
    current_time_str = current_ist["time"]
    current_month_year = current_ist["month_year"]
    current_year = current_ist["year"]
    logger.info(f"[WORKER] Current date (IST): {current_date_str} | Time: {current_time_str} | Year: {current_year}")

    # Format WORKER_SYSTEM
    time_aware_worker_system = WORKER_SYSTEM.format(
        current_date=current_date_str,
        current_time=current_time_str,
        current_month_year=current_month_year,
        current_year=current_year
    )

    bullets_text  = "\n- " + "\n- ".join(task.bullets)
    evidence_text = "\n".join(
        f"- {e.title} | {e.url} | {e.published_at or 'date:unknown'}"
        for e in evidence[:20]
    ) if evidence else ""

    worker_start = datetime.now()
    try:
        section_md = llm.invoke([
            SystemMessage(content=time_aware_worker_system),
            HumanMessage(content=(
                f"Blog title: {plan.blog_title}\nAudience: {plan.audience}\n"
                f"Tone: {plan.tone}\nBlog kind: {plan.blog_kind}\n"
                f"Constraints: {plan.constraints}\nTopic: {topic}\nMode: {mode}\n\n"
                f"Section title: {task.title}\nGoal: {task.goal}\n"
                f"Target words: {task.target_words}\nTags: {task.tags}\n"
                f"requires_research: {task.requires_research}\n"
                f"requires_citations: {task.requires_citations}\n"
                f"requires_code: {task.requires_code}\n"
                f"Bullets:{bullets_text}\n\n"
                f"Evidence (ONLY use these URLs when citing):\n{evidence_text}\n"
            ))
        ]).content.strip()
    except Exception as e:
        logger.error(f"[WORKER] Task {task.id} LLM failed: {e}", exc_info=True)
        raise

    elapsed    = (datetime.now() - worker_start).total_seconds()
    word_count = len(section_md.split())
    deviation  = abs(word_count - task.target_words) / max(task.target_words, 1) * 100
    logger.info(f"[WORKER] Task {task.id} done — ~{word_count}w (dev={deviation:.1f}%, {elapsed:.2f}s)")
    if deviation > 20:
        logger.warning(
            f"[WORKER] Task {task.id} word count deviation > 20%: "
            f"got {word_count}, target {task.target_words}"
        )

    return {"sections": [(task.id, section_md)]}


def merge_content(state: State) -> dict:
    logger.info(f"[MERGE] ── Entering merge_content node ──────────────────────")
    plan     = state["plan"]
    sections = state.get("sections", [])

    seen: dict = {}
    for task_id, md in sections:
        if task_id not in seen:
            seen[task_id] = md

    ordered   = [md for _, md in sorted(seen.items())]
    body      = "\n\n".join(ordered).strip()
    merged_md = f"# {plan.blog_title}\n\n{body}\n"

    logger.info(f"[MERGE] Title: '{plan.blog_title}' | ~{len(merged_md.split())} words")
    logger.info(f"[MERGE] ── merge_content node complete ───────────────────────")
    return {"merged_md": merged_md}


# ──────────────────────────────────────────────────────────────
# HITL Checkpoint Node
# ──────────────────────────────────────────────────────────────

def human_approval_node(state: State) -> dict:
    """
    Workflow pauses here via LangGraph interrupt().
    Resume by calling:
        workflow.update_state(config,
            {"approval_status": "approved" | "rejected",
             "rejection_reason": "..."},
            as_node="human_approval")
    """
    logger.info("[HITL] ── Workflow pausing for human approval ──────────────")
    logger.info(f"[HITL]   Title: '{state['plan'].blog_title if state.get('plan') else 'N/A'}'")
    interrupt("Waiting for human approval")
    logger.info(f"[HITL]   Resumed — status='{state.get('approval_status')}'")
    return {}


def route_after_approval(state: State) -> str:
    status = state.get("approval_status", "").lower()
    logger.info(f"[HITL] Routing after approval — status='{status}'")
    return "finalize_approved" if status == "approved" else "handle_rejection"


# ──────────────────────────────────────────────────────────────
# Image Pipeline Nodes
# ──────────────────────────────────────────────────────────────

def decide_images(state: State) -> dict:
    logger.info(f"[IMAGES] ── Entering decide_images node ──────────────────────")
    planner   = llm.with_structured_output(GlobalImagePlan)
    merged_md = state["merged_md"]
    plan      = state["plan"]
    assert plan is not None

    headings      = [l for l in merged_md.split("\n") if l.startswith("## ")]
    headings_block = "\n".join(headings)

    try:
        image_plan = planner.invoke([
            SystemMessage(content=DECIDE_IMAGE_SYSTEM),
            HumanMessage(content=(
                f"Blog kind: {plan.blog_kind}\nTopic: {state['topic']}\n\n"
                f"Section headings available for image placement:\n{headings_block}\n\n"
                "Decide which sections need images and fill in the ImageSpec list."
            )),
        ])
    except Exception as e:
        logger.error(f"[IMAGES] LLM failed in decide_images: {e}", exc_info=True)
        raise

    fixed_images = []
    for img in image_plan.images:
        m         = _PLACEHOLDER_RE.search(img.placeholder)
        canonical = f"[[IMAGE_{m.group(1)}]]" if m else img.placeholder
        if canonical != img.placeholder:
            img = img.model_copy(update={"placeholder": canonical})
        fixed_images.append(img)

    logger.info(f"[IMAGES] Images planned: {len(fixed_images)}")

    md_with_placeholders = (
        merged_md if not fixed_images
        else _inject_placeholders(merged_md, fixed_images)
    )

    return {
        "md_with_placeholders": md_with_placeholders,
        "image_specs":          [img.model_dump() for img in fixed_images],
    }


def generate_and_place_images(state: State) -> dict:
    """
    Generate images via Gemini, save them under Blogs/contents/images/<slug>/,
    replace placeholders in markdown, then write HTML / CSS / JS files.
    Does NOT update index.html (that happens only on approval).
    """
    logger.info(f"[IMGPLACE] ── Entering generate_and_place_images node ──────────")
    plan        = state["plan"]
    topic       = state["topic"]
    md          = state.get("md_with_placeholders") or state["merged_md"]
    image_specs = state.get("image_specs", []) or []
    slug        = _sanitize_filename(plan.blog_title)
    created_at  = datetime.now()

    root    = _ensure_blogs_scaffold()
    img_dir = root / "contents" / "images" / slug
    img_dir.mkdir(parents=True, exist_ok=True)

    # ── Generate images ───────────────────────────────────────
    MAX_RETRIES   = 3
    RETRY_BACKOFF = [5, 10, 15]

    def _generate_one(spec: dict, idx: int) -> dict:
        placeholder = spec["placeholder"]
        filename    = spec["filename"]
        out_path    = img_dir / filename

        if out_path.exists():
            logger.info(f"[IMGPLACE] Cached — skipping: '{out_path}'")
            return {"spec": spec, "status": "cached"}

        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                wait = RETRY_BACKOFF[attempt - 2]
                logger.warning(f"[IMGPLACE] Image {idx} retry {attempt}/{MAX_RETRIES} — waiting {wait}s...")
                time.sleep(wait)
            try:
                img_bytes = _gemini_generate_image_bytes(spec["prompt"])
                out_path.write_bytes(img_bytes)
                logger.info(f"[IMGPLACE] Image {idx} saved: '{out_path}' ({len(img_bytes)}b, attempt {attempt})")
                return {"spec": spec, "status": "success"}
            except Exception as e:
                last_exc = e
                logger.warning(f"[IMGPLACE] Image {idx} attempt {attempt}/{MAX_RETRIES} FAILED: {e}")

        logger.error(f"[IMGPLACE] Image {idx} PERMANENTLY FAILED. Last: {last_exc}", exc_info=True)
        return {"spec": spec, "status": "failed", "error": last_exc}

    results_map: dict = {}
    if image_specs:
        with ThreadPoolExecutor(max_workers=min(len(image_specs), 3)) as pool:
            future_to_spec = {
                pool.submit(_generate_one, spec, i): spec
                for i, spec in enumerate(image_specs, start=1)
            }
            for future in as_completed(future_to_spec):
                res = future.result()
                results_map[res["spec"]["placeholder"]] = res

    # ── Replace placeholders in markdown ─────────────────────
    success_count = failure_count = cached_count = 0
    for spec in image_specs:
        placeholder = spec["placeholder"]
        filename    = spec["filename"]
        res         = results_map.get(placeholder, {})
        status      = res.get("status", "failed")

        if status in ("cached", "success"):
            cached_count += (status == "cached")
            success_count += (status == "success")
            # Markdown-relative path (rewritten to HTML path in _save_blog_html_files)
            img_md = f"![{spec['alt']}](images/{filename})\n*{spec['caption']}*"
            md = md.replace(placeholder, img_md)
        else:
            failure_count += 1
            err = res.get("error", "unknown error")
            md  = md.replace(placeholder, (
                f"> **[IMAGE GENERATION FAILED]** {spec.get('caption', '')}\n>\n"
                f"> **Alt:** {spec.get('alt', '')}\n>\n"
                f"> **Prompt:** {spec.get('prompt', '')}\n\n"
                f"> **Error:** {err}\n"
            ))

    logger.info(
        f"[IMGPLACE] Summary — success={success_count} | "
        f"failed={failure_count} | cached={cached_count}"
    )

    # ── Save HTML / CSS / JS files ────────────────────────────
    _save_blog_html_files(plan, topic, slug, md, created_at)

    logger.info(f"[IMGPLACE] ── generate_and_place_images complete ───────────────")
    return {"final": md}


# ──────────────────────────────────────────────────────────────
# HITL Terminal Nodes
# ──────────────────────────────────────────────────────────────

def finalize_approved(state: State) -> dict:
    """
    Called after human approves.
    Makes the blog publicly visible by adding it to index.html.
    """
    logger.info("[HITL] ── finalize_approved ─────────────────────────────────")
    plan  = state.get("plan")
    topic = state.get("topic", "")
    final = state.get("final") or state.get("merged_md") or ""

    if plan and topic and final:
        slug = _sanitize_filename(plan.blog_title)
        _update_index_html(plan, topic, slug, final, datetime.now())
        logger.info(f"[HITL] Blog '{plan.blog_title}' published to index.html")
    else:
        logger.warning("[HITL] finalize_approved: missing plan/topic/content — index.html not updated.")

    return {}


def handle_rejection(state: State) -> dict:
    """Called after human rejects — logs reason, no further output."""
    reason = state.get("rejection_reason") or "No reason provided."
    logger.info(f"[HITL] ── handle_rejection — Reason: {reason}")
    return {"final": f"# Blog Rejected\n\n**Reason:** {reason}\n"}


# ──────────────────────────────────────────────────────────────
# Reducer Sub-graph  (merge → images — runs before HITL)
# ──────────────────────────────────────────────────────────────

reducer_graph = StateGraph(State)
reducer_graph.add_node("merge_content",             merge_content)
reducer_graph.add_node("decide_images",             decide_images)
reducer_graph.add_node("generate_and_place_images", generate_and_place_images)

reducer_graph.add_edge(START,                       "merge_content")
reducer_graph.add_edge("merge_content",             "decide_images")
reducer_graph.add_edge("decide_images",             "generate_and_place_images")
reducer_graph.add_edge("generate_and_place_images", END)

reducer_subgraph = reducer_graph.compile()


# ──────────────────────────────────────────────────────────────
# Main Graph
# ──────────────────────────────────────────────────────────────
#
#  router ──► [research] ──► orchestrator ──► worker(×N)
#                                                  │
#                                            reducer subgraph
#                                         (merge → images → save files)
#                                                  │
#                                          human_approval  ◄── CHECKPOINT
#                                          /              \
#                               finalize_approved    handle_rejection
#                             (update index.html)

def build_workflow(checkpointer) -> StateGraph:
    graph = StateGraph(State)

    graph.add_node("router",            router_node)
    graph.add_node("research",          research_node)
    graph.add_node("orchestrator",      orchestrator_node)
    graph.add_node("worker",            worker_node)
    graph.add_node("reducer",           reducer_subgraph)
    graph.add_node("human_approval",    human_approval_node)
    graph.add_node("finalize_approved", finalize_approved)
    graph.add_node("handle_rejection",  handle_rejection)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router", route_next,
        {"research": "research", "orchestrator": "orchestrator"}
    )
    graph.add_edge("research",     "orchestrator")
    graph.add_conditional_edges("orchestrator", sub_worker, ["worker"])
    graph.add_edge("worker",       "reducer")
    graph.add_edge("reducer",      "human_approval")

    graph.add_conditional_edges(
        "human_approval", route_after_approval,
        {"finalize_approved": "finalize_approved", "handle_rejection": "handle_rejection"}
    )

    graph.add_edge("finalize_approved", END)
    graph.add_edge("handle_rejection",  END)

    return graph.compile(checkpointer=checkpointer)
