"""Markdown → Confluence storage HTML (Mermaid as SVG attachments via Kroki + optional code macro)."""

from __future__ import annotations

import hashlib
import html
import re
import sys
import time
from pathlib import Path
from typing import Literal

import httpx
import markdown  # type: ignore[import-untyped]

Presentation = Literal["stakeholder", "standard"]

MERMAID_PLACEHOLDER_PREFIX = "MERMAIDBLOCK"
CODE_PLACEHOLDER_PREFIX = "CODEBLOCK"

# Fenced block: optional indent, ```lang, body, closing ```
_FENCE_RE = re.compile(
    r"^[ \t]*```[ \t]*([^\n`]*?)[ \t]*\n(.*?)^[ \t]*```[ \t]*$",
    re.DOTALL | re.MULTILINE,
)


def _extract_fenced(md: str) -> tuple[str, dict[str, str]]:
    store: dict[str, str] = {}
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal counter
        lang = (m.group(1) or "").strip().lower()
        body = m.group(2)
        counter += 1
        if lang == "mermaid":
            key = f"@@{MERMAID_PLACEHOLDER_PREFIX}{counter}@@"
            store[key] = body.strip()
            return f"\n\n{key}\n\n"
        key = f"@@{CODE_PLACEHOLDER_PREFIX}{counter}@@"
        store[key] = body.rstrip("\n")
        return f"\n\n{key}\n\n"

    out = _FENCE_RE.sub(repl, md)
    return out, store


