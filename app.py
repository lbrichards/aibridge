from fastapi import FastAPI, WebSocket, Query
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

current_command = ""
connected_clients = []

HTML = """
<!DOCTYPE html>
<html>
    <head>
        <title>AI Bridge</title>
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
            #copyBtn:active { background: #3d8b40; }
            #status {
                margin-top: 10px;
                padding: 10px;
                display: none;
                border-radius: 4px;
            }
            .success { background: #dff0d8; color: #3c763d; }
            .error { background: #f2dede; color: #a94442; }
            .header { 
                background: #2c3e50; 
                color: white; 
                padding: 20px;
                margin-bottom: 20px;
            }
            .connection-status {
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
            }
            .connected { background: #dff0d8; color: #3c763d; }
            .disconnected { background: #f2dede; color: #a94442; }
        </style>
    </head>
    <body>
        <div id="connectionStatus" class="connection-status disconnected">Disconnected</div>
        <div class="header">
            <h1>AI Bridge</h1>
            <p>Commands from the AI assistant will appear here for you to copy and execute.</p>
        </div>
        <div id="command"></div>
        <button id="copyBtn" onclick="copyCommand()">Copy to Clipboard</button>
        <div id="status"></div>

        <script>
            const wsHost = window.location.hostname;
            const wsPort = window.location.port;
            let ws;
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 5;

            function showStatus(message, isError = false) {
                const status = document.getElementById("status");
                status.textContent = message;
                status.className = isError ? "error" : "success";
                status.style.display = "block";
                setTimeout(() => status.style.display = "none", 3000);
            }

            function updateConnectionStatus(connected) {
                const status = document.getElementById("connectionStatus");
                status.className = `connection-status ${connected ? 'connected' : 'disconnected'}`;
                status.textContent = connected ? 'Connected' : 'Disconnected';
            }

            function connectWebSocket() {
                ws = new WebSocket(`ws://${wsHost}:${wsPort}/ws`);
                
                ws.onopen = function() {
                    console.log('Connected to AI Bridge');
                    updateConnectionStatus(true);
                    reconnectAttempts = 0;
                };

                ws.onclose = function() {
                    console.log('Disconnected from AI Bridge');
                    updateConnectionStatus(false);
                    if (reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        setTimeout(connectWebSocket, 2000);
                    }
                };
                
                ws.onmessage = function(event) {
                    document.getElementById("command").textContent = event.data;
                    showStatus("New command received");
                };

                ws.onerror = function(error) {
                    console.error('WebSocket error:', error);
                    showStatus("Connection error", true);
                };
            }

            async function copyCommand() {
                const command = document.getElementById("command").textContent;
                if (!command) {
                    showStatus("No command to copy", true);
                    return;
                }

                try {
                    // Try the modern clipboard API first
                    await navigator.clipboard.writeText(command);
                    showStatus("Command copied to clipboard!");
                } catch (err1) {
                    try {
                        // Fallback to older execCommand method
                        const textArea = document.createElement("textarea");
                        textArea.value = command;
                        document.body.appendChild(textArea);
                        textArea.select();
                        const success = document.execCommand('copy');
                        textArea.remove();
                        
                        if (success) {
                            showStatus("Command copied to clipboard!");
                        } else {
                            throw new Error("execCommand failed");
                        }
                    } catch (err2) {
                        console.error('Clipboard error:', err2);
                        showStatus("Failed to copy command. Please copy manually.", true);
                    }
                }
            }

            // Initial connection
            connectWebSocket();
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
async def set_command(command: str = Query(...)):
    global current_command
    current_command = command
    # Broadcast to all connected clients
    disconnected_clients = []
    for client in connected_clients:
        try:
            await client.send_text(command)
        except:
            disconnected_clients.append(client)
    
    # Clean up disconnected clients
    for client in disconnected_clients:
        if client in connected_clients:
            connected_clients.remove(client)
    
    return {"status": "success"}

@app.get("/status")
async def get_status():
    return {
        "active_connections": len(connected_clients),
        "current_command": current_command,
        "uptime": "implement_me",
        "version": "0.1.0"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=51753)
