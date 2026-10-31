#!/usr/bin/env python3
"""Verify the Chimera Lab research docs.

Usage: python scripts/verify_research.py [folder]   (default: docs/evolution/research)

Checks every .md file in the folder:
  1. every http(s) link resolves with status < 400 (403s reported separately)
  2. every "### RC-R<digit>-<number>" card has rule, applies_to, strength, status, source
  3. strength is hard|soft, status is VERIFIED|UNVERIFIED
  4. no card is strength: hard with status: UNVERIFIED
  5. a VERIFIED card whose source link is dead (not a 403) is flagged
  6. no em dashes in any doc

A link whose cert chain fails local verification but resolves without it is
reported as an SSL warning, not a failure.

A link that times out is reported as a TIMEOUT warning, not a failure, only if
it appears in the "## Resolved links" section of the history report (default:
VERIFY_REPORT.md in the parent of the folder; override with --history PATH).
A timeout on a link that has never resolved is still a failure.

Every link that resolves (status < 400) is printed as an OK line so the report
can record it in its "## Resolved links" section for later runs.

Standard library only. Exit 0 if clean, 1 if not.
"""
from __future__ import annotations

import re
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FIELDS = ("rule", "applies_to", "strength", "status", "source")
CARD_RE = re.compile(r"^### (RC-R\d-\d+)\s*$")
HEADING_RE = re.compile(r"^#{1,6} ")
FIELD_RE = re.compile(r"^(rule|applies_to|strength|status|source):\s*(.*)$")
URL_RE = re.compile(r"https?://[^\s<>\"'`]+")
TRAILING = ".,;:!?)]}>*_"
EM_DASH = "—"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 20
SSL_WARN = "SSL_WARNING"


def clean_url(url: str) -> str:
    # Strip trailing markdown/punctuation; keep a closing paren if balanced.
    while url and url[-1] in TRAILING:
        if url[-1] == ")" and url.count("(") >= url.count(")"):
            break
        url = url[:-1]
    return url


def parse_cards(path: Path) -> list[dict]:
    cards: list[dict] = []
    cur: dict | None = None
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = CARD_RE.match(line)
        if m:
            cur = {"id": m.group(1), "line": lineno, "fields": {}}
            cards.append(cur)
            continue
        if cur is None:
            continue
        if HEADING_RE.match(line) or line.strip() == "---":
            cur = None
            continue
        fm = FIELD_RE.match(line.strip())
        if fm and fm.group(1) not in cur["fields"]:
            cur["fields"][fm.group(1)] = fm.group(2).strip()
    return cards


def check_url(url: str) -> tuple[str, int | None, str]:
    ctx = ssl.create_default_context()
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    last_err = ""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
                return url, resp.status, ""
        except urllib.error.HTTPError as e:
            # Many servers reject HEAD; retry with GET before trusting the code.
            if method == "HEAD" and e.code in (400, 403, 404, 405, 406, 429, 500, 501, 503):
                last_err = f"HTTP {e.code}"
                continue
            return url, e.code, f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001 - network errors of every kind
            last_err = f"{type(e).__name__}: {e}"
            if _is_cert_error(e):
                return _check_insecure(url, headers)
            if method == "HEAD":
                continue
            return url, None, last_err
    return url, None, last_err


def _is_cert_error(e: Exception) -> bool:
    reason = getattr(e, "reason", e)
    return isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(e)


def _check_insecure(url: str, headers: dict) -> tuple[str, int | None, str]:
    """Certificate chain rejected by the local trust store (often a server that
    omits its intermediate cert). Retry without verification: if the page then
    resolves, report an SSL warning instead of a failure."""
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            return url, resp.status, SSL_WARN
    except urllib.error.HTTPError as e:
        return url, e.code, f"HTTP {e.code} (after SSL verify failure)"
    except Exception as e:  # noqa: BLE001
        return url, None, f"{type(e).__name__}: {e} (after SSL verify failure)"


def _is_timeout(err: str) -> bool:
    return "timed out" in err.lower() or "TimeoutError" in err


