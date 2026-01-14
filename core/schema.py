from typing import List, Dict, Any
import json
from core.database import db_manager
from logger import get_logger

logger = get_logger(__name__)


class SchemaManager:
    def __init__(self):
        self._connection = db_manager.connect()

    def get_database_list(self, exclude_system: bool = True) -> List[str]:
        try:
            with db_manager.get_cursor() as cursor:
                if exclude_system:
                    query = """
                    SELECT SCHEMA_NAME 
                    FROM information_schema.SCHEMATA 
                    WHERE SCHEMA_NAME NOT IN (
                        'information_schema', 
                        'mysql', 
                        'performance_schema', 
                        'sys'
                    )
                    ORDER BY SCHEMA_NAME
                    """
                else:
                    query = "SHOW DATABASES"

                cursor.execute(query)
                results = cursor.fetchall()

                if exclude_system:
                    return [row['SCHEMA_NAME'] for row in results]
                else:
                    return [row['Database'] for row in results]

        except Exception as e:
            raise Exception(f"Failed to get database list: {e}")


    def get_table_list(self, database_name: str = None) -> List[str]:
        try:
            with db_manager.get_cursor() as cursor:
                if database_name:
                    cursor.execute(f"SHOW TABLES FROM `{database_name}`")
                else:
                    cursor.execute("SHOW TABLES")

                results = cursor.fetchall()

                # Results format depends on how we connect
                key = f"Tables_in_{database_name}" if database_name else list(results[0].keys())[0]
                return [row[key] for row in results]

        except Exception as e:
            raise Exception(f"Failed to get table list: {e}")


    def _get_table_basic_info(self, table_name: str, database_name: str) -> Dict:
        """Get basic table information"""
        query = """
        SELECT 
            TABLE_NAME,
            TABLE_TYPE,
            ENGINE,
            ROW_FORMAT,
            TABLE_ROWS,
            AVG_ROW_LENGTH,
            ROUND(DATA_LENGTH / 1024 / 1024, 2) as data_mb,
            ROUND(INDEX_LENGTH / 1024 / 1024, 2) as index_mb,
            ROUND((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) as total_mb,
            DATA_FREE,
            AUTO_INCREMENT,
            TABLE_COLLATION,
            CREATE_TIME,
            UPDATE_TIME,
            CHECK_TIME,
            TABLE_COMMENT
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """

        with db_manager.get_cursor() as cursor:
            cursor.execute(query, (database_name, table_name))
            result = cursor.fetchone()
            return result if result else {}


    def _get_table_columns(self, table_name: str, database_name: str) -> List[Dict]:
        """Get detailed column information"""
        query = """
        SELECT 
            ORDINAL_POSITION as position,
            COLUMN_NAME,
            COLUMN_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            COLUMN_KEY,
            EXTRA,
            COLUMN_COMMENT,
            CHARACTER_SET_NAME,
            COLLATION_NAME,
            DATA_TYPE,
            CHARACTER_MAXIMUM_LENGTH,
            NUMERIC_PRECISION,
            NUMERIC_SCALE,
            DATETIME_PRECISION,
            PRIVILEGES
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
        """

        with db_manager.get_cursor() as cursor:
            cursor.execute(query, (database_name, table_name))
            return cursor.fetchall()


    def _get_table_indexes(self, table_name: str, database_name: str) -> Dict[str, Dict]:
        """
        Return minimal, query-relevant index metadata grouped by index name.
        """
        query = """
                    SELECT
                        INDEX_NAME,
                        NON_UNIQUE,
                        SEQ_IN_INDEX,
                        COLUMN_NAME,
                        INDEX_TYPE,
                        CARDINALITY,
                        SUB_PART
                    FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = %s
                      AND TABLE_NAME = %s
                    ORDER BY INDEX_NAME, SEQ_IN_INDEX
                """

        with db_manager.get_cursor() as cursor:
            cursor.execute(query, (database_name, table_name))
            rows = cursor.fetchall()

        indexes: Dict[str, Dict] = {}

        for row in rows:
            name = row["INDEX_NAME"]

            if name not in indexes:
                indexes[name] = {
                    "unique": row["NON_UNIQUE"] == 0,
                    "type": row["INDEX_TYPE"],
                    "cardinality": row["CARDINALITY"],
                    "columns": []
                }

            indexes[name]["columns"].append({
                "name": row["COLUMN_NAME"],
                "prefix_length": row["SUB_PART"]
            })

        return indexes

    def _get_foreign_keys(self, table_name: str, database_name: str) -> List[Dict]:
        """
        Return minimal foreign key metadata required for join inference.
        """

        query = """
                SELECT kcu.CONSTRAINT_NAME,
                       kcu.COLUMN_NAME,
                       kcu.REFERENCED_TABLE_NAME,
                       kcu.REFERENCED_COLUMN_NAME,
                       kcu.ORDINAL_POSITION
                FROM information_schema.KEY_COLUMN_USAGE kcu
                WHERE kcu.TABLE_SCHEMA = %s
                  AND kcu.TABLE_NAME = %s
                  AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION
                """

        with db_manager.get_cursor() as cursor:
            cursor.execute(query, (database_name, table_name))
            rows = cursor.fetchall()

        foreign_keys: Dict[str, Dict] = {}

        for row in rows:
            name = row["CONSTRAINT_NAME"]

            if name not in foreign_keys:
                foreign_keys[name] = {
                    "referenced_table": row["REFERENCED_TABLE_NAME"],
                    "columns": []
                }

            foreign_keys[name]["columns"].append({
                "local": row["COLUMN_NAME"],
                "referenced": row["REFERENCED_COLUMN_NAME"]
            })

        return list(foreign_keys.values())


    def _get_table_constraints(self, table_name: str, database_name: str) -> List[Dict]:
        """Get table constraints"""
        query = """
                SELECT 
                    CONSTRAINT_NAME,
                    CONSTRAINT_TYPE
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY CONSTRAINT_TYPE
                """

        with db_manager.get_cursor() as cursor:
            cursor.execute(query, (database_name, table_name))
            return cursor.fetchall()


    def _get_referential_constraints(self, table_name: str, database_name: str) -> List[Dict]:
        """Get detailed referential constraints"""
        query = """
        SELECT 
            CONSTRAINT_NAME,
            UNIQUE_CONSTRAINT_SCHEMA,
            UNIQUE_CONSTRAINT_NAME,
            MATCH_OPTION,
            UPDATE_RULE,
            DELETE_RULE
        FROM information_schema.REFERENTIAL_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = %s AND TABLE_NAME = %s
        """

        with db_manager.get_cursor() as cursor:
            cursor.execute(query, (database_name, table_name))
            return cursor.fetchall()

    def _get_create_statement(self, table_name: str, database_name: str) -> str:
        """Get CREATE TABLE statement as a single line"""
        with db_manager.get_cursor() as cursor:
            cursor.execute(f"SHOW CREATE TABLE `{database_name}`.`{table_name}`")
            result = cursor.fetchone()

        create_sql = result['Create Table'] if result else ""

        # Remove newlines and extra spaces
        create_sql_single_line = " ".join(create_sql.replace("\n", " ").replace("\r", " ").split())

        return create_sql_single_line

    def _get_sample_data(self, table_name: str, database_name: str, limit: int = 3) -> List[Dict]:
        """Get sample data from table"""
        with db_manager.get_cursor() as cursor:
            cursor.execute(f"SELECT * FROM `{database_name}`.`{table_name}` LIMIT %s", (limit,))
            return cursor.fetchall()


    def get_schema(self, database_name: str = None):
        """Get complete database schema information for relational DBs"""
        schema_info = {"tables": {}}

        try:
            cursor = db_manager.get_cursor()

            # Get all table names from INFORMATION_SCHEMA
            tables = self.get_table_list(database_name=database_name)
            logger.info(f"Tables found: {tables}")

            for table in tables:
                # Get columns for table
                cursor.execute("""
                               SELECT column_name, data_type, is_nullable, column_key
                               FROM information_schema.columns
                               WHERE table_schema =%s
                                 AND table_name = %s
                               ORDER BY ordinal_position;
                               """, (database_name, table))
                columns = cursor.fetchall()
                logger.info(f"Columns for table {table}: {columns}")

                # Get sample data
                cursor.execute(f"SELECT * FROM `{table}` LIMIT 3")
                rows = cursor.fetchall()
                logger.info(f"Sample data for table {table}: {rows}")
                for row in rows:
                    logger.info(f"Row: {row}")
                col_names = [desc[0] for desc in cursor.description]

                schema_info["tables"][table] = {
                    "create_statement": self._get_create_statement(table, database_name),
                    "columns": [
                        {
                            "name": col["COLUMN_NAME"],
                            "type": col["DATA_TYPE"],
                            "nullable": col["IS_NULLABLE"] == "YES",
                            "primary_key": col["COLUMN_KEY"] == "PRI"
                        }
                        for col in columns
                    ],
                    "sample_data": [dict(row) for row in rows]
                }
                logger.info(f"Schema info for table {table}: {schema_info['tables'][table]}")

            return schema_info

        except Exception as e:
            print(f"Error getting schema: {e}")
            raise

    def get_schema_string(self, database_name: str = None):
        """Convert schema to string format for LLM context"""
        schema_info = self.get_schema(database_name)
        schema_string = "Database Schema:\n\n"

        for table_name, table_info in schema_info["tables"].items():
            schema_string += f"Table: {table_name}\n"
            schema_string += f"Create Statement: {table_info['create_statement']}\n"
            schema_string += "Columns:\n"

            for col in table_info["columns"]:
                pk_flag = " PRIMARY KEY" if col["primary_key"] else ""
                null_flag = " NOT NULL" if not col["nullable"] else ""
                schema_string += f"  - {col['name']} ({col['type']}{pk_flag}{null_flag})\n"

            if table_info["sample_data"]:
                schema_string += "Sample Data:\n"
                for sample in table_info["sample_data"][:2]:  # Show only 2 samples
                    schema_string += f"  {sample}\n"

            schema_string += "\n"

        return schema_string


schema_manager = SchemaManager()