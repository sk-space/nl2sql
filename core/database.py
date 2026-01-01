import pymysql
from pymysql.cursors import DictCursor
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
import json

from core.config import config


class DatabaseManager:
    def __init__(self):
        self._connection = None

    def connect(self):
        """Establish database connection"""
        try:
            self._connection = pymysql.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                cursorclass=DictCursor,
                charset='utf8mb4',
                autocommit=True
            )
            print(f"✅ Connected to database: {config.DB_NAME}")
        except Exception as e:
            raise ConnectionError(f"❌ Database connection failed: {e}")

    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None
            print("✅ Database connection closed")

    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self._connection is not None and self._connection.open

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor"""
        if not self.is_connected():
            self.connect()

        cursor = self._connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute SQL query safely"""
        with self.get_cursor() as cursor:
            try:
                cursor.execute(query)
                results = cursor.fetchall()
                return results
            except Exception as e:
                raise ValueError(f"❌ Query execution failed: {e}")

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema for specific table"""
        query = """
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_KEY,
            COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
        """

        with self.get_cursor() as cursor:
            cursor.execute(query, (config.DB_NAME, table_name))
            columns = cursor.fetchall()

        return {
            "table_name": table_name,
            "columns": columns
        }

    def get_sample_data(self, table_name: str, limit: int = 3) -> List[Dict]:
        """Get sample data from table"""
        try:
            query = f"SELECT * FROM `{table_name}` LIMIT %s"
            with self.get_cursor() as cursor:
                cursor.execute(query, (limit,))
                return cursor.fetchall()
        except Exception as e:
            print(f"⚠ Could not get sample data from {table_name}: {e}")
            return []

    def validate_query(self, query: str) -> bool:
        """Validate SQL query safety"""
        query_lower = query.lower().strip()

        # Safety checks
        dangerous_patterns = [
            'drop table',
            'truncate table',
            'delete from',
            'update ',
            'alter table'
        ]

        for pattern in dangerous_patterns:
            if pattern in query_lower:
                # Allow if there's a WHERE clause for DELETE/UPDATE
                if pattern in ['delete from', 'update ']:
                    if 'where' not in query_lower:
                        return False
                else:
                    return False

        return True

    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except:
            return False


db_manager = DatabaseManager()