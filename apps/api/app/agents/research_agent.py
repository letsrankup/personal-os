"""Research Agent — real web research via DuckDuckGo HTML search.

Pipeline (no fabricated data anywhere):
  1. Query https://html.duckduckgo.com/html/?q=... with httpx + a UA header.
  2. Parse the top results (title, url, snippet) from the results HTML.
  3. Fetch up to 3 result pages and extract readable text (tags stripped).
  4. Summarize the collected text via the AI provider chain (app.ai.chat),
     with the fetched sources in the prompt.
  5. Save a memories row (kind=research, source URLs in content + tags) and
     return the summary + the source list. Verified by re-reading the
     memory row from the DB.

Competitor analysis uses the same pipeline with a "competitors of X" query.
If the network fails, the agent returns FAILED with the real error.
"""
import html as html_lib
import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from sqlalchemy.orm import Session

from .. import ai
from ..models import Memory, Task
from .base import BaseAgent

_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 PERSONAL-OS Research"}
_DDG_URL = "https://html.duckduckgo.com/html/"
_MAX_RESULTS = 8
_MAX_PAGES = 3
_PAGE_TEXT_LIMIT = 4000

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_RESULT_RE = re.compile(
    r'class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>'
    r'.*?class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
    re.DOTALL,
)


def _clean(fragment: str) -> str:
    text = _ANY_TAG_RE.sub(" ", fragment or "")
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def _real_url(href: str) -> str:
    """DuckDuckGo wraps result links as //duckduckgo.com/l/?uddg=<real>."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    if "uddg" in qs:
        return unquote(qs["uddg"][0])
    return href


def extract_topic(command: str) -> tuple[str, bool]:
    """Pull the research topic out of the raw command. Returns (query, is_competitor)."""
    text = command.strip()
    low = text.lower()
    competitor = False
    m = re.search(r"competitors?\s+of\s+(.+)", low)
    if m:
        topic = text[m.start(1):].strip().rstrip(".")
        return f"competitors of {topic}", True
    if "competitor" in low:
        competitor = True
    cleaned = re.sub(
        r"(?i)\b(research|tahqeeq|investigate|find out|dhoondo|maloom karo|search|about|on|the|a|an|karo|kar|do)\b",
        " ",
        text,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .:,-")
    return (cleaned or text)[:200], competitor


def fetch_results(query: str) -> list[dict]:
    resp = httpx.get(_DDG_URL, params={"q": query}, headers=_UA, timeout=20.0, follow_redirects=True)
    resp.raise_for_status()
    results = []
    for m in _RESULT_RE.finditer(resp.text):
        url = _real_url(html_lib.unescape(m.group("url")))
        if not url.startswith("http"):
            continue
        results.append(
            {"title": _clean(m.group("title")), "url": url, "snippet": _clean(m.group("snippet"))}
        )
        if len(results) >= _MAX_RESULTS:
            break
    if not results and (resp.status_code == 202 or "anomaly-modal" in resp.text or "challenge" in resp.text[:4000].lower()):
        # DuckDuckGo serves a bot-challenge page (HTTP 202) to some clients/IPs
        # instead of results — report that honestly instead of "no results".
        raise RuntimeError(
            f"DuckDuckGo served a bot-challenge page (HTTP {resp.status_code}) with no search "
            "results — the search provider blocked this client/IP."
        )
    return results


def fetch_page_text(url: str) -> str:
    resp = httpx.get(url, headers=_UA, timeout=20.0, follow_redirects=True)
    resp.raise_for_status()
    body = _TAG_RE.sub(" ", resp.text)
    return _clean(body)[:_PAGE_TEXT_LIMIT]


class ResearchAgent(BaseAgent):
    key = "research"
    name = "Research Agent"

    def run(self, db: Session, task: Task, context: dict) -> dict:
        logs: list[str] = []
        query, competitor = extract_topic(task.description)
        logs.append(f"Research query: '{query}' (competitor_analysis={competitor}).")

        try:
            results = fetch_results(query)
        except Exception as exc:  # real network/HTTP failure — report it, never invent results
            msg = f"Web search failed for query '{query}': {type(exc).__name__}: {exc}"
            return {"result": None, "verified": False, "error": msg, "logs": logs + [msg]}
        if not results:
            msg = f"Web search for '{query}' returned no results."
            return {"result": None, "verified": False, "error": msg, "logs": logs + [msg]}
        logs.append(f"DuckDuckGo returned {len(results)} result(s).")

        sources_text = []
        fetched = 0
        for r in results:
            if fetched >= _MAX_PAGES:
                break
            try:
                page_text = fetch_page_text(r["url"])
            except Exception as exc:  # a dead page is skipped, the rest still count
                logs.append(f"Could not fetch {r['url']}: {type(exc).__name__}: {exc}")
                continue
            if page_text:
                fetched += 1
                sources_text.append(f"SOURCE: {r['title']} ({r['url']})\n{page_text}")
        logs.append(f"Fetched readable text from {fetched} page(s).")
        if not sources_text:  # fall back to the snippets DDG itself returned (still real data)
            sources_text = [f"SOURCE: {r['title']} ({r['url']})\n{r['snippet']}" for r in results]
            logs.append("Page fetches yielded no text; using DuckDuckGo snippets as sources.")

        joined = "\n\n".join(sources_text)[:12000]
        prompt = (
            f"Research topic: {query}\n\n"
            "Using ONLY the sources below, write a concise research summary with key findings. "
            "Do not add facts that are not in the sources.\n\n" + joined
        )
        summary = ai.chat(prompt, system="You are the PERSONAL OS Research Agent. Summarize only from the provided sources and cite source titles where useful.")
        logs.append(f"Summary produced via AI provider '{ai.provider_name()}'.")

        source_lines = [f"- {r['title']}: {r['url']}" for r in results]
        result = f"Research summary — {query}\n\n{summary}\n\nSources:\n" + "\n".join(source_lines)

        memory = Memory(
            user_id=task.user_id,
            kind="research",
            title=f"Research: {query}"[:255],
            content=result,
            tags=["research"] + (["competitor"] if competitor else []) + [r["url"] for r in results],
            source_ref=task.id,
        )
        db.add(memory)
        db.flush()
        saved = db.get(Memory, memory.id)  # verify the research was really persisted
        if saved is None:
            msg = "Research memory row could not be verified in the database."
            return {"result": None, "verified": False, "error": msg, "logs": logs + [msg]}
        logs.append(f"Saved research memory row {saved.id} with {len(results)} source URL(s).")
        return {"result": result, "verified": True, "logs": logs}
