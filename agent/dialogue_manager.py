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
    
    if state["conversation_history"]:
        # return state
        return {**state, "current_node": END}

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""You are an audience building assistant for Pollen.
        Greet the user warmly and ask which product and corresponding Product they'd like to build audiences for.
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
            "current_node": "lookup_product_details"  # 🚀 This ensures the workflow stops looping
        }

def lookup_product_details(state: AudienceBuilderState) -> AudienceBuilderState:

    print(f"\n\nLooking up product details for Product Name: {state.get('product_name')}")

    product_name = state.get("product_name")
    product_lookup_tool = ProductLookupTool()

    try:
        product_search_results = product_lookup_tool.invoke(product_name)

        # Summarize the details to the user
        response_prompt = ChatPromptTemplate.from_template(
            """You are an audience building assistant for retail media.
            
            You just received details for the Product Name {product_name}. 
            You have also just run a search to return similar product variants, with results grouped by Buyer Category and Product Categories.
            
            - Product Name: {product_name}
            - Product Details: {product_search_results}

            Respond warmly to the user confirming the Product Name.
            Summarise the product variants that have been found, specifying the unique Buyer Categories and Product Categories.

            Do not say 'Hi' or 'Hello' or anything like that. You have already spoken with the user.

            YOU MUST RESPOND as the assistant.
            """
        )

        response_chain = response_prompt | llm
        response = response_chain.invoke({
            "product_name": product_name,
            "product_search_results": product_search_results
        })

        print(f"\n\nResponse: {response.content}")

        return {
            **state,
            "product_name": product_name,
            "product_search_results": product_search_results,
            "current_node": END,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content=response.content)
            ]
        }
    
    except Exception as e:
        print("\nException in lookup_product_details:", repr(e))
        # If the SKU cannot be found or something else goes wrong
        not_found_prompt = ChatPromptTemplate.from_template(
            """You are an audience building assistant for retail media.
            
            The user asked about Product Name {product_name}, but it could not be found in our database.
            
            Politely inform them that you couldn't find this Product and ask if they'd like to try a different product.

            Respond as the assistant.
            """
        )

        not_found_chain = not_found_prompt | llm
        not_found_response = not_found_chain.invoke({"name": product_name})
        
        return {
            **state,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content=not_found_response.content)
            ],
            "current_node": END
        }

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
    
    workflow.add_node("greet", greet)
    workflow.add_node("identify_product", identify_product)
    workflow.add_node("lookup_product_details", lookup_product_details)

    workflow.add_edge("greet", "identify_product")
    workflow.add_edge("identify_product", "lookup_product_details")

    workflow.add_conditional_edges(
        "identify_product",
        lambda state: state["current_node"],
        {
            "identify_product": "identify_product",
            "lookup_product_details": "lookup_product_details",
            END: END
        }
    )

    workflow.add_edge("lookup_product_details", END)

    workflow.set_entry_point("greet")
    
    return workflow.compile()