"""Compact page observation and interactive element extraction from visible HTML."""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional

from app.agent.mcp_client import PlaywrightMCPClient


class _HTMLPageExtractor(HTMLParser):
    """Parses HTML to extract page title, visible text, interactive elements, and form state."""

    def __init__(self) -> None:
        super().__init__()
        self.title: str = ""
        self._in_title: bool = False
        self._in_script_or_style: bool = False
        self._text_chunks: list[str] = []
        self.interactive_elements: list[str] = []
        self.form_snapshot: dict[str, str] = {}

        # Tracking button and link inner text
        self._current_tag: Optional[str] = None
        self._current_tag_attrs: dict[str, str] = {}
        self._current_tag_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag_lower in ("script", "style", "svg", "noscript"):
            self._in_script_or_style = True
            return

        if tag_lower == "title":
            self._in_title = True
            return

        if tag_lower == "input":
            input_type = attr_dict.get("type", "text").lower()
            if input_type != "hidden":
                id_val = attr_dict.get("id", "")
                name = attr_dict.get("name", "")
                val = attr_dict.get("value", "")
                placeholder = attr_dict.get("placeholder", "")

                sel = f"#{id_val}" if id_val else (f"input[name='{name}']" if name else "input")
                desc = f"Input ({input_type}): selector='{sel}'"
                if name:
                    desc += f", name='{name}'"
                if id_val:
                    desc += f", id='{id_val}'"
                if val:
                    desc += f", value='{val}'"
                if placeholder:
                    desc += f", placeholder='{placeholder}'"

                self.interactive_elements.append(desc)
                key = id_val or name or sel
                self.form_snapshot[key] = val

        elif tag_lower == "textarea":
            id_val = attr_dict.get("id", "")
            name = attr_dict.get("name", "")
            sel = f"#{id_val}" if id_val else (f"textarea[name='{name}']" if name else "textarea")
            self._current_tag = "textarea"
            self._current_tag_attrs = attr_dict
            self._current_tag_text = []

        elif tag_lower == "select":
            id_val = attr_dict.get("id", "")
            name = attr_dict.get("name", "")
            val = attr_dict.get("value", "")
            sel = f"#{id_val}" if id_val else (f"select[name='{name}']" if name else "select")
            desc = f"Select: selector='{sel}'"
            if name:
                desc += f", name='{name}'"
            if id_val:
                desc += f", id='{id_val}'"
            if val:
                desc += f", value='{val}'"
            self.interactive_elements.append(desc)
            key = id_val or name or sel
            self.form_snapshot[key] = val

        elif tag_lower in ("button", "a"):
            self._current_tag = tag_lower
            self._current_tag_attrs = attr_dict
            self._current_tag_text = []

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "svg", "noscript"):
            self._in_script_or_style = False
            return

        if tag_lower == "title":
            self._in_title = False
            return

        if tag_lower == "textarea" and self._current_tag == "textarea":
            attrs = self._current_tag_attrs
            val = "".join(self._current_tag_text).strip()
            id_val = attrs.get("id", "")
            name = attrs.get("name", "")
            sel = f"#{id_val}" if id_val else (f"textarea[name='{name}']" if name else "textarea")
            desc = f"Textarea: selector='{sel}'"
            if name:
                desc += f", name='{name}'"
            if id_val:
                desc += f", id='{id_val}'"
            if val:
                desc += f", value='{val}'"
            self.interactive_elements.append(desc)
            key = id_val or name or sel
            self.form_snapshot[key] = val
            self._current_tag = None

        elif tag_lower in ("button", "a") and self._current_tag == tag_lower:
            attrs = self._current_tag_attrs
            text = " ".join("".join(self._current_tag_text).split())
            id_val = attrs.get("id", "")
            if tag_lower == "button":
                btn_type = attrs.get("type", "button")
                sel = (
                    f"#{id_val}"
                    if id_val
                    else ("button" if not text else f"button:has-text('{text}')")
                )
                desc = f"Button: text='{text}', selector='{sel}'"
                if id_val:
                    desc += f", id='{id_val}'"
                if btn_type:
                    desc += f", type='{btn_type}'"
                self.interactive_elements.append(desc)
            elif tag_lower == "a":
                href = attrs.get("href", "")
                if href and href != "#" and not href.startswith("javascript:"):
                    sel = f"#{id_val}" if id_val else f"a[href='{href}']"
                    desc = f"Link: text='{text}', href='{href}', selector='{sel}'"
                    if id_val:
                        desc += f", id='{id_val}'"
                    self.interactive_elements.append(desc)
            self._current_tag = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
            return

        if self._in_script_or_style:
            return

        stripped = data.strip()
        if stripped:
            self._text_chunks.append(stripped)

        if self._current_tag in ("button", "a", "textarea"):
            self._current_tag_text.append(data)


