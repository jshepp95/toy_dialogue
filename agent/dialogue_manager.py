import os
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain.output_parsers import StructuredOutputParser
from langchain_openai import AzureChatOpenAI

from schema import AudienceBuilderState, ProductIdentification, ProductSearchResults
from tools import SKULookupTool, ProductLookupTool

from pprint import pprint

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

def greet(state: AudienceBuilderState) -> AudienceBuilderState:
    print(f"\n\nGreeting user from state: {state}")
    
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""You are an audience building assistant for Pollen.
        Greet the user warmly and ask which product and corresponding SKU they'd like to build audiences for.
        Don't sound cheesy or corporate.""")
    ])

    chain = prompt | llm
    response = chain.invoke({})

    return {
        **state,
        "conversation_history": state["conversation_history"] + [
            AIMessage(content=response.content)
        ],
        "current_node": "identify_product"
    }

def identify_product(state: AudienceBuilderState) -> AudienceBuilderState:
    print(f"\n\n🔍 Identifying product from state: {state}")

    messages = state["conversation_history"]
    
    last_user_message = None
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            last_user_message = message.content
            break

    if not last_user_message:
        return {**state, "current_node": "identify_product"}
    
    parser = PydanticOutputParser(pydantic_object=ProductIdentification)
    
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""Extract the product that the user wants to build audiences for."""),
        HumanMessage(content=f"User Message: {last_user_message}\n\n{parser.get_format_instructions()}")
    ])

    chain = prompt | llm | parser
    result = chain.invoke({})
    
    if not result.product_name:
        return {
            **state,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content="I'm not sure which product you're referring to. Can you clarify?")
            ],
            "current_node": "identify_product"
        }
    else:
        print(f"✅ Found product: {result.product_name}")

        return {
            **state,
            "product_name": result.product_name,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content=f"Got it! You're building audiences for {result.product_name}.")
            ],
            "current_node": END  # 🚀 This ensures the workflow stops looping
        }
    
def route_next_step(state: AudienceBuilderState):
    """Determines which node to go to next based on the current state."""
    return state.get("current_node", "greet")

def get_initial_state():
    """Returns the initial state for the workflow."""
    return {
        "conversation_history": [],
        "product_name": None,
        "product_category": None,
        "buyer_category": None,
        "product_search_results": None,
        "current_node": "greet",
    }

def create_workflow():
    """Creates and returns the compiled workflow."""
    workflow = StateGraph(AudienceBuilderState)
    
    # Add nodes
    workflow.add_node("greet", greet)
    workflow.add_node("identify_product", identify_product)

    # Add edges
    workflow.add_edge("greet", "identify_product")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "identify_product",
        route_next_step,
        {
            "identify_product": "identify_product",
            END: END
        }
    )

    # Set entry point
    workflow.set_entry_point("greet")
    
    return workflow.compile()