def load_history(path: Path) -> set[str]:
    """URLs listed under '## Resolved links' in an earlier VERIFY_REPORT.md."""
    if not path.is_file():
        return set()
    urls: set[str] = set()
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_section = line.strip().lower().startswith("## resolved links")
            continue
        if in_section:
            urls.update(clean_url(u) for u in URL_RE.findall(line))
    return urls


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    history_path: Path | None = None
    if "--history" in args:
        i = args.index("--history")
        history_path = Path(args[i + 1])
        del args[i:i + 2]
    folder = Path(args[0]) if args else Path("docs/evolution/research")
    if history_path is None:
        history_path = folder.parent / "VERIFY_REPORT.md"
    history = load_history(history_path)
    if not folder.is_dir():
        print(f"ERROR {folder}: not a directory")
        return 1
    files = sorted(folder.glob("*.md"))
    problems: list[str] = []
    blocked: list[str] = []
    ssl_warns: list[str] = []
    timeout_warns: list[str] = []
    resolved: list[str] = []
    warned: set[str] = set()

    url_locs: dict[str, list[str]] = {}
    cards_by_file: dict[Path, list[dict]] = {}
    for f in files:
        text = f.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if EM_DASH in line:
                problems.append(f"{f.name}:{lineno} EM_DASH em dash found")
            for raw in URL_RE.findall(line):
                url_locs.setdefault(clean_url(raw), []).append(f"{f.name}:{lineno}")
        cards_by_file[f] = parse_cards(f)

    # Card structure checks.
    for f, cards in cards_by_file.items():
        for c in cards:
            cid, flds = c["id"], c["fields"]
            for name in FIELDS:
                if not flds.get(name):
                    problems.append(f"{f.name} {cid} MISSING_FIELD {name}")
            s, st = flds.get("strength"), flds.get("status")
            if s and s not in ("hard", "soft"):
                problems.append(f"{f.name} {cid} BAD_STRENGTH {s!r}")
            if st and st not in ("VERIFIED", "UNVERIFIED"):
                problems.append(f"{f.name} {cid} BAD_STATUS {st!r}")
            if s == "hard" and st == "UNVERIFIED":
                problems.append(f"{f.name} {cid} HARD_UNVERIFIED hard card is UNVERIFIED")

    # Link checks.
    results: dict[str, tuple[int | None, str]] = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        for url, code, err in pool.map(check_url, sorted(url_locs)):
            results[url] = (code, err)
    for url in sorted(results):
        code, err = results[url]
        where = ", ".join(url_locs[url])
        if code == 403:
            blocked.append(f"{where} {url} (403: likely bot-blocked, check in a browser)")
        elif err == SSL_WARN and code is not None and code < 400:
            ssl_warns.append(f"{where} {url} (HTTP {code} only without cert verification; "
                             "server likely omits its intermediate cert)")
            warned.add(url)
        elif code is None and _is_timeout(err) and url in history:
            timeout_warns.append(f"{where} {url} (timed out; resolved in an earlier recorded "
                                 "run, recheck later)")
            warned.add(url)
        elif code is None or code >= 400:
            problems.append(f"{where} DEAD_LINK {url} ({err or code})")
        if code is not None and code < 400:
            resolved.append(url)

    # VERIFIED cards whose source is dead (not 403).
    for f, cards in cards_by_file.items():
        for c in cards:
            if c["fields"].get("status") != "VERIFIED":
                continue
            for raw in URL_RE.findall(c["fields"].get("source", "")):
                if clean_url(raw) in warned:
                    continue
                code, err = results.get(clean_url(raw), (None, "not checked"))
                if code != 403 and (code is None or code >= 400):
                    problems.append(
                        f"{f.name} {c['id']} VERIFIED_DEAD_SOURCE {clean_url(raw)} ({err or code})"
                    )

    n_cards = sum(len(c) for c in cards_by_file.values())
    print(f"# checked {len(files)} files, {n_cards} cards, {len(results)} unique links")
    for p in problems:
        print(f"FAIL {p}")
    for b in blocked:
        print(f"403  {b}")
    for w in ssl_warns:
        print(f"SSL  {w}")
    for w in timeout_warns:
        print(f"TIME {w}")
    for u in resolved:
        print(f"OK   {u}")
    print(f"# {len(problems)} failures, {len(blocked)} bot-blocked (403), "
          f"{len(ssl_warns)} SSL warnings, {len(timeout_warns)} timeout warnings, "
          f"{len(resolved)} resolved (history: {len(history)} URLs from {history_path})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
