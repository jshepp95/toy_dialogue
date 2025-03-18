
def briefer(state: AudienceBuilderState) -> AudienceBuilderState:
    """Elicit media brief information from the user."""
    print(f"\n\nCollecting brief information. Current state: {state}")
    
    # Check which fields we've already collected
    brief_info = state.get("brief_info", {})
    
    # Check if we're waiting for user input
    waiting_for_input = state.get("waiting_for_brief_input", False)
    
    # Determine what information is still missing
    missing_fields = []
    if "objectives" not in brief_info:
        missing_fields.append("objectives")
    if "budget" not in brief_info:
        missing_fields.append("budget")
    if "channel" not in brief_info:
        missing_fields.append("channel")
    if "timelines" not in brief_info:
        missing_fields.append("timelines")
    
    # If we have everything, summarize and exit
    if not missing_fields:
        # Create a summary of the complete brief
        summary_prompt = ChatPromptTemplate.from_template("""
        You are helping to summarize a media brief. Here are the details collected:
        
        Product: {product_name}
        Selected Categories: {categories}
        Campaign Objectives: {objectives}
        Budget: {budget}
        Channel: {channel}
        Timelines: {timelines}
        
        Provide a concise summary of this brief, highlighting the key information.
        """)
        
        # Format the categories for the prompt
        categories_text = "None"
        if state.get("audience_selections"):
            categories_text = ", ".join([f"{cat['buyer_category']} > {cat['product_category']}" 
                                        for cat in state["audience_selections"]])
        
        response = summary_prompt | llm
        summary = response.invoke({
            "product_name": state.get("product_name", "Not specified"),
            "categories": categories_text,
            "objectives": brief_info.get("objectives", "Not specified"),
            "budget": brief_info.get("budget", "Not specified"),
            "channel": brief_info.get("channel", "Not specified"),
            "timelines": brief_info.get("timelines", "Not specified")
        })
        
        # Return the final state with the summary
        return {
            **state,
            "brief_summary": summary.content if hasattr(summary, 'content') else summary,
            "conversation_history": state["conversation_history"] + [
                AIMessage(content=f"Thank you! I've collected all the necessary information for your media brief. Here's a summary:\n\n{summary.content if hasattr(summary, 'content') else summary}")
            ],
            "current_node": END
        }
    
    # If we're waiting for input and there's a new user message, process it
    last_user_message = None
    if waiting_for_input:
        for message in reversed(state["conversation_history"]):
            if isinstance(message, HumanMessage):
                last_user_message = message.content
                break
        
        if last_user_message:
            # Try to extract information from the last user message
            extraction_prompt = ChatPromptTemplate.from_template("""
            Extract the following information from the user's message if present:
            
            User message: {message}
            
            Extract as JSON:
            {{
                "objectives": "The campaign objectives mentioned, or null if not provided",
                "budget": "The budget mentioned, or null if not provided",
                "channel": "The channel mentioned, or null if not provided",
                "timelines": "The timelines mentioned, or null if not provided"
            }}
            
            Only include fields that are explicitly mentioned in the message.
            """)
            
            extraction_chain = extraction_prompt | llm
            extracted_info = extraction_chain.invoke({"message": last_user_message})
            
            # Parse the extracted JSON (handle potential formatting issues)
            try:
                import json
                import re
                
                # Find JSON content between the first { and the last }
                json_match = re.search(r"\{.*\}", extracted_info.content, re.DOTALL)
                if json_match:
                    extracted_json = json.loads(json_match.group(0))
                    
                    # Update brief_info with any extracted information
                    for field in ["objectives", "budget", "channel", "timelines"]:
                        if field in extracted_json and extracted_json[field] and extracted_json[field] != "null":
                            brief_info[field] = extracted_json[field]
                            if field in missing_fields:
                                missing_fields.remove(field)
            except Exception as e:
                print(f"Error parsing extracted info: {e}")
            
            # Reset waiting flag to generate a new prompt
            waiting_for_input = False
    
    # If we aren't waiting for input or we just processed input, generate a new question
    if not waiting_for_input:
        # Formulate a response asking for missing information
        response_prompt = ChatPromptTemplate.from_template("""
        You are a helpful assistant collecting media brief information. The user is building an audience for {product_name}.
        
        Information already collected:
        {collected_info}
        
        Information still needed:
        {missing_info}
        
        Product information:
        {product_details}
        
        Audience categories selected:
        {audience_details}
        
        Based on this, craft a friendly response that:
        1. Acknowledges any information the user has just provided
        2. Asks for the specific missing information
        3. If this is the first time asking, explain briefly why each piece of information is important
        
        Keep your response conversational and helpful.
        """)
        
        # Format the collected and missing information for the prompt
        collected_info = []
        for field in ["objectives", "budget", "channel", "timelines"]:
            if field in brief_info:
                collected_info.append(f"- {field.capitalize()}: {brief_info[field]}")
        
        missing_info = []
        for field in missing_fields:
            missing_info.append(f"- {field.capitalize()}")
        
        # Get product details and audience selections for context
        product_details = f"Product: {state.get('product_name', 'Not specified')}"
        
        audience_details = "None selected"
        if state.get("audience_selections"):
            audience_details = ", ".join([f"{cat['buyer_category']} > {cat['product_category']}" 
                                        for cat in state["audience_selections"]])
        
        # Generate the response
        response = response_prompt | llm
        response_text = response.invoke({
            "product_name": state.get("product_name", "your product"),
            "collected_info": "\n".join(collected_info) if collected_info else "No information collected yet",
            "missing_info": "\n".join(missing_info),
            "product_details": product_details,
            "audience_details": audience_details
        })
        
        # Update the state with the information we've collected so far
        return {
            **state,
            "brief_info": brief_info,
            "waiting_for_brief_input": True,  # Set waiting flag to true
            "conversation_history": state["conversation_history"] + [
                AIMessage(content=response_text.content if hasattr(response_text, 'content') else response_text)
            ],
            "current_node": "briefer"  # Stay in the briefer node until we have all the information
        }
    
    # If we're still waiting for input, just return the current state without adding a new message
    return {**state, "current_node": "briefer"}

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
        "brief_info": {},
        "waiting_for_brief_input": False,
        "table_sent": False,  # Add this to track if the table has been sent
        "current_node": "greet",
    }

def create_workflow():
    """Creates and returns the compiled workflow."""
    workflow = StateGraph(AudienceBuilderState)
    
    workflow.add_node("greet", greet)
    workflow.add_node("identify_product", identify_product)
    workflow.add_node("get_product_table", get_product_table)
    workflow.add_node("briefer", briefer)

    workflow.add_edge("greet", "identify_product")
    workflow.add_edge("identify_product", "get_product_table")

    workflow.add_conditional_edges(
        "identify_product",
        lambda state: state["current_node"],
        {
            "identify_product": "identify_product",
            "get_product_table": "get_product_table",
            # "briefer": "briefer",
            END: END
        }
    )

    workflow.add_edge("get_product_table", END)

    # workflow.add_edge("get_product_table", "briefer")

    # workflow.add_conditional_edges(
    #     "briefer",
    #     lambda state: "briefer" if len(state.get("brief_info", {})) < 4 else END,
    #     {
    #         "briefer": "briefer",
    #         END: END
    #     }
    # )

    workflow.set_entry_point("greet")
    
    return workflow.compile()