import textwrap
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from state import AgentState, NewsState
from news_agent import news_agent

app = FastAPI(title="Stock News Sentiment API")


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
