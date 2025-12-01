from langgraph.graph import StateGraph, END
from state import NewsState
from parse_input import parse_input
from news_sentiment import fetch_sentiment_rows


def create_lookup_graph():
    graph = StateGraph(NewsState)
    graph.set_entry_point("parse_input")

    graph.add_node("parse_input", parse_input)
    graph.add_node("search_news", fetch_sentiment_rows)

    graph.add_edge("parse_input", "search_news")
    graph.add_edge("search_news", END)

    return graph.compile()
