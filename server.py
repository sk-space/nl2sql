import logging
from typing import Dict, Any
from dotenv import load_dotenv
from mcp.server import FastMCP
from core.agent import nl2sql_agent
from core.config import config
from core.database import db_manager
from core.schema import schema_manager

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize MCP
mcp = FastMCP("NL2SQL Agent")

class MCPServer:
    def __init__(self):
        self._db_name = config.DB_NAME
        self._connection = None
        self._cursor = None
        self._schema_context = None


    # get database connection
    async def get_db_connection(self):
        try:
            self._connection = db_manager.connect()
            logger.info("Connected to database")
        except Exception as e:
            logger.info(f"Error getting database connection: {e}")
            raise ConnectionError(f"❌ Database connection failed: {e}")
            raise


    # get database connection
    async def get_db_cursor(self):
        try:
            self._cursor = db_manager.cursor()
            logger.info("Database cursor configured")
        except Exception as e:
            logger.info(f"Error fetching database cursor: {e}")
            raise ConnectionError(f"❌ Database connection failed: {e}")


    async def get_schema_context(self):
        try:
            self._schema_context = schema_manager.get_full_schema_context(self._db_name)
            logger.info("Schema context configured")
        except Exception as e:
            logger.info(f"Error getting schema context: {e}")
            raise



    @mcp.tool()
    def convert_to_sql(self, query: str) -> dict:
        self.get_schema_context()
        try:
            sql = nl2sql_agent.generate_sql(query, self._schema_context)
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
    def execute_sql(self, query: str) -> Dict[str, Any]:
        """Execute SQL query and return results"""
        try:
            self.get_db_cursor()
            cursor = self._cursor
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
                self._cursor.commit()
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
    MCPServer().get_db_connection()
    logger.info("Connected to database")
    # Run MCP server
    mcp.run()