import os
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain.output_parsers import StructuredOutputParser
from langchain_openai import AzureChatOpenAI

from schema import AudienceBuilderState, ProductIdentification, ProductSearchResults
from tools import SKULookupTool, ProductLookupTool, transform_to_product_table

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
                AIMessage(content=f"Got it! You're building audiences for {result.product_name}. Let's retrieve some product details for you.")
            ],
            "current_node": "get_product_table"
        }


def get_product_table(state: AudienceBuilderState) -> AudienceBuilderState:
    print("\n\nFormatting Search Results")
    
    # Get the product name from state
    product_name = state.get("product_name")
    
    try:
        # Get the product search results (either from state or by querying)
        product_search_results = state.get("product_search_results")
        if not product_search_results:
            product_lookup_tool = ProductLookupTool()
            product_search_results = product_lookup_tool.invoke(product_name)
            # Save the full results in state for potential future use
            state = {**state, "product_search_results": product_search_results}
        
        # Transform the search results into a table format
        product_table = transform_to_product_table(product_search_results)
        
        # Save the table format in state
        state = {**state, "product_table": product_table}
        
        # Create a prompt template that takes the structured data
        response_prompt = ChatPromptTemplate.from_template("""
        You are a data formatter that creates clean, readable summaries from product data.
                                                           
        YOU MUST BE CONCISE and to the point.

        Here are the search results for products:

        Query: {query}
        Buyer Categories: {buyer_categories}
        Product Categories: {product_categories}
        Total Results: {total_results}

        Here's the detailed data for each category combination:
        {table_data}

        Your job is to:
        1. First, provide a brief summary of the search results (what was found, categories, etc.)
        2. Then, mention that you're showing a detailed breakdown below.
        3. End with a note that this data will help them build audiences more effectively.

        DO NOT create or include a table in your response - a formatted table will be displayed separately.
        """)
        
        # Prepare detailed table data for the prompt
        table_details = []
        for row in product_table["rows"]:
            # Format the sample SKUs as a readable list
            sku_samples = ", ".join([f"{s['name']} (SKU: {s['sku']})" for s in row["skus"]])
            table_details.append(
                f"- {row['buyer_category']} > {row['product_category']}:\n" +
                f"  * Sample SKUs: {sku_samples}\n" +
                f"  * Total SKUs: {row['count']}"
            )
        
        # Create the chain
        response_chain = response_prompt | llm
        
        # Invoke the chain with the formatted product data
        response = response_chain.invoke({
            "query": product_name,
            "buyer_categories": ", ".join(product_search_results.unique_buyer_categories),
            "product_categories": ", ".join(product_search_results.unique_product_categories),
            "total_results": product_search_results.total_results,
            "table_data": "\n\n".join(table_details)
        })
        
        # Extract the content from the response
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response
        
        # Return updated state with the formatted response
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
    """Returns the initial state for the workflow."""
    return {
        "conversation_history": [],
        "product_name": None,
        "product_category": None,
        "buyer_category": None,
        "product_search_results": None,
        "product_table": None,
        "audience_selections": None,
        "current_node": "greet",
    }

def create_workflow():
    """Creates and returns the compiled workflow."""
    workflow = StateGraph(AudienceBuilderState)
    
    workflow.add_node("greet", greet)
    workflow.add_node("identify_product", identify_product)
    workflow.add_node("get_product_table", get_product_table)

    workflow.add_edge("greet", "identify_product")
    workflow.add_edge("identify_product", "get_product_table")

    workflow.add_conditional_edges(
        "identify_product",
        lambda state: state["current_node"],
        {
            "identify_product": "identify_product",
            "get_product_table": "get_product_table",
            END: END
        }
    )

    workflow.add_edge("get_product_table", END)

    workflow.set_entry_point("greet")
    
    return workflow.compile()






# def lookup_product_details(state: AudienceBuilderState) -> AudienceBuilderState:

#     print(f"\n\nLooking up product details for Product Name: {state.get('product_name')}")

#     product_name = state.get("product_name")
#     product_lookup_tool = ProductLookupTool()

#     try:
#         product_search_results = product_lookup_tool.invoke(product_name)

