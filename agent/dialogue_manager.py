import os
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel

from schema import AudienceBuilderState, ProductSearchResults
from tools import ProductLookupTool, transform_to_product_table

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

#
# 1) Pydantic model to parse the Marketing Brief in one shot
#
class MarketingBrief(BaseModel):
    product_name: str
    objectives: str
    budget: str
    channel: str
    duration: str

#
# 2) greet node
#
def greet(state: AudienceBuilderState) -> AudienceBuilderState:
    print(f"\n\nGreeting user from state: {state}")
    
    if state["conversation_history"]:
        return {**state, "current_node": END}

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""You are an audience-building assistant for Pollen.
        Greet the user warmly.
        
        Then **ask for a brief** (product name, objectives, budget, channel, duration)
        so we can get started building the best possible audience.""")
    ])

    chain = prompt | llm
    response = chain.invoke({})

    return {
        **state,
        "conversation_history": state["conversation_history"] + [
            AIMessage(content=response.content)
        ],
        "current_node": "gather_marketing_brief"
    }

#
# 3) gather_marketing_brief node
#
def gather_marketing_brief(state: AudienceBuilderState) -> AudienceBuilderState:
    print(f"\n\nCapturing marketing brief from user. State: {state}")

    # Grab the last user message
    messages = state["conversation_history"]
    last_user_message = None
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            last_user_message = message.content
            break

    if not last_user_message:
        # If we somehow have nothing from user, loop
        return {
            **state,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content="Could you please provide the marketing brief?")
            ],
            "current_node": "gather_marketing_brief"
        }

    # Parse the marketing brief
    parser = PydanticOutputParser(pydantic_object=MarketingBrief)
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""Extract the following from the user's message:
- product_name
- objectives
- budget
- channel
- duration

If you're missing something, fill it with a short placeholder, but do your best to parse it!"""),
        HumanMessage(content=f"User: {last_user_message}\n\n{parser.get_format_instructions()}")
    ])

    chain = prompt | llm | parser

    try:
        brief = chain.invoke({})
    except Exception:
        # Keep it REALLY SIMPLE
        return {
            **state,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content="Sorry, I'm having trouble understanding your brief. Could you restate it clearly?")
            ],
            "current_node": "gather_marketing_brief"
        }

    # Save fields into state
    return {
        **state,
        "product_name": brief.product_name,
        "marketing_objectives": brief.objectives,
        "marketing_budget": brief.budget,
        "marketing_channel": brief.channel,
        "marketing_duration": brief.duration,
        "conversation_history": state["conversation_history"] + [
            AIMessage(content=(
                f"Great! So we're building audiences for '{brief.product_name}', "
                f"with objectives '{brief.objectives}', budget '{brief.budget}', channel '{brief.channel}', "
                f"and duration '{brief.duration}'. Let me pull up relevant product details..."
            ))
        ],
        "current_node": "get_product_table"
    }

#
# 4) get_product_table node
#
def get_product_table(state: AudienceBuilderState) -> AudienceBuilderState:
    print("\n\nFormatting Search Results")
    
    product_name = state.get("product_name")
    
    try:
        product_search_results = state.get("product_search_results")
        if not product_search_results:
            product_lookup_tool = ProductLookupTool()
            product_search_results = product_lookup_tool.invoke(product_name)
            state = {**state, "product_search_results": product_search_results}
        
        product_table = transform_to_product_table(product_search_results)
        state = {**state, "product_table": product_table}
        
        response_prompt = ChatPromptTemplate.from_template("""
        You have been presented with the users marketing brief query, for Audience Building.

        Query: {query}
        Buyer Categories: {buyer_categories}
        Product Categories: {product_categories}
        Total Results: {total_results}

        Detailed data:
        {table_data}

        Provide:
        1) A short reccomendation for the best Product Category & Buyer Category combination

        Do NOT produce an actual table in the text. We'll display it separately.
        """)
        
        table_details = []
        for row in product_table["rows"]:
            sku_samples = ", ".join([f"{s['name']} (SKU: {s['sku']})" for s in row["skus"]])
            table_details.append(
                f"- {row['buyer_category']} > {row['product_category']}:\n"
                f"  * Sample SKUs: {sku_samples}\n"
                f"  * Total SKUs: {row['count']}"
            )
        
        response_chain = response_prompt | llm
        response = response_chain.invoke({
            "query": product_name,
            "buyer_categories": ", ".join(product_search_results.unique_buyer_categories),
            "product_categories": ", ".join(product_search_results.unique_product_categories),
            "total_results": product_search_results.total_results,
            "table_data": "\n\n".join(table_details)
        })

        content = response.content if hasattr(response, 'content') else response

        return {
            **state,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content=content)
            ],
            "current_node": END
        }
        
    except Exception as e:
        print(f"Error in get_product_table: {e}")
        return {
            **state,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content=f"I encountered an error retrieving product details: {str(e)}")
            ],
            "current_node": END
        }

#
# 5) get_initial_state
#
def get_initial_state():
    return {
        "conversation_history": [],
        "product_name": None,
        "product_category": None,
        "buyer_category": None,
        "product_search_results": None,
        "product_table": None,
        "audience_selections": None,
        "marketing_objectives": None,
        "marketing_budget": None,
        "marketing_channel": None,
        "marketing_duration": None,
        "current_node": "greet",
    }

#
# 6) create_workflow
#
def create_workflow():
    workflow = StateGraph(AudienceBuilderState)
    
    workflow.add_node("greet", greet)
    workflow.add_node("gather_marketing_brief", gather_marketing_brief)
    workflow.add_node("get_product_table", get_product_table)

    # Flow: greet -> gather_marketing_brief -> get_product_table -> END
    workflow.add_edge("greet", "gather_marketing_brief")
    workflow.add_edge("gather_marketing_brief", "get_product_table")
    workflow.add_edge("get_product_table", END)

    workflow.set_entry_point("greet")
    
    return workflow.compile()
