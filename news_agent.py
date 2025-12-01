from typing import cast
from langchain_core.runnables import RunnableConfig
from state import AgentState, NewsState
from news_graph import create_lookup_graph
from news_adapters import into_news_state, out_of_news_state


async def news_agent(parent: AgentState):
    in_state = into_news_state(parent, NewsState())
    result = await create_lookup_graph().ainvoke(
        in_state,
        config=cast(RunnableConfig, cast(object, {"recursion_limit": 100}))
    )

    out_state = out_of_news_state(parent, result)

    return out_state
