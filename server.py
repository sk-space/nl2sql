from typing import Dict, Any
from dotenv import load_dotenv
from mcp.server import FastMCP

from core.agent import nl2sql_agent
from core.config import config
from core.database import db_manager
from core.llm import hf_interface
from core.schema import schema_manager

load_dotenv()

# Initialize MCP
mcp = FastMCP("NL2SQL Agent")

# Tools
@mcp.tool()
def convert_to_sql(query: str) -> Dict[str, Any]:
    try:
        details = schema_manager.get_full_schema_context(config.DB_NAME)
        sql = nl2sql_agent.generate_sql(query, details)
        return {
            "success": True,
            "query": query,
            "sql": sql
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": query
        }


if __name__ == "__main__":
    print("=" * 60)
    print("NL2SQL MCP Server")
    print("=" * 60)

    # Initialize components
    db_manager.connect()

    # Load model in background
    import threading


    def load_model_async():
        try:
            hf_interface.load_model()
            print("✅ Model loaded successfully")
        except Exception as e:
            print(f"⚠ Model loading failed: {e}")


    model_thread = threading.Thread(target=load_model_async)
    model_thread.daemon = True
    model_thread.start()

    print("🚀 Server ready. Starting MCP protocol...")
    print("=" * 60)

    # Run MCP server
    mcp.run()