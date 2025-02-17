from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

current_command = ""
connected_clients = []

HTML = """
<!DOCTYPE html>
<html>
    <head>
        <title>OpenHands Command Share</title>
        <style>
            body { margin: 20px; font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; }
            #command { 
                width: 100%; 
                padding: 10px; 
                margin: 10px 0; 
                font-family: monospace; 
                background: #f0f0f0; 
                border: 1px solid #ccc;
                white-space: pre-wrap;
                min-height: 50px;
            }
            #copyBtn {
                padding: 10px 20px;
                background: #4CAF50;
                color: white;
                border: none;
                cursor: pointer;
                font-size: 16px;
            }
            #copyBtn:hover { background: #45a049; }
            #status {
                margin-top: 10px;
                padding: 10px;
                display: none;
            }
            .success { background: #dff0d8; color: #3c763d; }
            .header { 
                background: #2c3e50; 
                color: white; 
                padding: 20px;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>OpenHands Command Share</h1>
            <p>Commands from the AI assistant will appear here for you to copy and execute.</p>
        </div>
        <div id="command"></div>
        <button id="copyBtn" onclick="copyCommand()">Copy to Clipboard</button>
        <div id="status"></div>

        <script>
            const wsHost = window.location.hostname;
            const wsPort = window.location.port;
            let ws = new WebSocket(`ws://${wsHost}:${wsPort}/ws`);
            
            ws.onmessage = function(event) {
                document.getElementById("command").textContent = event.data;
            };

            function copyCommand() {
                const command = document.getElementById("command").textContent;
                navigator.clipboard.writeText(command).then(function() {
                    const status = document.getElementById("status");
                    status.textContent = "Command copied to clipboard!";
                    status.className = "success";
                    status.style.display = "block";
                    setTimeout(() => status.style.display = "none", 2000);
                });
            }
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(HTML)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        connected_clients.remove(websocket)

@app.post("/command")
async def set_command(command: str):
    global current_command
    current_command = command
    # Broadcast to all connected clients
    for client in connected_clients:
        try:
            await client.send_text(command)
        except:
            connected_clients.remove(client)
    return {"status": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=51753)
