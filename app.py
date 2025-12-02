import textwrap
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from state import AgentState, NewsState
from news_agent import news_agent

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


@app.post("/api/news-agent", response_model=AgentState)
async def run_news(state: AgentState):
    try:
        updated_state = await news_agent(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"news_agent_error: {e}")

    return updated_state


async def local_cli():
    print("MarketMind CLI (type 'exit' to quit)")
    while True:
        prompt = input("\nYou: ").strip()
        if not prompt or prompt.lower() in {"exit", "quit"}:
            print("Done.")
            break
        state = AgentState(prompt=prompt)
        try:
            result = await news_agent(state)
            print(textwrap.dedent(f"""
                ========================================== RESULTS ==========================================
                Prompt: {result.prompt}
                ------------------------------------------------
                Search: {result.lookup_result or "None"}
                News: {result.news_result or "None"}
                =============================================================================================
            """).strip())
        except Exception as e:
            print("Error:", e)


if __name__ == "__main__":
    import asyncio
    asyncio.run(local_cli())
