from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from graph import graph_builder
from pydantic import BaseModel
from template import html
from langgraph.checkpoint.memory import MemorySaver
import uvicorn

app = FastAPI()

graph = graph_builder.compile(checkpointer=MemorySaver())
counter = 0

class ChatInput(BaseModel):
    message: str

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global counter
    await websocket.accept()
    
    counter += 1
    thread_id = str(counter)
    
    await websocket.send_text(f"THREAD_ID:{thread_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            config = {"configurable": {"thread_id": thread_id}}
            async for event in graph.astream(
                {"messages": [data]}, 
                config=config,
                stream_mode="messages"
            ):
                await websocket.send_text(event[0].content)
    
    except WebSocketDisconnect as e:
        print(e)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)