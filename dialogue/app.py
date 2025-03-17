# app.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dialogue_manager import get_initial_state, create_workflow, State
from langchain_core.messages import HumanMessage, AIMessage
from template import html
from pydantic import BaseModel

app = FastAPI()

workflow = create_workflow(state=State)
counter = 0

@app.get("/")
async def get():
    return HTMLResponse(html)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    
    # Send thread_id to client (optional)
    await websocket.send_text(f"THREAD_ID:{thread_id}")

    # Initialize state
    state = get_initial_state()
    
    # Config with thread_id
    config = {"configurable": {"thread_id": thread_id}}
    
    # Initial workflow execution with thread_id
    async for step_result in workflow.astream(state, config=config):
        if step_result:
            # Extract the actual state
            node_name = next(iter(step_result))
            actual_state = step_result[node_name]
            
            # Check for AI messages to send
            msgs = actual_state["conversation_history"]
            if msgs and isinstance(msgs[-1], AIMessage):
                await websocket.send_text(msgs[-1].content)
    
    # Update state with the actual last state
    if step_result:
        node_name = next(iter(step_result))
        state = step_result[node_name]
    
    try:
        # Main interaction loop
        while True:
            user_input = await websocket.receive_text()
            
            # Update state with user input
            state["conversation_history"].append(HumanMessage(content=user_input))
            
            # Process through workflow again with the same thread_id in config
            async for step_result in workflow.astream(state, config=config):
                if step_result:
                    node_name = next(iter(step_result))
                    actual_state = step_result[node_name]
                    msgs = actual_state["conversation_history"]
                    
                    if msgs and isinstance(msgs[-1], AIMessage):
                        await websocket.send_text(msgs[-1].content)
            
            # Update state with the last result
            if step_result:
                node_name = next(iter(step_result))
                state = step_result[node_name]
                
    except WebSocketDisconnect:
        print(f"Client disconnected: {thread_id}")
        
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)