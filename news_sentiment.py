import sys
import re
import time
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
from urllib.parse import quote_plus
from state import NewsState

import requests
import feedparser
import yfinance as yf

# Sentiment that ships its own lexicon
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

try:
    from yahooquery import search as yq_search

    HAVE_YQ = True
except Exception:
    HAVE_YQ = False

try:
    from newspaper import Article

    HAVE_NEWS = True
except Exception:
    HAVE_NEWS = False

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
HTTP_TIMEOUT = 10

# Tight ticker check so "nvidia" is treated as a name, not a ticker
TICKER_RE = re.compile(r"^[A-Z0-9]{1,6}([.\-][A-Z0-9]{1,4})?$")


def is_likely_ticker(q: str) -> bool:
    return bool(TICKER_RE.match(q.strip().upper()))


def resolve_symbol_and_name(query: str) -> Tuple[str, Optional[str]]:
    q = query.strip()

    def yf_name(sym: str) -> Optional[str]:
        try:
            t = yf.Ticker(sym)
            # get_info is flaky sometimes; try both
            info = {}
            try:
                info = t.get_info() or {}
            except Exception:
                pass
            name = info.get("shortName") or info.get("longName")
            if not name:
                fast = getattr(t, "fast_info", None)
                if fast and isinstance(fast, dict):
                    name = fast.get("shortName") or fast.get("longName")
            return name
        except Exception:
            return None

    if is_likely_ticker(q):
        sym = q.upper()
        name = yf_name(sym)
        return sym, name

    if HAVE_YQ:
        try:
            res = yq_search(q)
            quotes = res.get("quotes", []) if isinstance(res, dict) else []
            # Prefer equities; otherwise take the first thing with a symbol
            equities = [it for it in quotes if str(it.get("quoteType", "")).upper() == "EQUITY"]
            best = equities[0] if equities else (quotes[0] if quotes else {})
            sym = (best.get("symbol") or best.get("ticker") or q).upper()
            name = best.get("longname") or best.get("shortname") or yf_name(sym)
            return sym, name
        except Exception:
            pass

    # Last resort: treat as ticker
    return q.upper(), yf_name(q.upper())


def fetch_url(url: str) -> Optional[bytes]:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception:
        pass
    return None


def rss_google_news(symbol: str, company_name: Optional[str]) -> List[Dict[str, Any]]:
    q_parts = [symbol]
    if company_name:
        q_parts.extend([
            f"\"{company_name}\"",
            f"\"{company_name}\" stock",
            f"{company_name} ticker"
        ])
    q = " OR ".join(q_parts)
    url = f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-US&gl=US&ceid=US:en"
    content = fetch_url(url)
    items: List[Dict[str, Any]] = []
    if not content:
        return items
    feed = feedparser.parse(content)
    for e in feed.entries:
        title = getattr(e, "title", "")
        link = getattr(e, "link", "")
        # publisher from source or author
        pub = ""
        try:
            pub = e.source.title  # type: ignore[attr-defined]
        except Exception:
            pub = getattr(e, "author", "") or ""
        ts_struct = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        if not title or not link or not ts_struct:
            continue
        ts = int(time.mktime(ts_struct))
        items.append({"title": title.strip(), "link": link.strip(), "publisher": pub.strip(), "ts": ts})
    return items


def rss_bing_news(symbol: str, company_name: Optional[str]) -> List[Dict[str, Any]]:
    q = f"{symbol} {company_name or ''}".strip()
    url = f"https://www.bing.com/news/search?q={quote_plus(q)}&format=RSS"
    content = fetch_url(url)
    items: List[Dict[str, Any]] = []
    if not content:
        return items
    feed = feedparser.parse(content)
    for e in feed.entries:
        title = getattr(e, "title", "")
        link = getattr(e, "link", "")
        pub = ""
        try:
            pub = e.source.title  # type: ignore[attr-defined]
        except Exception:
            pub = getattr(e, "author", "") or ""
        ts_struct = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        if not title or not link or not ts_struct:
            continue
        ts = int(time.mktime(ts_struct))
        items.append({"title": title.strip(), "link": link.strip(), "publisher": pub.strip(), "ts": ts})
    return items


def rss_yahoo_finance(symbol: str) -> List[Dict[str, Any]]:
    urls = [
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(symbol)}&lang=en-US",
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(symbol)}&region=US&lang=en-US",
    ]
    items: List[Dict[str, Any]] = []
    for url in urls:
        content = fetch_url(url)
        if not content:
            continue
        feed = feedparser.parse(content)
        for e in feed.entries:
            title = getattr(e, "title", "")
            link = getattr(e, "link", "")
            pub = ""
            try:
                pub = e.source.title  # type: ignore[attr-defined]
            except Exception:
                pub = getattr(e, "author", "") or ""
            ts_struct = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
            if not title or not link or not ts_struct:
                continue
            ts = int(time.mktime(ts_struct))
            items.append({"title": title.strip(), "link": link.strip(), "publisher": pub.strip(), "ts": ts})
        if items:
            break
    return items


