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


class MarketingBrief(BaseModel):
    product_name: str
    objectives: str
    budget: str
    channel: str
    duration: str

def greet(state: AudienceBuilderState) -> AudienceBuilderState:
    print(f"\n\nGreeting user from state: {state}")
    
    if state["conversation_history"]:
        return {**state, "current_node": END}

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""You are an audience-building assistant for Pollen.
        Greet the Abhinav warmly.
        
        Use 'some' emojis, but don't overdo it or be too cheesy. Use some bold for emphasis.

        Then **ask for a brief** (product name, objectives, budget, channel, duration) with a super short explanation of each,
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

def gather_marketing_brief(state: AudienceBuilderState) -> AudienceBuilderState:
    print(f"\n\nCapturing marketing brief from user. State: {state}")

    # 1) If we don't already have a 'brief' in state, store a dict with empty strings:
    brief_data = state.get("brief_data", {
        "product_name": "",
        "objectives": "",
        "budget": "",
        "channel": "",
        "duration": ""
    })

    # 2) Grab the last user message
    messages = state["conversation_history"]
    last_user_message = None
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            last_user_message = message.content
            break

    # If no user message yet, politely ask for any marketing brief info
    if not last_user_message:
        return {
            **state,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content="Could you share your Marketing Brief? (Product, Objectives, Budget, Channel, Duration)")
            ],
            "current_node": "gather_marketing_brief"
        }

    # 3) Use the Pydantic parser to try to extract whatever fields are present
    parser = PydanticOutputParser(pydantic_object=MarketingBrief)
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""Extract these fields if present:
- product_name
- objectives
- budget
- channel
- duration

For missing ones, just fill with a short placeholder. 
"""),
        HumanMessage(content=f"{last_user_message}\n\n{parser.get_format_instructions()}")
    ])

    chain = prompt | llm | parser
    
    try:
        parsed_brief = chain.invoke({})  # a MarketingBrief instance
    except Exception:
        # If we can't parse, just ask the user again
        return {
            **state,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content="I wasn't able to understand your details. Could you restate your brief, please?")
            ],
            "current_node": "gather_marketing_brief"
        }

    # 4) Update partial data with newly parsed fields (ignore placeholders)
    #    For any field that's missing, we'll keep our existing data.
    if parsed_brief.product_name and "placeholder" not in parsed_brief.product_name.lower():
        brief_data["product_name"] = parsed_brief.product_name
    if parsed_brief.objectives and "placeholder" not in parsed_brief.objectives.lower():
        brief_data["objectives"] = parsed_brief.objectives
    if parsed_brief.budget and "placeholder" not in parsed_brief.budget.lower():
        brief_data["budget"] = parsed_brief.budget
    if parsed_brief.channel and "placeholder" not in parsed_brief.channel.lower():
        brief_data["channel"] = parsed_brief.channel
    if parsed_brief.duration and "placeholder" not in parsed_brief.duration.lower():
        brief_data["duration"] = parsed_brief.duration

    # 5) Check if all fields are now filled
    missing_fields = [k for k, v in brief_data.items() if not v.strip()]

    if missing_fields:
        # 6) We still need some data. Ask for the missing fields. Remain on the same node.
        missing_str = ", ".join(missing_fields)
        return {
            **state,
            "brief_data": brief_data,  # store partial
            "conversation_history": state["conversation_history"] + [
                AIMessage(content=(
                    f"I still need the following info: {missing_str}.\n"
                    "Please provide them now. You can list them all together."
                ))
            ],
            "current_node": "gather_marketing_brief"
        }

    return {
        **state,
        "brief_data": brief_data,  # for reference
        "product_name": brief_data["product_name"],
        "marketing_objectives": brief_data["objectives"],
        "marketing_budget": brief_data["budget"],
        "marketing_channel": brief_data["channel"],
        "marketing_duration": brief_data["duration"],
        "conversation_history": state["conversation_history"] + [
            AIMessage(content=(
                f"Great, we have all the details now:\n"
                f"• Product: {brief_data['product_name']}\n"
                f"• Objectives: {brief_data['objectives']}\n"
                f"• Budget: {brief_data['budget']}\n"
                f"• Channel: {brief_data['channel']}\n"
                f"• Duration: {brief_data['duration']}\n"
                "Let me pull up relevant product details..."
            ))
        ],
        "current_node": "get_product_table"
    }

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

        Marketing Objective: Conversion                                                   
        Product: {query}
        Buyer Categories: {buyer_categories}
        Product Categories: {product_categories}
        Total Results: {total_results}

        Detailed data:
        {table_data}

        Provide:
        1) A short reccomendation for the best Product Category & Buyer Category combination that is related to thier marketing objective

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