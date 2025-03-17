html = """<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <div id="thread-info"></div>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <p id='messages'></p>
        <script>
            var threadId = null;
            var ws = new WebSocket("ws://localhost:8000/ws");
            
            ws.onmessage = function(event) {
                var data = event.data;
                var messages = document.getElementById('messages');
                
                // Check if this is a thread ID message
                if (data.startsWith("THREAD_ID:")) {
                    threadId = data.substring(10);
                    document.getElementById('thread-info').innerText = "Connected with thread ID: " + threadId;
                } else {
                    // Regular message
                    messages.innerHTML += "<div>" + data + "</div>";
                }
            };
            
            function sendMessage(event) {
                var input = document.getElementById("messageText");
                ws.send(input.value);
                input.value = '';
                event.preventDefault();
            }
        </script>
    </body>
</html>
"""


# html = """
# <!DOCTYPE html>
# <html>
#     <head>
#         <title>Chat</title>
#     </head>
#     <body>
#         <h1>WebSocket Chat</h1>
#         <form action="" onsubmit="sendMessage(event)">
#             <input type="text" id="messageText" autocomplete="off"/>
#             <button>Send</button>
#         </form>
#         <p id='messages'></p>
#         <script>
#             var ws = new WebSocket("ws://localhost:8000/ws/123");
#             ws.onmessage = function(event) {
#                 var messages = document.getElementById('messages')
#                 messages.innerText+=event.data
#             };
#             function sendMessage(event) {
#                 var input = document.getElementById("messageText")
#                 ws.send(input.value)
#                 input.value = ''
#                 event.preventDefault()
#             }
#         </script>
#     </body>
# </html>
# """