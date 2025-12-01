from state import AgentState, NewsState


def into_news_state(parent: AgentState, child: NewsState) -> NewsState:
    return child.model_copy(update={
        "prompt": parent.prompt
    })


def out_of_news_state(parent: AgentState, child: NewsState) -> AgentState:
    return parent.model_copy(update={
        "news_result": child,
        "route_taken": [*parent.route_taken, "news_agent_done"],
    })
