#!/usr/bin/env python3
"""
Fixed FastAPI Client with better error handling
"""

from fastapi import FastAPI, HTTPException, Query, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, AsyncGenerator
import uvicorn
import subprocess
import sys
import asyncio
import json
import time
import os
import signal

from core.config import config


# Pydantic Models
class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    execute: bool = Field(True, description="Execute the generated SQL")


class SQLRequest(BaseModel):
    sql: str = Field(..., description="SQL query to execute")


class TableRequest(BaseModel):
    table_name: str = Field(..., description="Table name")
    limit: Optional[int] = Field(5, ge=1, le=100)


# Simple MCP Client for testing
class SimpleMCPClient:
    def __init__(self):
        self.server_process = None
        self.is_running = False

    async def start_server(self):
        """Start MCP server in background"""
        try:
            print("🔧 Starting MCP server...")

            # Start the MCP server process
            self.server_process = subprocess.Popen(
                [sys.executable, "server.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Wait a bit for server to initialize
            await asyncio.sleep(3)

            # Check if process is still running
            if self.server_process.poll() is None:
                self.is_running = True
                print("✅ MCP server started successfully")
                return True
            else:
                # Read error output
                stderr_output = self.server_process.stderr.read()
                print(f"❌ MCP server failed to start: {stderr_output}")
                return False

        except Exception as e:
            print(f"❌ Error starting MCP server: {e}")
            return False

    async def stop_server(self):
        """Stop MCP server"""
        if self.server_process and self.is_running:
            print("🛑 Stopping MCP server...")
            try:
                self.server_process.terminate()
                await asyncio.sleep(2)

                if self.server_process.poll() is None:
                    self.server_process.kill()
                    await asyncio.sleep(1)

                self.is_running = False
                print("✅ MCP server stopped")
            except Exception as e:
                print(f"⚠ Error stopping MCP server: {e}")

    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Simulate MCP tool calls"""
        if not self.is_running:
            return {
                "success": False,
                "error": "MCP server is not running",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }

        # Simulate processing delay
        await asyncio.sleep(0.5)

        # Return simulated responses
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if tool_name == "convert_to_sql":
            query = kwargs.get("natural_language_query", "test query")
            return {
                "success": True,
                "query": query,
                "sql": f"SELECT id, name, email FROM users WHERE active = 1 LIMIT 10",
                "model": config.HF_MODEL,
                "timestamp": timestamp
            }

        elif tool_name == "execute_sql":
            return {
                "success": True,
                "sql": kwargs.get("sql_query", ""),
                "results": [
                    {"id": 1, "name": "Test User 1", "email": "test1@example.com", "active": True},
                    {"id": 2, "name": "Test User 2", "email": "test2@example.com", "active": True}
                ],
                "row_count": 2,
                "timestamp": timestamp
            }

        elif tool_name == "natural_language_query":
            return {
                "success": True,
                "natural_language_query": kwargs.get("query", ""),
                "generated_sql": "SELECT id, name, email FROM users WHERE active = 1 ORDER BY created_at DESC LIMIT 10",
                "results": [
                    {"id": i, "name": f"User {i}", "email": f"user{i}@example.com"}
                    for i in range(1, 6)
                ],
                "row_count": 5,
                "conversion_success": True,
                "execution_success": True,
                "model": config.HF_MODEL,
                "timestamp": timestamp
            }

        else:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "timestamp": timestamp
            }


# Global instances
mcp_client = SimpleMCPClient()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager
    """
    # Startup
    print("\n" + "=" * 60)
    print("🚀 STARTING NL2SQL AGENT API")
    print("=" * 60)
    print(f"📊 Database: {config.DB_NAME}")
    print(f"🧠 Model: {config.HF_MODEL}")
    print(f"🌐 Host: {config.API_HOST}")
    print(f"🚪 Port: {config.API_PORT}")
    print("=" * 60)

    # Start MCP server
    server_started = await mcp_client.start_server()
    if not server_started:
        print("⚠ MCP server failed to start, running in limited mode")

    print(f"\n✅ API Server starting on http://{config.API_HOST}:{config.API_PORT}")
    print("📚 API Documentation: http://localhost:8001/docs")
    print("🌐 WebSocket Test: http://localhost:8001/ws-test")
    print("=" * 60 + "\n")

    yield

    # Shutdown
    print("\n" + "=" * 60)
    print("🛑 SHUTTING DOWN NL2SQL AGENT API")
    print("=" * 60)
    await mcp_client.stop_server()
    print("✅ Shutdown complete")
    print("=" * 60)


# Create FastAPI app
app = FastAPI(
    title="NL2SQL Agent API",
    description="REST API for Natural Language to SQL Conversion",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "NL2SQL Agent API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "GET /": "This message",
            "GET /health": "Health check",
            "GET /docs": "API documentation",
            "GET /ws-test": "WebSocket test page",
            "POST /convert": "Convert NL to SQL",
            "POST /execute": "Execute SQL",
            "POST /query": "Convert and execute"
        },
        "config": {
            "database": config.DB_NAME,
            "model": config.HF_MODEL,
            "api_host": config.API_HOST,
            "api_port": config.API_PORT
        }
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "service": "nl2sql-api",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mcp_server": "running" if mcp_client.is_running else "stopped",
        "database": config.DB_NAME,
        "model": config.HF_MODEL
    }


@app.post("/convert")
async def convert(request: QueryRequest):
    """Convert natural language to SQL"""
    try:
        result = await mcp_client.call_tool(
            "convert_to_sql",
            natural_language_query=request.query
        )

        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get("error", "Conversion failed"))

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute")
async def execute(request: SQLRequest):
    """Execute SQL query"""
    try:
        result = await mcp_client.call_tool(
            "execute_sql",
            sql_query=request.sql
        )

        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get("error", "Execution failed"))

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def query(request: QueryRequest):
    """Convert and execute natural language query"""
    try:
        result = await mcp_client.call_tool(
            "natural_language_query",
            query=request.query
        )

        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get("error", "Query failed"))

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Simple WebSocket endpoint for testing
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Simple WebSocket endpoint"""
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            query_text = data.get("query", "")

            # Send immediate response
            await websocket.send_json({
                "type": "status",
                "message": f"Processing: {query_text[:50]}...",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })

            # Simulate processing
            await asyncio.sleep(1)

            await websocket.send_json({
                "type": "result",
                "sql": f"SELECT * FROM users WHERE query LIKE '%{query_text[:10]}%'",
                "results": [{"id": 1, "message": f"Result for '{query_text}'"}],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")


@app.get("/test")
async def test_endpoint():
    """Test endpoint for quick verification"""
    return {
        "status": "ok",
        "message": "API is working!",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoints": [
            "GET /test - This endpoint",
            "GET /health - Health check",
            "POST /convert - Convert NL to SQL",
            "POST /query - Full NL to SQL pipeline"
        ]
    }


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🎯 NL2SQL API CLIENT - READY TO START")
    print("=" * 60)

    # Verify configuration
    try:
        config.validate()
        print("✅ Configuration validated")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("💡 Check your .env file")
        sys.exit(1)

    # Start the server
    # uvicorn.run(
    #     app,
    #     host=config.API_HOST,
    #     port=config.API_PORT,
    #     reload=True,
    #     log_level="info"
    # )