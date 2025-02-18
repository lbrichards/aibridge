from fastapi import FastAPI, WebSocket, Query
from fastapi.responses import HTMLResponse
import uvicorn
import redis
import logging
import os
import json
from ast import literal_eval
from typing import Optional, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize Redis client
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', '6379'))
redis_db = int(os.getenv('REDIS_DB', '0'))

try:
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        decode_responses=True  # Auto-decode Redis responses to strings
    )
    redis_client.ping()
    logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
except redis.ConnectionError:
    logger.warning("Could not connect to Redis - messages will only appear in web interface")
    redis_client = None

def get_tmate_urls() -> Optional[Dict[str, str]]:
    """Get the current tmate session URLs from Redis."""
    if not redis_client:
        return None
    
    try:
        urls_str = redis_client.get('tmate_urls')
        if not urls_str:
            return None
        
        # Convert string representation of dict to actual dict
        urls = literal_eval(urls_str)
        logger.info(f"Found tmate URLs: web={urls.get('web')}, ssh={urls.get('ssh')}")
        return urls
    except Exception as e:
        logger.error(f"Error getting tmate URLs: {str(e)}")
        return None

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
                cursor: text;
                user-select: all;  /* Makes the text pre-selected */
            }
            .command-container {
                position: relative;
                margin: 20px 0;
            }
            .copy-hint {
                position: absolute;
                top: -20px;
                left: 0;
                color: #666;
                font-size: 12px;
                display: none;
            }
            #command:hover + .copy-hint {
                display: block;
            }
            .buttons {
                display: flex;
                gap: 10px;
                margin: 10px 0;
            }
            button {
                padding: 10px 20px;
                background: #4CAF50;
                color: white;
                border: none;
                cursor: pointer;
                font-size: 16px;
                border-radius: 4px;
            }
            button:hover { background: #45a049; }
            button.secondary {
                background: #2196F3;
            }
            button.secondary:hover {
                background: #1976D2;
            }
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
                border-radius: 4px;
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
            kbd {
                background-color: #f7f7f7;
                border: 1px solid #ccc;
                border-radius: 3px;
                box-shadow: 0 1px 0 rgba(0,0,0,0.2);
                color: #333;
                display: inline-block;
                font-size: .85em;
                font-family: Monaco, monospace;
                line-height: 1;
                padding: 2px 4px;
                white-space: nowrap;
            }
            .tmate-urls {
                margin-top: 20px;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 4px;
                border-left: 4px solid #2196F3;
            }
            .tmate-urls h3 {
                margin-top: 0;
                color: #2c3e50;
            }
            .tmate-urls code {
                display: block;
                margin: 5px 0;
                padding: 5px;
                background: #fff;
                border: 1px solid #ddd;
                border-radius: 3px;
                font-family: Monaco, monospace;
            }
        </style>
    </head>
    <body>
        <div id="connectionStatus" class="connection-status disconnected">Disconnected</div>
        <div class="header">
            <h1>AI Bridge</h1>
            <p>Commands from the AI assistant will appear below. Click the command to select it, then press <kbd>⌘C</kbd> or <kbd>Ctrl+C</kbd> to copy.</p>
        </div>
        <div class="command-container">
            <div id="command" onclick="this.focus()"></div>
            <div class="copy-hint">Click to select, then press ⌘C or Ctrl+C to copy</div>
        </div>
        <div class="buttons">
            <button onclick="selectCommand()">Select All</button>
            <button class="secondary" onclick="clearCommand()">Clear</button>
        </div>
        <div id="status"></div>
        <div id="tmateUrls" class="tmate-urls" style="display: none;">
            <h3>Terminal Session URLs</h3>
            <div id="tmateUrlsContent"></div>
        </div>

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

            function selectCommand() {
                const commandDiv = document.getElementById("command");
                if (commandDiv.textContent) {
                    const range = document.createRange();
                    range.selectNodeContents(commandDiv);
                    const selection = window.getSelection();
                    selection.removeAllRanges();
                    selection.addRange(range);
                    showStatus("Command selected - press ⌘C or Ctrl+C to copy");
                }
            }

            function clearCommand() {
                document.getElementById("command").textContent = "";
                showStatus("Command cleared");
            }

            function updateTmateUrls() {
                fetch('/tmate-urls')
                    .then(response => response.json())
                    .then(data => {
                        if (data && (data.web || data.ssh)) {
                            const content = document.getElementById('tmateUrlsContent');
                            content.innerHTML = `
                                <p><strong>Web URL (preferred):</strong><br>
                                <code>${data.web || 'Not available'}</code></p>
                                <p><strong>SSH URL (alternate):</strong><br>
                                <code>${data.ssh || 'Not available'}</code></p>
                                <p><em>Last updated: ${new Date(data.timestamp).toLocaleString()}</em></p>
                            `;
                            document.getElementById('tmateUrls').style.display = 'block';
                        }
                    })
                    .catch(error => console.error('Error fetching tmate URLs:', error));
            }

            function connectWebSocket() {
                ws = new WebSocket(`ws://${wsHost}:${wsPort}/ws`);
                
                ws.onopen = function() {
                    console.log('Connected to AI Bridge');
                    updateConnectionStatus(true);
                    reconnectAttempts = 0;
                    updateTmateUrls();  // Get initial URLs
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
                    selectCommand();  // Automatically select new commands
                };

                ws.onerror = function(error) {
                    console.error('WebSocket error:', error);
                    showStatus("Connection error", true);
                };
            }

            // Initial connection
            connectWebSocket();

            // Periodically update tmate URLs
            setInterval(updateTmateUrls, 10000);
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(HTML)

@app.get("/tmate-urls")
async def get_tmate_urls_endpoint():
    """Return the current tmate session URLs."""
    urls = get_tmate_urls()
    if urls:
        return urls
    return {"error": "No active tmate session found"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        connected_clients.remove(websocket)

@app.get("/command")
async def get_command():
    # Return HTML with the current command in <div id="command">
    html_content = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>Current Command</title>
            <style>
                #command {{ 
                    width: 100%; 
                    padding: 10px; 
                    margin: 10px 0; 
                    font-family: monospace; 
                    background: #f0f0f0; 
                    border: 1px solid #ccc;
                    white-space: pre-wrap;
                    min-height: 50px;
                }}
            </style>
        </head>
        <body>
            <div id="command">{current_command}</div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/command")
async def set_command(command: str = Query(...)):
    global current_command
    current_command = command
    
    # Publish to Redis if available
    if redis_client:
        try:
            redis_client.publish('llm_suggestions', command)
            logger.info(f"Published to Redis: {command[:50]}...")
        except Exception as e:
            logger.error(f"Redis publish failed: {str(e)}")
    else:
        logger.error("Redis client not initialized - check Redis connection")
    
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=51753)
