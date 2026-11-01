"""S3a part 4: citation verification for web-cited traits.

S2 checked only that a cited URL was a page the model opened, not that the page supports the value, and accepted
weak sources (a museum store page, a dictionary, a children's encyclopedia). Now every cited field must pass two
checks in code:

1. Source tier (data/source_tiers.json): tier 1 = university, museum, government, peer-reviewed or Animal
   Diversity Web; tier 2 = zoos, aquariums, major science media. Stores, dictionaries, children's encyclopedias and
   general wikis are rejected; an unlisted domain is not accepted either.
2. Quote on the page: the page is fetched in code (PDF sources through pypdf) and the model-extracted supporting
   quote (`evidence`) must appear in its text (normalized: case, punctuation, whitespace, HTML entities; "..." splits the quote into
   segments that must each appear, in order).
3. Subject: the page must name the animal (common name, scientific name or genus). A true quote from a page about
   another animal (the mammoth's lungs from a whale guide) does not support the field.

A field that fails either check falls back to "model-estimated" with the reason recorded. The value itself is not
changed here: it is no longer called cited.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

TIERS_PATH = Path(__file__).resolve().parents[3] / "data" / "source_tiers.json"
SUPPORTED = "supported"
MIN_QUOTE_WORDS = 4  # a shorter quote proves little; it must still be found, but is flagged as short

Fetch = Callable[[str], Awaitable[str]]


@lru_cache
def tiers(path: Path = TIERS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def host_of(url: str) -> str:
    h = (urlparse(url.strip()).hostname or "").lower()
    return h.removeprefix("www.")


def _under(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def classify(url: str, extra: dict[str, int] | None = None) -> dict[str, Any]:
    """{tier: 1 | 2 | None, status: tier1 | tier2 | rejected | unlisted | no_url, reason}."""
    host = host_of(url)
    if not host:
        return {"tier": None, "status": "no_url", "reason": "no URL", "host": ""}
    for dom, t in (extra or {}).items():
        if _under(host, dom):
            return {"tier": t, "status": f"tier{t}", "reason": "fixture source (mock mode)", "host": host}
    rej = tiers()["rejected"]
    for dom, why in rej["domains"].items():
        if _under(host, dom):
            return {"tier": None, "status": "rejected", "reason": rej["reasons"][why], "host": host}
    labels = host.split(".")
    for word, why in rej["host_words"].items():
        if any(word in lab for lab in labels[:-1]):
            return {"tier": None, "status": "rejected", "reason": rej["reasons"][why], "host": host}
    t1 = tiers()["tier1"]
    if any(host.endswith(s) for s in t1["suffixes"]) or any(_under(host, d) for d in t1["domains"]):
        return {"tier": 1, "status": "tier1", "reason": "university, museum, government, peer-reviewed or ADW",
                "host": host}
    t2 = tiers()["tier2"]
    if any(_under(host, d) for d in t2["domains"]) or any(p in lab for p in t2["patterns"] for lab in labels[:-1]):
        return {"tier": 2, "status": "tier2", "reason": "zoo, aquarium or major science media", "host": host}
    return {"tier": None, "status": "unlisted", "reason": "domain not in data/source_tiers.json", "host": host}


# ------------------------------------------------------------------ quote matching

_TAGS = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)


def page_text(raw: str) -> str:
    return html.unescape(_TAGS.sub(" ", raw))


def norm(text: str) -> list[str]:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[‘’“”'\"`]", "", t)
    return re.findall(r"[a-z0-9]+", t)


def _find(seq: list[str], sub: list[str], start: int) -> int:
    n = len(sub)
    first = sub[0]
    i = start
    while True:
        try:
            i = seq.index(first, i)
        except ValueError:
            return -1
        if seq[i:i + n] == sub:
            return i
        i += 1


def quote_found(quote: str, text: str) -> bool:
    """Every "..."-separated segment of the quote appears in the page text, in order, word for word (after
    normalization)."""
    page = norm(text)
    pos = 0
    segs = [norm(s) for s in re.split(r"\.\.\.|…|\[\.\.\.\]", quote)]
    segs = [s for s in segs if s]
    if not segs:
        return False
    for s in segs:
        i = _find(page, s, pos)
        if i < 0:
            return False
        pos = i + len(s)
    return True


# ------------------------------------------------------------------ verification


@dataclass
class Check:
    field: str
    url: str
    host: str
    tier: int | None
    source_status: str  # tier1 | tier2 | rejected | unlisted | no_url
    quote: str
    quote_status: str  # found | not_found | no_quote | fetch_failed | not_checked
    status: str  # supported | rejected_source | unlisted_source | quote_not_found | off_subject | no_quote | fetch_failed
    #              | uncited
    provenance: str  # web-cited | model-estimated
    reason: str
    short_quote: bool = False


class CitationVerifier:
    """Checks every cited field's tier and quote. One fetch per URL (pages are cached for the verifier's life)."""

    def __init__(self, fetch: Fetch, extra_tiers: dict[str, int] | None = None) -> None:
        self.fetch = fetch
        self.subject: list[str] = []  # words naming the animal; the page must mention one (set by verify)
        self.extra = extra_tiers or {}
        self.pages: dict[str, str | Exception] = {}

    async def _page(self, url: str) -> str | Exception:
        if url not in self.pages:
            try:
                self.pages[url] = page_text(await self.fetch(url))
            except Exception as e:  # noqa: BLE001 - any fetch failure means "not verified"
                self.pages[url] = e
        return self.pages[url]

    async def check(self, field: str, url: str, quote: str) -> Check:
        src = classify(url, self.extra)
        quote = (quote or "").strip()
        base = {"field": field, "url": url, "host": src["host"], "tier": src["tier"], "source_status": src["status"],
                "quote": quote, "short_quote": 0 < len(norm(quote)) < MIN_QUOTE_WORDS}
        if src["status"] == "no_url":
            return Check(**base, quote_status="not_checked", status="uncited", provenance="model-estimated",
                         reason="no citation")
        if src["tier"] is None:
            st = "rejected_source" if src["status"] == "rejected" else "unlisted_source"
            return Check(**base, quote_status="not_checked", status=st, provenance="model-estimated",
                         reason=f"{src['host']}: {src['reason']}")
        if not quote:
            return Check(**base, quote_status="no_quote", status="no_quote", provenance="model-estimated",
                         reason="no supporting quote given")
        page = await self._page(url)
        if isinstance(page, Exception):
            return Check(**base, quote_status="fetch_failed", status="fetch_failed", provenance="model-estimated",
                         reason=f"page could not be fetched: {type(page).__name__}: {str(page)[:100]}")
        if not quote_found(quote, page):
            return Check(**base, quote_status="not_found", status="quote_not_found", provenance="model-estimated",
                         reason="the quote does not appear on the page")
        words = set(norm(page))
        if self.subject and not any(all(t in words for t in norm(term)) for term in self.subject):
            return Check(**base, quote_status="found", status="off_subject", provenance="model-estimated",
                         reason=f"the quote is on the page, but the page never names the animal ({self.subject[0]})")
        return Check(**base, quote_status="found", status=SUPPORTED, provenance="web-cited",
                     reason=f"tier {src['tier']} source; quote found on the page")

    async def verify(self, citations: dict[str, dict[str, Any]],
                     subject: list[str] | None = None) -> dict[str, dict[str, Any]]:
        """{field: Check as a dict} for every field in `citations` ({url, evidence}). `subject`: names of the animal
        (common name, scientific name, genus); a page that names none of them does not support the field."""
        self.subject = [x for x in (subject or []) if x]
        out = {}
        for f, c in citations.items():
            out[f] = asdict(await self.check(f, str(c.get("url") or ""), str(c.get("evidence") or "")))
        return out


async def http_fetch(url: str, timeout: float = 25.0) -> str:
    """Live page fetch (browser-like headers; redirects followed). Raises on HTTP >= 400."""
    import httpx

    headers = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0 Safari/537.36"),
               "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
               "Accept-Language": "en-US,en;q=0.9"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        if "pdf" in resp.headers.get("content-type", "").lower() or resp.content[:5] == b"%PDF-":
            return pdf_text(resp.content)
        return resp.text


def pdf_text(data: bytes) -> str:
    """The text of a PDF source (pypdf), so a quote from a fact sheet can be checked like a web page."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def summary(checks: dict[str, dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in checks.values():
        out[c["status"]] = out.get(c["status"], 0) + 1
    return out
