from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import StateGraph, END
import uvicorn
from dialogue_manager import get_initial_state, create_workflow
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel
import asyncio

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
            if user_message.strip():
                state["conversation_history"].append(HumanMessage(content=user_message))

                async for step_result in workflow.astream(state, config=config):
                    if step_result:
                        node_name = next(iter(step_result))
                        state = step_result[node_name]  # ✅ Persist updated state
                        print(f"🚀 Transitioning to: {state['current_node']}")  # Debugging
                        msgs = state["conversation_history"]
                        if msgs and isinstance(msgs[-1], AIMessage):
                            await websocket.send_text(msgs[-1].content)

                # ✅ Close WebSocket when workflow ends
                if state["current_node"] == END:
                    print(f"✅ Ending conversation for thread {thread_id}")
                    await websocket.close()
                    return

    except WebSocketDisconnect:
        print(f"Client {thread_id} disconnected")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)