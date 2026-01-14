import json
from contextlib import asynccontextmanager
from typing import Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from client import MCPClient
from logger import get_logger, setup_file_logging
from core.config import config

load_dotenv()
setup_file_logging("server.log")
logger = get_logger(__name__)

class Settings(BaseSettings):
    server_script_path: str = "C:/Users/hpgsumank/Documents/nl2sql/server.py"


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = MCPClient()
    try:
        connected = await client.connect_to_server(settings.server_script_path)
        if not connected:
            raise HTTPException(
                status_code=500, detail="Failed to connect to MCP server"
            )
        app.state.client = client
        yield
    except Exception as e:
        print(f"Error during lifespan: {e}")
        raise HTTPException(status_code=500, detail="Error during lifespan") from e
    finally:
        # shutdown
        await client.cleanup()


app = FastAPI(title="MCP Client API", lifespan=lifespan)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


class QueryRequest(BaseModel):
    query: str


class Message(BaseModel):
    role: str
    content: Any


class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any]


@app.get("/tools")
async def get_tools():
    """Get the list of available tools"""
    try:
        tools = await app.state.client.get_mcp_tools()
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in tools
            ]
        }
    except Exception as e:
        logger.info(f"Failed to get available tools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def process_query(request: QueryRequest):
    """Process a query and return the response"""
    try:
        logger.info(f"Received query: {request.query}")
        response = await app.state.client.process_query(request.query)
        return json.loads(response)
    except Exception as e:
        logger.info(f"Failed to generate sql: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post('/execute-sql')
async def execute_sql(request: QueryRequest):
    """Execute custom SQL query"""
    try:
        logger.info(f"Received sql: {request.query}")
        response = await app.state.client.execute_query(request.query)
        return json.loads(response)

    except Exception as e:
        logger.info(f"Failed to execute query: {str(e)}")
        return HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=f"{config.API_HOST}", port=config.API_PORT)