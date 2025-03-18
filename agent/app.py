from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import StateGraph, END
import uvicorn
from dialogue_manager import get_initial_state, create_workflow
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel
import asyncio
import json

app = FastAPI()

workflow = create_workflow()
counter = 0

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Fix to allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatInput(BaseModel):
    message: str

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global counter
    await websocket.accept()

    counter += 1
    thread_id = str(counter)

    await websocket.send_text(f"THREAD_ID:{thread_id}")

    state = get_initial_state()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        if not state["conversation_history"]:
            async for step_result in workflow.astream(state, config=config):
                if step_result:
                    node_name = next(iter(step_result))
                    state = step_result[node_name]  # ✅ Persist state properly
                    msgs = state["conversation_history"]
                    if msgs and isinstance(msgs[-1], AIMessage):
                        await websocket.send_text(msgs[-1].content)
                    break  # ✅ Stops greet from looping

        while True:
            user_message = await websocket.receive_text()
            
            # Try to parse as JSON to check if it's a category selection
            try:
                json_data = json.loads(user_message)
                if json_data.get("type") == "audience_selection":
                    categories = json_data.get("categories", [])
                    print(f"Received selection of {len(categories)} categories")
                    
                    # Format the categories for display
                    category_details = []
                    for cat in categories:
                        buyer = cat.get("buyer_category", "Unknown")
                        product = cat.get("product_category", "Unknown")
                        category_details.append(f"{buyer} > {product}")
                    
                    # Format the category details as a readable list
                    categories_text = ", ".join(category_details)

                    state["audience_selections"] = categories
        
                    print(f"Updated state with audience selections: {state['audience_selections']}")
                    
                    # Send a more detailed acknowledgment back to client
                    await websocket.send_json({
                        "type": "selection_received",
                        "message": f"Selected categories: {categories_text}",
                        "categories": categories
                    })
                    continue
            
            except json.JSONDecodeError:
                # Not JSON, handle as normal message
                pass
            
            # Normal text message handling
            if user_message.strip():
                state["conversation_history"].append(HumanMessage(content=user_message))

                async for step_result in workflow.astream(state, config=config):
                    if step_result:
                        node_name = next(iter(step_result))
                        state = step_result[node_name]  # ✅ Persist updated state
                        print(f"🚀 Transitioning to: {state['current_node']}")  # Debugging
                        msgs = state["conversation_history"]
                        
                        if msgs and isinstance(msgs[-1], AIMessage):
                            # Check if we have a product_table in state
                            if "product_table" in state:
                                # Create a structured message with both text and table
                                message_data = {
                                    "type": "complex",
                                    "text": msgs[-1].content,
                                    "table": state["product_table"]
                                }
                                print("Sending complex message with table")
                                # Send as JSON
                                await websocket.send_json(message_data)
                                
                                # Remove product_table from state after sending
                                state = {**state}
                                del state["product_table"]
                            else:
                                # Just send the text as before
                                await websocket.send_text(msgs[-1].content)

                # ✅ Close WebSocket when workflow ends
                if state["current_node"] == END:
                    print(f"✅ Ending conversation for thread {thread_id}")
                    # await websocket.close()
                    # return
                    pass

    except WebSocketDisconnect:
        print(f"Client {thread_id} disconnected")
    except Exception as e:
        print(f"Error in WebSocket handling: {e}")
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)