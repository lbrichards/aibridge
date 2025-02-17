# Command Share Tool for OpenHands

A simple web-based command sharing tool that allows an AI assistant to send commands to a user's clipboard.

## Quick Start

1. Start the service:
   ```bash
   docker compose up -d
   ```

2. Access the web interface:
   - Open http://localhost:51753 in your browser

3. Send commands (for AI):
   ```bash
   curl -X POST http://localhost:51753/command -H 'Content-Type: application/json' -d '"ls -la"'
   ```

## Features
- Real-time command updates via WebSocket
- Copy to clipboard functionality
- Clean, simple interface
- Docker-based deployment