def yf_property_news(symbol: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    try:
        t = yf.Ticker(symbol)
        raw = t.news or []
        for it in raw:
            title = it.get("title") or it.get("headline")
            link = it.get("link") or it.get("url")
            pub = it.get("publisher") or it.get("source") or ""
            ts = it.get("providerPublishTime") or it.get("published_at")
            if not title or not link or not ts:
                continue
            try:
                tsf = float(ts)
            except Exception:
                continue
            items.append({"title": title.strip(), "link": link.strip(), "publisher": pub.strip(), "ts": int(tsf)})
    except Exception:
        pass
    return items


def dedup_and_sort(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for it in items:
        key = (it["title"], it["link"])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    out.sort(key=lambda x: x["ts"], reverse=True)
    return out


def classify(comp: float) -> str:
    if comp >= 0.05:
        return "pos"
    if comp <= -0.05:
        return "neg"
    return "neu"


def sentiment_rows(items: List[Dict[str, Any]], use_article_body: bool) -> List[Dict[str, Any]]:
    sia = SentimentIntensityAnalyzer()
    rows: List[Dict[str, Any]] = []
    for it in items:
        text = it["title"]
        if use_article_body and HAVE_NEWS:
            try:
                art = Article(it["link"])
                art.download()
                art.parse()
                body = ((art.title or "") + "\n" + (art.text or "")).strip()
                if body:
                    # keep it quick
                    text = body[:2000]
            except Exception:
                pass
        score = sia.polarity_scores(text)
        comp = float(score.get("compound", 0.0))
        rows.append({
            "published": datetime.fromtimestamp(it["ts"]).strftime("%Y-%m-%d %H:%M"),
            "publisher": it["publisher"],
            "title": it["title"],
            "link": it["link"],
            "compound": comp,
            "label": classify(comp),
        })
    return rows


def print_summary(rows: List[Dict[str, Any]], symbol: str, name: Optional[str], used_body: bool):
    print("")
    print("=== News Sentiment Snapshot ===")
    print(f"Symbol:   {symbol}")
    print(f"Name:     {name or 'n/a'}")
    print(f"Source:   {'headline + body' if used_body and HAVE_NEWS else 'headline only'}")
    if not rows:
        print("No news found.")
        return
    comps = [r["compound"] for r in rows]
    avg = sum(comps) / len(comps)
    med = sorted(comps)[len(comps) // 2] if comps else 0.0
    pos = sum(1 for r in rows if r["label"] == "pos")
    neu = sum(1 for r in rows if r["label"] == "neu")
    neg = sum(1 for r in rows if r["label"] == "neg")
    print(f"Items: {len(rows)}   Avg: {avg:+.3f}   Median: {med:+.3f}   Breakdown: +{pos} / 0 {neu} / -{neg}")
    print("")


def print_ranked(rows: List[Dict[str, Any]], limit: int):
    if not rows:
        print("No recent news found.")
        return
    print(f"Top {min(limit, len(rows))} recent items:")
    for r in rows[:limit]:
        c = r["compound"]
        tag = "++" if c >= 0.25 else "+" if c >= 0.05 else "--" if c <= -0.25 else "-" if c <= -0.05 else "0"
        print(f"[{tag} {c:+.3f}] {r['published']} | {r['publisher']}: {r['title']}")
        print(f"    {r['link']}")
    print("")


def news_sentiment(state: NewsState) -> NewsState:
    print("News & Sentiment")

    company = state.company
    if not company:
        print("No company provided in state. Exiting news-sentiment node.")
        return state.model_copy(update={
            "error": "[news_sentiment.py] No company provided. Exiting news-sentiment node.",
        })

    try:
        limit = max(1, int(state.items)) if state.items is not None else 20
    except Exception:
        limit = 20

    use_body = False

    symbol, name = resolve_symbol_and_name(company)

    items: List[Dict[str, Any]] = []
    items.extend(rss_google_news(symbol, name))
    if not items:
        items.extend(rss_bing_news(symbol, name))
    if not items:
        items.extend(rss_yahoo_finance(symbol))
    if not items:
        items.extend(yf_property_news(symbol))

    items = dedup_and_sort(items)[:limit]

    rows = sentiment_rows(items, use_article_body=use_body)

    print_summary(rows, symbol, name, used_body=use_body)
    print_ranked(rows, limit=min(12, limit))
    print("Done.")

    return state.model_copy(update={
        "company": name or company,
        "items": len(rows),
        "symbol": symbol,
        "rows": rows,
        "error": None,
    })


def main():
    query = input("Ticker or company: ").strip()
    if not query:
        print("No query provided. Exiting.")
        sys.exit(1)

    raw_limit = input("How many headlines to analyze [Default 20]: ").strip() or "20"
    try:
        limit = max(1, int(raw_limit))
    except Exception:
        limit = 20

    use_body = False
    if HAVE_NEWS:
        yn = input("Use full article text when available (slower) [y/N]: ").strip().lower()
        use_body = yn in {"y", "yes", "1", "true", "t"}

    symbol, name = resolve_symbol_and_name(query)

    # Pull from strongest to weakest
    items: List[Dict[str, Any]] = []
    items.extend(rss_google_news(symbol, name))
    if not items:
        items.extend(rss_bing_news(symbol, name))
    if not items:
        items.extend(rss_yahoo_finance(symbol))
    if not items:
        items.extend(yf_property_news(symbol))

    items = dedup_and_sort(items)[:limit]

    rows = sentiment_rows(items, use_article_body=use_body)
    print_summary(rows, symbol, name, used_body=use_body)
    print_ranked(rows, limit=min(12, limit))
    print("Done.")


# --- UI-friendly helper for frontend ---
def fetch_sentiment_rows(query: str, limit: int = 20, use_body: bool = False):
    symbol, name = resolve_symbol_and_name(query)
    items = []
    items.extend(rss_google_news(symbol, name))
    if not items:
        items.extend(rss_bing_news(symbol, name))
    if not items:
        items.extend(rss_yahoo_finance(symbol))
    if not items:
        items.extend(yf_property_news(symbol))
    items = dedup_and_sort(items)[:max(1, int(limit))]
    rows = sentiment_rows(items, use_article_body=use_body)
    return {"symbol": symbol, "name": name, "rows": rows}


if __name__ == "__main__":
    try:
        news_sentiment()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
