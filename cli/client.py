from __future__ import annotations

import json
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://xiaoce.fun"
DEFAULT_PATH = "/baike"
USER_AGENT = "guess-baike/0.1.0 (+https://xiaoce.fun/baike)"


@dataclass(slots=True)
class PageInfo:
    title: str
    module_scripts: list[str]
    stylesheets: list[str]
    html: str


@dataclass(slots=True)
class BaikePuzzle:
    title: str
    author: str | None
    paragraphs: list[list[str]]
    date: str
    raw_response: dict[str, Any]


class _BaikeHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self.title_chunks: list[str] = []
        self.module_scripts: list[str] = []
        self.stylesheets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "title":
            self._in_title = True
            return
        if tag == "script" and attr_map.get("type") == "module" and attr_map.get("src"):
            self.module_scripts.append(attr_map["src"])
            return
        if tag == "link" and attr_map.get("rel") == "stylesheet" and attr_map.get("href"):
            self.stylesheets.append(attr_map["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_chunks.append(data)


def _request(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_html(path: str = DEFAULT_PATH) -> PageInfo:
    html = _request(f"{BASE_URL}{path}")
    parser = _BaikeHTMLParser()
    parser.feed(html)
    return PageInfo(
        title="".join(parser.title_chunks).strip(),
        module_scripts=parser.module_scripts,
        stylesheets=parser.stylesheets,
        html=html,
    )


def _fetch_json(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    query = f"?{urlencode(params)}" if params else ""
    payload = _request(f"{BASE_URL}{path}{query}")
    return json.loads(payload)


def get_latest_daily_date() -> str:
    response = _fetch_json("/api/v0/quiz/daily/getDateV1")
    data = response.get("data")
    if not response.get("success") or not isinstance(data, str):
        raise RuntimeError(f"Unexpected date response: {response}")
    return data


def get_baike_puzzle(
    *,
    date: str | None = None,
    sub_type: str | None = None,
    infinity: bool = False,
    author: str | None = None,
) -> BaikePuzzle:
    params: dict[str, str] = {}
    if date:
        params["date"] = date
    if sub_type:
        params["subType"] = sub_type
    if author:
        params["author"] = author

    path = "/api/v0/quiz/daily/baike/infinity/get" if infinity else "/api/v0/quiz/daily/baike/get"
    response = _fetch_json(path, params or None)
    if not response.get("success"):
        raise RuntimeError(f"Baike request failed: {response}")

    payload = response["data"]
    puzzle = payload["data"]
    paragraphs = _normalize_paragraphs(puzzle["content"]["paragraphs"])
    return BaikePuzzle(
        title=puzzle["title"],
        author=puzzle.get("author"),
        paragraphs=paragraphs,
        date=payload["date"],
        raw_response=response,
    )


def _normalize_paragraphs(paragraphs: list[Any]) -> list[list[str]]:
    normalized: list[list[str]] = []
    for paragraph in paragraphs:
        if isinstance(paragraph, str):
            normalized.append([paragraph])
        elif isinstance(paragraph, list):
            normalized.append([segment for segment in paragraph if isinstance(segment, str)])
        else:
            raise RuntimeError(f"Unexpected paragraph payload: {paragraph!r}")
    return normalized