#         # Summarize the details to the user
#         response_prompt = ChatPromptTemplate.from_template(
#             """You are an audience building assistant for retail media.
            
#             You just received details for the Product Name {product_name}. 
#             You have also just run a search to return similar product variants, with results grouped by Buyer Category and Product Categories.
            
#             - Product Name: {product_name}
#             - Product Details: {product_search_results}

#             Respond warmly to the user confirming the Product Name.
#             Summarise the product variants that have been found, specifying the unique Buyer Categories and Product Categories.

#             Do not say 'Hi' or 'Hello' or anything like that. You have already spoken with the user.

#             YOU MUST RESPOND as the assistant.
#             """
#         )

#         response_chain = response_prompt | llm
#         response = response_chain.invoke({
#             "product_name": product_name,
#             "product_search_results": product_search_results
#         })

#         print(f"\n\nResponse: {response.content}")

#         return {
#             **state,
#             "product_name": product_name,
#             "product_search_results": product_search_results,
#             "current_node": END,
#             "conversation_history": state["conversation_history"] + [
#                 AIMessage(content=response.content)
#             ]
#         }
    
#     except Exception as e:
#         print("\nException in lookup_product_details:", repr(e))
#         # If the SKU cannot be found or something else goes wrong
#         not_found_prompt = ChatPromptTemplate.from_template(
#             """You are an audience building assistant for retail media.
            
#             The user asked about Product Name {product_name}, but it could not be found in our database.
            
#             Politely inform them that you couldn't find this Product and ask if they'd like to try a different product.

#             Respond as the assistant.
#             """
#         )

#         not_found_chain = not_found_prompt | llm
#         not_found_response = not_found_chain.invoke({"name": product_name})
        
#         return {
#             **state,
#             "conversation_history": state["conversation_history"] + [
#                 AIMessage(content=not_found_response.content)
#             ],
#             "current_node": END
#         }

# def get_product_table(state: AudienceBuilderState) -> AudienceBuilderState:
#     print("\n\nFormatting Search Results")
    
#     # Get the product search results from state


#     product_name = state.get("product_name")
#     product_lookup_tool = ProductLookupTool()

#     try:
#         product_search_results = product_lookup_tool.invoke(product_name)
    
#     except Exception as e:
#         print(e)
    
#     # Create a prompt template that takes the structured data
#     response_prompt = ChatPromptTemplate.from_template("""
#     You are a data formatter that creates clean, readable summaries from product data.
    
#     DO NOT USE Header, or Subheaders in your Markdown. Just bold for emphased titles.

#     Here are the search results for products:
    
#     Buyer Categories: {buyer_categories}
#     Product Categories: {product_categories}
#     Total Results: {total_results}
    
#     Sample products:
#     {sample_products}
    
#     1. First, provide a brief summary of the search results.
#     2. Then, create a well-formatted markdown table showing the most relevant products.
#     3. Include columns for: Buyer Category, Product Category, SKU Number, Product Name.
#     4. Limit to showing at most 10 products total.
#     """)
    
#     # Format the product data for the prompt
#     # Convert ProductDetails objects to strings for display in the prompt
#     sample_products = []
#     for p in product_search_results.all_products[:5]:  # Just show 5 examples
#         sample_products.append(
#             f"- {p.product_name} (SKU: {p.sku}, Buyer Category: {p.buyer_category}, Product Category: {p.product_category})"
#         )
    
#     # Create the chain
#     response_chain = response_prompt | llm
    
#     # Invoke the chain with the formatted product data
#     response = response_chain.invoke({
#         "buyer_categories": ", ".join(product_search_results.unique_buyer_categories),
#         "product_categories": ", ".join(product_search_results.unique_product_categories),
#         "total_results": product_search_results.total_results,
#         "sample_products": "\n".join(sample_products)
#     })
    
#     # Extract the content from the response
#     if hasattr(response, 'content'):
#         content = response.content
#     else:
#         content = response
    
#     # Return updated state with the formatted response
#     return {
#         **state,
#         "conversation_history": state["conversation_history"] + [
#             AIMessage(content=content)
#         ],
#         "current_node": END
#     }