@dataclass
class PageObservation:
    url: str
    title: str
    visible_text: str
    interactive_elements: list[str] = field(default_factory=list)
    form_snapshot: dict[str, str] = field(default_factory=dict)

    @property
    def page_state_key(self) -> tuple[str, str, tuple[tuple[str, str], ...]]:
        """Normalized tuple representing the observable page state for loop detection."""
        norm_text = " ".join(self.visible_text.split())
        sorted_forms = tuple(sorted(self.form_snapshot.items()))
        return (self.url.strip(), norm_text, sorted_forms)


def parse_html_page(html: str, current_url: str, max_text_chars: int = 3000) -> PageObservation:
    """Parse HTML into structured PageObservation with compact elements and visible text."""
    parser = _HTMLPageExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass

    title = " ".join(parser.title.split())
    # Clean text chunks and join with newlines/spaces
    full_text = "\n".join(parser._text_chunks)
    # Deduplicate consecutive whitespace/newlines
    clean_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()
    visible_text = clean_text[:max_text_chars]

    # Limit interactive elements to 35 items to respect token budget
    elements = parser.interactive_elements[:35]

    return PageObservation(
        url=current_url,
        title=title,
        visible_text=visible_text,
        interactive_elements=elements,
        form_snapshot=parser.form_snapshot,
    )


async def get_page_observation(
    mcp_client: PlaywrightMCPClient,
    current_url: str,
    max_text_chars: int = 3000,
) -> PageObservation:
    """Retrieve visible HTML from MCP client and parse into PageObservation.

    Falls back cleanly to playwright_get_visible_text if HTML is unavailable.
    """
    raw_html = ""
    try:
        res = await mcp_client.call_tool(
            "playwright_get_visible_html",
            {"removeScripts": True, "removeStyles": True, "maxLength": 30000},
        )
        if isinstance(res, dict):
            content_list = res.get("content", [])
            if isinstance(content_list, list) and content_list:
                first = content_list[0]
                if isinstance(first, dict):
                    raw_html = first.get("text", "")
            if not raw_html:
                raw_html = res.get("html", "") or res.get("text", "")
        elif isinstance(res, str):
            raw_html = res
    except Exception:
        raw_html = ""

    if raw_html and any(tag in raw_html.lower() for tag in ("<html", "<body", "<div")):
        return parse_html_page(raw_html, current_url=current_url, max_text_chars=max_text_chars)

    # Fallback to visible text if HTML tool fails or returns non-HTML
    raw_text = ""
    try:
        text_res = await mcp_client.call_tool("playwright_get_visible_text", {})
        if isinstance(text_res, dict):
            raw_text = text_res.get("text", "") or str(text_res.get("content", ""))
        elif isinstance(text_res, str):
            raw_text = text_res
    except Exception:
        raw_text = ""

    clean_text = " ".join(raw_text.split())[:max_text_chars]
    return PageObservation(
        url=current_url,
        title="",
        visible_text=clean_text,
        interactive_elements=[],
        form_snapshot={},
    )
