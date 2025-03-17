from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from llm import llm_model


class State(TypedDict):
    messages: Annotated[list, add_messages]

def chatbot(state: State) -> State:
    system_message = "You are a helpful assistant."

    response = llm_model.invoke(
        {
            "system_message": system_message,
            "messages": state["messages"]
        }
    )

    return {"messages": [response]}

graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")

graph = graph_builder.compile(checkpointer=MemorySaver())
