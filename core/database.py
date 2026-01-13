from typing import Any
import pymysql
from pymysql.cursors import DictCursor
from core.config import config
from logger import get_logger

logger = get_logger(__name__)

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
            logger.info(f"✅ Connected to database: {config.DB_NAME}")
        except Exception as e:
            raise ConnectionError(f"❌ Database connection failed: {e}")

    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("✅ Database connection closed")

    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self._connection is not None and self._connection.open

    def get_cursor(self) -> Any | None:
        """Context manager for database cursor."""
        if self._connection:
            return self._connection.cursor()
        return None


db_manager = DatabaseManager()