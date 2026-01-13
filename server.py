from logger import setup_file_logging, get_logger
from typing import Dict, Any
from dotenv import load_dotenv
from mcp.server import FastMCP
from core.agent import nl2sql_agent
from core.config import config
from core.database import db_manager
from core.schema import schema_manager

load_dotenv()

setup_file_logging("server.log")

logger = get_logger(__name__)

# Initialize MCP
mcp = FastMCP("NL2SQL Agent")


# get database connection
async def get_db_connection():
    try:
        logger.info("Connected to database")
        return db_manager.connect()
    except Exception as e:
        logger.info(f"Error getting database connection: {e}")
        raise ConnectionError(f"❌ Database connection failed: {e}")


async def get_schema_context():
    try:
        logger.info("Schema context configured")
        return schema_manager.get_full_schema_context(config.DB_NAME)
    except Exception as e:
        logger.info(f"Error getting schema context: {e}")
        raise



@mcp.tool()
async def convert_to_sql(query: str) -> dict:
    try:
        schema_context = await get_schema_context()
        sql = nl2sql_agent.generate_sql(query, schema_context)
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


@mcp.tool()
def execute_sql(query: str) -> Dict[str, Any]:
    """Execute SQL query and return results"""
    try:
        cursor = db_manager.cursor()
        cursor.execute(query)

        if query.strip().upper().startswith('SELECT'):
            results = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return {
                "success": True,
                "columns": columns,
                "data": [dict(zip(columns, row)) for row in results]
            }
        else:
            cursor.commit()
            return {
                "success": True,
                "message": f"Query executed successfully. Rows affected: {cursor.rowcount}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    # Setting up database connection
    logger.info("Starting server")
    db_manager.connect()
    logger.info("Connected to database")
    # Run MCP server
    mcp.run()