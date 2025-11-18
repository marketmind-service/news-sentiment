# app.py
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from news_sentiment import (
    fetch_sentiment_rows,
    resolve_symbol_and_name,
    HAVE_NEWS,
)

app = FastAPI(title="Stock News Sentiment API")


def summarize_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "avg_compound": None,
            "median_compound": None,
            "pos": 0,
            "neu": 0,
            "neg": 0,
        }

    comps = [float(r["compound"]) for r in rows]
    comps_sorted = sorted(comps)
    n = len(comps_sorted)
    median = comps_sorted[n // 2] if n % 2 == 1 else (
        comps_sorted[n // 2 - 1] + comps_sorted[n // 2]
    ) / 2.0

    pos = sum(1 for r in rows if r.get("label") == "pos")
    neu = sum(1 for r in rows if r.get("label") == "neu")
    neg = sum(1 for r in rows if r.get("label") == "neg")

    return {
        "count": n,
        "avg_compound": sum(comps) / n if n else None,
        "median_compound": median,
        "pos": pos,
        "neu": neu,
        "neg": neg,
    }


@app.get("/healthz")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sentiment")
def sentiment_api(
    query: str = Query(..., description="Ticker or company name"),
    limit: int = Query(20, ge=1, le=100, description="Number of headlines to analyze"),
    use_body: bool = Query(
        False,
        description="Try to use full article text when available (slower, needs newspaper3k)",
    ),
):
    """
    Example:
    /api/sentiment?query=NVDA&limit=20&use_body=false
    """

    if not query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    # If newspaper3k is not available, ignore use_body flag
    effective_use_body = bool(use_body and HAVE_NEWS)

    try:
        symbol, name = resolve_symbol_and_name(query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Symbol resolution failed: {e}")

    try:
        data = fetch_sentiment_rows(
            query=query,
            limit=limit,
            use_body=effective_use_body,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sentiment fetch failed: {e}")

    rows = data.get("rows", [])
    summary = summarize_rows(rows)

    return JSONResponse(
        {
            "symbol": data.get("symbol") or symbol,
            "name": data.get("name") or name,
            "requested_limit": limit,
            "used_body": effective_use_body,
            "summary": summary,
            "rows": rows,
        }
    )