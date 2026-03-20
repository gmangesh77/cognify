import re
import xml.etree.ElementTree as ET
from typing import TypedDict

import httpx

from src.services.trends.protocol import TrendSourceError

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"


class ArxivPaper(TypedDict):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    published: str
    updated: str
    pdf_url: str
    abs_url: str
    primary_category: str
    categories: list[str]


class ArxivAPIError(TrendSourceError):
    """Raised when arXiv API is unreachable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__("arxiv", message)


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text


def _parse_entry(entry: ET.Element) -> ArxivPaper:
    raw_id = _text(entry.find(f"{{{_ATOM_NS}}}id"))
    arxiv_id = raw_id.rsplit("/", 1)[-1] if "/" in raw_id else raw_id

    raw_title = _text(entry.find(f"{{{_ATOM_NS}}}title"))
    title = re.sub(r"\s+", " ", raw_title).strip()

    abstract = _text(
        entry.find(f"{{{_ATOM_NS}}}summary"),
    ).strip()

    authors = [
        _text(a.find(f"{{{_ATOM_NS}}}name"))
        for a in entry.findall(f"{{{_ATOM_NS}}}author")
    ]

    published = _text(entry.find(f"{{{_ATOM_NS}}}published"))
    updated = _text(entry.find(f"{{{_ATOM_NS}}}updated"))

    abs_url = ""
    pdf_url = ""
    for link in entry.findall(f"{{{_ATOM_NS}}}link"):
        rel = link.get("rel", "")
        if rel == "alternate":
            abs_url = link.get("href", "")
        elif link.get("title") == "pdf":
            pdf_url = link.get("href", "")

    prim_el = entry.find(f"{{{_ARXIV_NS}}}primary_category")
    primary_category = prim_el.get("term", "") if prim_el is not None else ""

    categories = [
        cat.get("term", "")
        for cat in entry.findall(f"{{{_ATOM_NS}}}category")
        if cat.get("term")
    ]

    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors,
        published=published,
        updated=updated,
        pdf_url=pdf_url,
        abs_url=abs_url,
        primary_category=primary_category,
        categories=categories,
    )


class ArxivClient:
    def __init__(
        self,
        base_url: str,
        timeout: float,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout

    async def fetch_papers(
        self,
        categories: list[str],
        max_results: int,
        sort_by: str,
    ) -> list[ArxivPaper]:
        query = " OR ".join(f"cat:{cat}" for cat in categories)
        params: dict[str, str | int] = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
            ) as client:
                resp = await client.get(
                    self._base_url,
                    params=params,
                )
        except httpx.TimeoutException as exc:
            raise ArxivAPIError(
                f"arXiv timed out: {exc}",
            ) from exc
        except httpx.ConnectError as exc:
            raise ArxivAPIError(
                f"arXiv connection failed: {exc}",
            ) from exc
        if not resp.is_success:
            raise ArxivAPIError(
                f"arXiv returned {resp.status_code}",
            )
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            raise ArxivAPIError(
                f"arXiv XML parse error: {exc}",
            ) from exc
        entries = root.findall(f"{{{_ATOM_NS}}}entry")
        return [_parse_entry(e) for e in entries]
