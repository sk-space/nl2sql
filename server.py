#!/usr/bin/env python3
"""
MCP Server for NL2SQL Agent
Provides tools, resources, and prompts for natural language to SQL conversion
"""

from fastmcp import FastMCP
from typing import Dict, Any, List
import json
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from core.schema import schema_manager
from core.llm import llm_service
from core.database import db_manager
from core.config import config

# Initialize MCP
mcp = FastMCP("NL2SQL Agent")


@asynccontextmanager
async def mcp_lifespan():
    """Lifespan context manager for MCP server"""
    print("🚀 Starting MCP Server...")
    print(f"📊 Database: {config.DB_NAME}")
    print(f"🧠 Model: {config.HF_MODEL}")

    # Initialize database connection
    try:
        db_manager.connect()
        print("✅ Database connected")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise

    # Load LLM model (lazy loading is handled by llm_service)
    print("⏳ Loading LLM model...")
    try:
        llm_service.is_available()
        print("✅ Model loaded")
    except Exception as e:
        print(f"⚠ Model loading warning: {e}")
        print("⚠ SQL generation will fail without model")

    try:
        yield
    finally:
        # Cleanup
        print("🛑 Shutting down MCP Server...")
        db_manager.close()
        print("✅ MCP Server shutdown complete")


# Apply lifespan to MCP
mcp = FastMCP("NL2SQL Agent")


# Resources
@mcp.resource(uri="schema://database")
def get_database_schema() -> str:
    """
    Get the complete database schema as JSON
    """
    schema = schema_manager.get_full_schema()
    return json.dumps(schema, indent=2, default=str)


@mcp.resource(uri="tables://list")
def list_all_tables() -> str:
    """
    List all tables in the database
    """
    schema = schema_manager.get_full_schema()
    tables = [table["name"] for table in schema["tables"]]
    return json.dumps({"tables": tables, "count": len(tables)}, indent=2)


@mcp.resource(uri="table://{table_name}/info")
def get_table_details(table_name: str) -> str:
    """
    Get detailed information about a specific table
    """
    info = schema_manager.get_table_info(table_name)
    return json.dumps(info, indent=2, default=str)


# Tools
@mcp.tool()
def convert_to_sql(natural_language_query: str) -> Dict[str, Any]:
    """
    Convert natural language query to SQL

    Args:
        natural_language_query: The natural language question to convert

    Returns:
        Dictionary with generated SQL
    """
    # Create prompt
    schema_text = schema_manager.format_schema_for_prompt()

    print(f"Schema text: {schema_text}")

    prompt = f"""Database Schema:
{schema_text}

Convert this natural language query to SQL:

"{natural_language_query}"

Rules:
1. Use correct table and column names
2. Add WHERE clauses when filtering
3. Limit results to 100 rows
4. Return only SQL, no explanations

SQL:"""

    try:
        sql = llm_service.generate_sql(prompt)
        return {
            "success": True,
            "query": natural_language_query,
            "sql": sql,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": natural_language_query
        }


@mcp.tool()
def execute_sql(sql_query: str) -> Dict[str, Any]:
    """
    Execute SQL query on the database

    Args:
        sql_query: The SQL query to execute

    Returns:
        Dictionary with query results
    """
    try:
        # Validate query
        if not db_manager.validate_query(sql_query):
            return {
                "success": False,
                "error": "Query validation failed: potentially dangerous operation",
                "sql": sql_query
            }

        # Execute
        results = db_manager.execute_query(sql_query)

        return {
            "success": True,
            "sql": sql_query,
            "results": results,
            "row_count": len(results),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "sql": sql_query
        }


@mcp.tool()
def natural_language_query(query: str) -> Dict[str, Any]:
    """
    Convert natural language to SQL and execute it

    Args:
        query: Natural language question

    Returns:
        Dictionary with SQL and results
    """
    # Step 1: Convert to SQL
    conversion_result = convert_to_sql(query)

    if not conversion_result["success"]:
        return conversion_result

    sql = conversion_result["sql"]

    # Step 2: Execute SQL
    execution_result = execute_sql(sql)

    # Combine results
    if execution_result["success"]:
        return {
            "success": True,
            "natural_language_query": query,
            "generated_sql": sql,
            "results": execution_result["results"],
            "row_count": execution_result["row_count"],
            "conversion_success": True,
            "execution_success": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        return {
            "success": False,
            "natural_language_query": query,
            "generated_sql": sql,
            "error": execution_result["error"],
            "conversion_success": True,
            "execution_success": False
        }


@mcp.tool()
def get_table_sample(table_name: str, limit: int = 5) -> Dict[str, Any]:
    """
    Get sample data from a table

    Args:
        table_name: Name of the table
        limit: Maximum number of rows to return

    Returns:
        Dictionary with sample data
    """
    try:
        sample_data = db_manager.get_sample_data(table_name, limit)

        return {
            "success": True,
            "table": table_name,
            "sample_data": sample_data,
            "count": len(sample_data),
            "limit": limit,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "table": table_name
        }


# Prompts
@mcp.prompt()
def sql_generation_prompt(natural_query: str) -> str:
    """
    Template for generating SQL from natural language

    Args:
        natural_query: Natural language query

    Returns:
        Formatted prompt
    """
    schema_text = schema_manager.format_schema_for_prompt()

    return f"""Database Schema:
{schema_text}

Task: Convert this natural language query to valid SQL:

"{natural_query}"

Important:
- Use exact table and column names from schema
- Add appropriate joins if needed
- Include WHERE for filtering
- Add LIMIT 100 for large results
- Return only SQL code

SQL Query:"""


@mcp.prompt()
def sql_explanation_prompt(sql_query: str, results: List[Dict]) -> str:
    """
    Template for explaining SQL query results

    Args:
        sql_query: The SQL query executed
        results: Query results

    Returns:
        Prompt for explaining results
    """
    results_str = json.dumps(results[:3], indent=2, default=str)

    return f"""SQL Query:
{sql_query}

Query Results (first 3 rows):
{results_str}

Task: Explain what this query does and summarize the results in plain English.

Explanation:"""


if __name__ == "__main__":
    # Note: FastMCP currently handles its own lifecycle
    # We'll integrate with lifespan when FastMCP supports it
    print("=" * 60)
    print("NL2SQL MCP Server")
    print("=" * 60)

    # Initialize components
    db_manager.connect()

    # Load model in background
    import threading


    def load_model_async():
        try:
            llm_service.is_available()
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