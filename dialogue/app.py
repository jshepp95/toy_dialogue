from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from next.dialogue_manager import get_initial_state, create_workflow
from langchain_core.messages import HumanMessage, AIMessage

app = FastAPI()

# Compile the workflow once
workflow = create_workflow()

# Allow from localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread_Id
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")

    # Send an immediate ping
    await websocket.send_json({"type": "ping", "content": "Connection test"})
    print("Sent test ping")

    # Create new state, run greeting
    state = get_initial_state()
    for step_result in workflow.stream(state):
        print(state)
        # If there's a new AIMessage, send it
        msgs = step_result["conversation_history"]
        if msgs and isinstance(msgs[-1], AIMessage):
            await websocket.send_json({"content": msgs[-1].content})
        state = step_result
    print("Greeting complete")

    # Receive user input repeatedly
    try:
        while True:
            text = await websocket.receive_text()
            print("Got user message:", text)

            state["conversation_history"].append(HumanMessage(content=text))

            # Run workflow steps
            for step_result in workflow.stream(state):
                old_len = len(state["conversation_history"])
                new_len = len(step_result["conversation_history"])
                if new_len > old_len:
                    last_msg = step_result["conversation_history"][-1]
                    if isinstance(last_msg, AIMessage):
                        await websocket.send_json({"content": last_msg.content})
                state = step_result

    except WebSocketDisconnect:
        print("Client disconnected")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)