import os
from typing import List, Optional, TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import AzureChatOpenAI

from dotenv import load_dotenv

load_dotenv()

AZURE_OAI_KEY = os.getenv("AZURE_OAI_KEY")
END_POINT = os.getenv("END_POINT")
DEPLOYMENT_NAME = "gpt-4o"
API_VERSION_GPT = os.getenv("API_VERSION_GPT")

llm = AzureChatOpenAI(
    azure_deployment=DEPLOYMENT_NAME,
    openai_api_version=API_VERSION_GPT,
    azure_endpoint=END_POINT,
    api_key=AZURE_OAI_KEY,
    temperature=0
)

# Define state schema using TypedDict
class State(TypedDict):
    conversation_history: List
    product_name: Optional[str]
    current_node: str

def greet(state):
    msg = "Hey there! I'm your Pollen assistant. Which product are we building audiences for?"
    state["conversation_history"].append(AIMessage(content=msg))
    state["current_node"] = "DONE"
    return state

def create_workflow():
    # Pass the State class (not an instance) to StateGraph
    graph = StateGraph(State)
    graph.add_node("greet", greet)
    graph.set_entry_point("greet")
    
    # Add edge to END
    graph.add_edge("greet", END)
    
    return graph.compile()

def get_initial_state():
    return {
        "conversation_history": [],
        "product_name": None,
        "current_node": "greet",
    }

# Create the workflow using the State class
workflow = create_workflow()

# Initialize state
state = get_initial_state()

# Process through the workflow
for step_result in workflow.stream(state):
    print("Current step result:", step_result)

    node_name = next(iter(step_result))
    actual_state = step_result[node_name]

    # Access conversation_history from actual_state, not step_result
    msgs = actual_state["conversation_history"]
    
    if msgs and isinstance(msgs[-1], AIMessage):
        print("\n\nAI Message:", msgs[-1].content)
    
    # Update state with the actual state
    state = actual_state
