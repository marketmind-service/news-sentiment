from langgraph.graph import StateGraph, END
from state import NewsState
from parse_input import parse_input
from news_sentiment import news_sentiment


def create_news_graph():
    graph = StateGraph(NewsState)
    graph.set_entry_point("parse_input")

    graph.add_node("parse_input", parse_input)
    graph.add_node("search_news", news_sentiment)

    graph.add_edge("parse_input", "news_sentiment")
    graph.add_edge("news_sentiment", END)

    return graph.compile()
