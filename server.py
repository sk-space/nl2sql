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
        return schema_manager.get_schema_string(config.DB_NAME)
    except Exception as e:
        logger.info(f"Error getting schema context: {e}")
        raise


@mcp.tool()
async def get_schema():
    """
        Retrieves the current database schema as a formatted string.

        This tool connects to the active database and extracts the schema
        information, including tables, columns, and relationships. The schema
        is returned in a human-readable format suitable for use by agents
        performing natural language to SQL translation.

        Returns:
            str: A formatted string representation of the database schema.
    """
    try:
        schema_context = await schema_manager.get_schema_info(config.DB_NAME)
        return schema_context
    except Exception as e:
        return f"❌ Error retrieving schema: {e}"



@mcp.tool()
async def convert_to_sql(query: str) -> dict:
    """
        Converts a natural language query into a valid SQL statement.

        This tool accepts a user-provided natural language question describing
        a data retrieval requirement and generates a syntactically correct,
        schema-aware SQL query based on the current database structure.

        The function:
        - Loads the active database schema context
        - Uses an NL-to-SQL agent to translate the natural language query
        - Returns the generated SQL without executing it

        Parameters:
            query (str): A natural language query describing the desired data,
                         such as "List all active projects in the HR department".

        Returns:
            dict: A structured response containing:
                - success (bool): Indicates whether SQL generation was successful
                - query (str): The original natural language query
                - sql (str): The generated SQL query (if successful)
                - error (str): Error message (if failed)
    """
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
    """
        Executes a SQL query against the connected database and returns structured results.

        This tool is responsible for executing a validated SQL statement generated
        by an upstream agent (e.g., NL-to-SQL converter). It supports both read and
        write operations and returns results in a structured JSON-compatible format.

        Behavior:
        - Executes the provided SQL query using the active database connection
        - Automatically detects the query type (SELECT / WITH vs DML)
        - Fetches and returns result rows for SELECT queries
        - Commits transactions for INSERT, UPDATE, and DELETE queries
        - Returns affected row count for write operations

        Parameters:
            query (str): A valid SQL query to be executed. The query is assumed
                         to be syntactically correct and safe to run.

        Returns:
            Dict[str, Any]: A structured response containing:
                - success (bool): Indicates whether execution succeeded
                - columns (list[str]): Column names (for SELECT queries)
                - data (list[dict]): Query result rows as dictionaries
                - rows_affected (int): Number of rows modified (for DML queries)
                - error (str): Error message if execution fails

        Notes:
            - SELECT and WITH queries return result sets
            - INSERT / UPDATE / DELETE queries return rows_affected
            - This function does not perform SQL validation or sanitization
              and should only be called with trusted or pre-validated SQL
    """
    try:
        with db_manager.get_cursor() as cursor:
            cursor.execute(query)

            query_type = query.strip().split()[0].upper()

            if query_type in ("SELECT", "WITH"):
                # Fetch actual rows
                rows = cursor.fetchall()

                if not rows:
                    return {"success": True, "columns": [], "data": []}

                # Get column names
                columns = [desc[0] for desc in cursor.description]

                # Map actual row values into dict
                data = [dict(row) for row in rows]

                return {"success": True, "columns": columns, "data": data}

            else:
                # For INSERT, UPDATE, DELETE
                db_manager.commit()
                rowcount = cursor.rowcount

                # Handle RETURNING rows if supported
                data = []
                if cursor.description:
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    data = [dict(zip(columns, row)) for row in rows]

                return {"success": True, "rows_affected": rowcount, "data": data}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Setting up database connection
    logger.info("Starting server")
    db_manager.connect()
    logger.info("Connected to database")
    # Run MCP server
    mcp.run()