def _mermaid_code_macro(src: str) -> str:
    safe = src.replace("]]>", "]] >")
    return (
        '<ac:structured-macro ac:name="code" ac:schema-version="1">'
        '<ac:parameter ac:name="language">mermaid</ac:parameter>'
        f"<ac:plain-text-body><![CDATA[{safe}]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )


def _mermaid_svg_attachment_macro(filename: str) -> str:
    fe = html.escape(filename, quote=True)
    return (
        f'<p><ac:image ac:align="center"><ri:attachment ri:filename="{fe}" /></ac:image></p>'
        '<p><em>Diagram (Mermaid, rendered as SVG).</em></p>'
    )


def _code_macro(lang: str, src: str) -> str:
    safe = src.replace("]]>", "]] >")
    lg = html.escape(lang or "text", quote=True)
    return (
        '<ac:structured-macro ac:name="code" ac:schema-version="1">'
        f'<ac:parameter ac:name="language">{lg}</ac:parameter>'
        f"<ac:plain-text-body><![CDATA[{safe}]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )


def _expand_wrap(inner_storage: str, title: str) -> str:
    tt = html.escape(title, quote=True)
    return (
        '<ac:structured-macro ac:name="expand" ac:schema-version="1">'
        f'<ac:parameter ac:name="title">{tt}</ac:parameter>'
        f"<ac:rich-text-body>{inner_storage}</ac:rich-text-body>"
        "</ac:structured-macro>"
    )


def _code_macro_for_presentation(lang: str, src: str, presentation: Presentation) -> str:
    inner = _code_macro(lang, src)
    if presentation != "stakeholder":
        return inner
    nlines = src.count("\n") + (1 if src else 0)
    if nlines <= 3 and len(src) < 220:
        return inner
    label = (lang or "text").strip() or "text"
    return _expand_wrap(inner, f"Technical reference ({label})")


_TABLE_TAG_RE = re.compile(r"<table([^>]*)>", re.IGNORECASE)
_BLOCKQUOTE_RE = re.compile(r"<blockquote>\s*(.*?)\s*</blockquote>", re.DOTALL | re.IGNORECASE)


def _enhance_tables_for_confluence(html_body: str) -> str:
    def repl(m: re.Match[str]) -> str:
        attrs = m.group(1) or ""
        if "confluenceTable" in attrs:
            return m.group(0)

        def bump_class(mm: re.Match[str]) -> str:
            existing = mm.group(1)
            extra = "relative-table wrapped confluenceTable"
            if "relative-table" in existing:
                return f'class="{existing}"'
            return f'class="{existing} {extra}"'

        if re.search(r"\bclass\s*=", attrs, re.IGNORECASE):
            new_attrs = re.sub(
                r'class\s*=\s*"([^"]*)"',
                bump_class,
                attrs,
                count=1,
                flags=re.IGNORECASE,
            )
            return f"<table{new_attrs}>"
        return f'<table class="relative-table wrapped confluenceTable"{attrs}>'

    return _TABLE_TAG_RE.sub(repl, html_body)


def _blockquotes_to_panels(html_body: str) -> str:
    def repl(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        if not inner:
            return ""
        return (
            '<ac:structured-macro ac:name="panel" ac:schema-version="1">'
            '<ac:parameter ac:name="panelColor">note</ac:parameter>'
            '<ac:parameter ac:name="borderStyle">solid</ac:parameter>'
            '<ac:parameter ac:name="title">Key point</ac:parameter>'
            f"<ac:rich-text-body>{inner}</ac:rich-text-body>"
            "</ac:structured-macro>"
        )

    return _BLOCKQUOTE_RE.sub(repl, html_body)


def _polish_html_body(html_body: str, presentation: Presentation) -> str:
    if presentation != "stakeholder":
        return html_body
    html_body = _enhance_tables_for_confluence(html_body)
    html_body = _blockquotes_to_panels(html_body)
    return html_body


def _md_extensions(presentation: Presentation) -> list[str]:
    ex: list[str] = ["tables", "sane_lists"]
    if presentation == "standard":
        ex.append("nl2br")
    return ex


def _img_tag_to_confluence(m: re.Match[str]) -> str:
    tag = m.group(0)
    al = re.search(r'\balt="([^"]*)"', tag)
    sr = re.search(r'\bsrc="([^"]+)"', tag)
    alt = al.group(1) if al else ""
    src = sr.group(1) if sr else ""
    ev = html.escape(src, quote=True)
    if src.startswith("http://") or src.startswith("https://"):
        return f'<ac:image ac:align="center"><ri:url ri:value="{ev}" /></ac:image>'
    base = Path(src.split("?", maxsplit=1)[0]).name
    if "/" in src or "\\" in src:
        return (
            f'<p><em>{html.escape(alt)}</em> '
            f'<a href="{ev}">{html.escape(Path(src).name)}</a></p>'
        )
    return (
        f'<p><em>{html.escape(alt)}</em></p>'
        f'<ac:image ac:align="center"><ri:attachment ri:filename="{html.escape(base, quote=True)}" /></ac:image>'
    )


def _inject_placeholder_macro(html_body: str, key: str, macro: str) -> str:
    variants = (
        f"<p>{key}</p>",
        f"<p>{key}<br /></p>",
        f"<p>{key}<br/></p>",
        f"<p><br />{key}</p>",
        f"<p><br/>{key}</p>",
    )
    for v in variants:
        if v in html_body:
            return html_body.replace(v, macro, 1)
    if key in html_body:
        return html_body.replace(key, macro, 1)
    return html_body


def markdown_to_storage(md: str, *, presentation: Presentation = "stakeholder") -> str:
    """Classic path: Mermaid via Confluence ``code`` macro (needs Mermaid app to render).

    ``stakeholder`` (default): document-style paragraphs (no nl2br), Confluence table classes,
    blockquotes as panels, long code blocks inside Expand macros.
    ``standard``: legacy Markdown-like line breaks (nl2br) and plain code macros.
    """
    md2, ph = _extract_fenced(md)
    html_body = markdown.markdown(md2, extensions=_md_extensions(presentation))
    html_body = _polish_html_body(html_body, presentation)
    html_body = re.sub(r"<img\b[^>]+/?>", _img_tag_to_confluence, html_body)
    for key, body in ph.items():
        if MERMAID_PLACEHOLDER_PREFIX in key:
            macro = _mermaid_code_macro(body)
        else:
            macro = _code_macro_for_presentation("", body, presentation)
        html_body = _inject_placeholder_macro(html_body, key, macro)
    _assert_no_placeholder_leaks(html_body)
    return html_body


def _assert_no_placeholder_leaks(html_body: str) -> None:
    if MERMAID_PLACEHOLDER_PREFIX in html_body or CODE_PLACEHOLDER_PREFIX in html_body:
        idx = html_body.find("@@")
        snip = html_body[idx : idx + 120] if idx >= 0 else html_body[:120]
        raise ValueError(
            "Markdown→storage left unreplaced fenced placeholders (check fences / markdown output). "
            f"Snippet: {snip!r}"
        )


def fetch_mermaid_svg(client: httpx.Client, source: str, kroki_url: str = "https://kroki.io/mermaid/svg") -> bytes | None:
    """Render Mermaid to SVG via Kroki HTTP POST (no URL length limit)."""
    payload = source.strip().encode("utf-8")
    if not payload:
        return None
    for attempt in range(3):
        try:
            r = client.post(
                kroki_url,
                content=payload,
                headers={"Content-Type": "text/plain; charset=utf-8"},
                timeout=120.0,
            )
        except OSError:
            return None
        if r.status_code == 200 and b"<svg" in r.content[:2000]:
            return r.content
        if r.status_code in (429, 502, 503) and attempt < 2:
            time.sleep(1.0 * (attempt + 1))
            continue
        return None
    return None


def mermaid_attachment_filename(source: str) -> str:
    h = hashlib.sha256(source.strip().encode("utf-8")).hexdigest()[:14]
    return f"mermaid-{h}.svg"


def markdown_to_storage_with_mermaid_svgs(
    md: str,
    client: httpx.Client,
    *,
    kroki_url: str = "https://kroki.io/mermaid/svg",
    include_source_macro: bool = False,
    presentation: Presentation = "stakeholder",
) -> tuple[str, list[tuple[str, bytes]]]:
    """Build storage HTML and SVG attachments for each Mermaid block (Kroki POST).

    Confluence often does not render ``language=mermaid`` code macros without a marketplace app.
    Uploaded SVG attachments + ``ri:attachment`` display diagrams reliably.

    If Kroki fails for a diagram, falls back to the code macro for that block only.

    ``presentation`` matches :func:`markdown_to_storage` (default ``stakeholder``).

    Returns:
        (storage_html, list of (filename, svg_bytes) to upload before saving the page body)
    """
    md2, ph = _extract_fenced(md)
    html_body = markdown.markdown(md2, extensions=_md_extensions(presentation))
    html_body = _polish_html_body(html_body, presentation)
    html_body = re.sub(r"<img\b[^>]+/?>", _img_tag_to_confluence, html_body)

    attachments: list[tuple[str, bytes]] = []
    mermaid_keys = [k for k in ph if MERMAID_PLACEHOLDER_PREFIX in k]

    for key in mermaid_keys:
        body = ph[key]
        svg = fetch_mermaid_svg(client, body, kroki_url=kroki_url)
        if svg:
            fname = mermaid_attachment_filename(body)
            attachments.append((fname, svg))
            macro = _mermaid_svg_attachment_macro(fname)
            if include_source_macro:
                macro = macro + _mermaid_code_macro(body)
        else:
            head = body.strip().split("\n", 1)[0][:80]
            print(
                f"Kroki Mermaid render failed; using Confluence code macro (install Mermaid app to view). "
                f"First line: {head!r}",
                file=sys.stderr,
            )
            macro = _mermaid_code_macro(body)
        html_body = _inject_placeholder_macro(html_body, key, macro)

    for key, body in ph.items():
        if MERMAID_PLACEHOLDER_PREFIX in key:
            continue
        macro = _code_macro_for_presentation("", body, presentation)
        html_body = _inject_placeholder_macro(html_body, key, macro)

    _assert_no_placeholder_leaks(html_body)
    return html_body, attachments


def fix_markdown_images_for_attachments(md: str) -> str:
    """Use basenames for wiki screenshots; keep absolute URLs intact."""

    def repl(m: re.Match[str]) -> str:
        alt, path = m.group(1), m.group(2).strip()
        if path.startswith("http://") or path.startswith("https://"):
            return m.group(0)
        base = Path(path.split("?", maxsplit=1)[0]).name
        return f"![{alt}]({base})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, md)
