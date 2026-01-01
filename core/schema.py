import json
from typing import Dict, Any

from core.config import config
from core.database import db_manager


class SchemaManager:
    def __init__(self):
        self._schema_cache = None

    def get_full_schema(self) -> Dict[str, Any]:
        """Get complete database schema"""
        if self._schema_cache:
            return self._schema_cache

        schema = {
            "database": config.DB_NAME,
            "tables": []
        }

        # Get all tables
        query = """
        SELECT TABLE_NAME, TABLE_COMMENT 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME
        """

        with db_manager.get_cursor() as cursor:
            cursor.execute(query, (config.DB_NAME,))
            tables = cursor.fetchall()

            for table in tables:
                table_name = table['TABLE_NAME']
                table_info = self.get_table_info(table_name)
                schema["tables"].append(table_info)

        self._schema_cache = schema
        return schema

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get detailed table information"""
        schema = db_manager.get_table_schema(table_name)
        sample_data = db_manager.get_sample_data(table_name)

        return {
            "name": table_name,
            "schema": schema["columns"],
            "sample_data": sample_data,
            "sample_count": len(sample_data)
        }

    def format_schema_for_prompt(self) -> str:
        """Format schema for LLM prompt"""
        schema = self.get_full_schema()
        lines = []

        lines.append(f"Database: {schema['database']}")
        lines.append("=" * 50)

        for table in schema["tables"]:
            lines.append(f"\nTable: {table['name']}")
            lines.append("-" * 30)

            for col in table["schema"]:
                nullable = "NULL" if col["IS_NULLABLE"] == "YES" else "NOT NULL"
                key = f" ({col['COLUMN_KEY']})" if col["COLUMN_KEY"] else ""
                comment = f" // {col['COLUMN_COMMENT']}" if col["COLUMN_COMMENT"] else ""
                lines.append(f"  {col['COLUMN_NAME']}: {col['DATA_TYPE']} {nullable}{key}{comment}")

            if table["sample_data"]:
                lines.append(f"\n  Sample data ({table['sample_count']} rows):")
                for i, row in enumerate(table["sample_data"][:2], 1):
                    lines.append(f"    Row {i}: {json.dumps(row, default=str)}")

        return "\n".join(lines)


schema_manager = SchemaManager()