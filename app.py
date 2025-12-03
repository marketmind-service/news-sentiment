import textwrap
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from state import AgentState, NewsState
from news_agent import news_agent
from news_sentiment import news_sentiment

app = FastAPI(title="Stock News Sentiment API")


@app.post("/api/news-agent", response_model=AgentState)
async def run_news(state: AgentState):
    try:
        updated_state = await news_agent(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"news_agent_error: {e}")

    return updated_state


class DirectNewsRequest(BaseModel):
    company: str
    items: int


@app.post("/api/news", response_model=NewsState)
async def direct_news(req: DirectNewsRequest):
    in_state = NewsState(
        company=req.company,
        items=req.items
    )

    try:
        out_state = news_sentiment(in_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"news_error: {e}")

    if out_state.error:
        raise HTTPException(status_code=400, detail=out_state.error)

    return out_state


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
