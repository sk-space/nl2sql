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


    def _get_table_indexes(self, table_name: str, database_name: str) -> Dict[str, List]:
        """Get index information grouped by index name"""
        query = """
        SELECT 
            INDEX_NAME,
            NON_UNIQUE,
            SEQ_IN_INDEX,
            COLUMN_NAME,
            COLLATION,
            CARDINALITY,
            INDEX_TYPE,
            INDEX_COMMENT,
            SUB_PART,
            PACKED,
            NULLABLE
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        ORDER BY INDEX_NAME, SEQ_IN_INDEX
        """

        with db_manager.get_cursor() as cursor:
            cursor.execute(query, (database_name, table_name))
            rows = cursor.fetchall()

        # Group by index name
        indexes = {}
        for row in rows:
            index_name = row['INDEX_NAME']
            if index_name not in indexes:
                indexes[index_name] = {
                    'name': index_name,
                    'is_unique': row['NON_UNIQUE'] == 0,
                    'type': row['INDEX_TYPE'],
                    'columns': [],
                    'details': row
                }
            indexes[index_name]['columns'].append({
                'column_name': row['COLUMN_NAME'],
                'sub_part': row['SUB_PART'],
                'collation': row['COLLATION']
            })

        return indexes


    def _get_foreign_keys(self, table_name: str, database_name: str) -> List[Dict]:
        """Get foreign key relationships"""
        query = """
        SELECT 
            kcu.CONSTRAINT_NAME,
            kcu.COLUMN_NAME,
            kcu.REFERENCED_TABLE_NAME,
            kcu.REFERENCED_COLUMN_NAME,
            rc.UPDATE_RULE,
            rc.DELETE_RULE
        FROM information_schema.KEY_COLUMN_USAGE kcu
        LEFT JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
            ON kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
            AND kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
        WHERE kcu.TABLE_SCHEMA = %s 
            AND kcu.TABLE_NAME = %s
            AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION
        """

        with db_manager.get_cursor() as cursor:
            cursor.execute(query, (database_name, table_name))
            return cursor.fetchall()


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
        """Get CREATE TABLE statement"""
        with db_manager.get_cursor() as cursor:
            cursor.execute(f"SHOW CREATE TABLE `{database_name}`.`{table_name}`")
            result = cursor.fetchone()
            return result['Create Table'] if result else ""


    def _get_sample_data(self, table_name: str, database_name: str, limit: int = 3) -> List[Dict]:
        """Get sample data from table"""
        with db_manager.get_cursor() as cursor:
            cursor.execute(f"SELECT * FROM `{database_name}`.`{table_name}` LIMIT %s", (limit,))
            return cursor.fetchall()


    def _calculate_table_summary(self, table_details: Dict) -> Dict:
        """Calculate summary statistics from table details"""
        columns = table_details.get('columns', [])
        indexes = table_details.get('indexes', {})
        foreign_keys = table_details.get('foreign_keys', [])
        basic_info = table_details.get('basic_info', {})

        # Count column types
        column_types = {}
        for col in columns:
            data_type = col.get('DATA_TYPE', '')
            column_types[data_type] = column_types.get(data_type, 0) + 1

        # Count constraints
        constraints = table_details.get('constraints', [])
        constraint_counts = {}
        for cons in constraints:
            cons_type = cons.get('CONSTRAINT_TYPE', '')
            constraint_counts[cons_type] = constraint_counts.get(cons_type, 0) + 1

        return {
            'total_columns': len(columns),
            'primary_key_columns': len([c for c in columns if c.get('COLUMN_KEY') == 'PRI']),
            'nullable_columns': len([c for c in columns if c.get('IS_NULLABLE') == 'YES']),
            'unique_columns': len([c for c in columns if c.get('COLUMN_KEY') == 'UNI']),
            'indexed_columns': len([c for c in columns if c.get('COLUMN_KEY') == 'MUL']),
            'total_indexes': len(indexes),
            'unique_indexes': len([idx for idx in indexes.values() if idx['is_unique']]),
            'foreign_key_count': len(foreign_keys),
            'estimated_rows': basic_info.get('TABLE_ROWS', 0),
            'table_size_mb': basic_info.get('total_mb', 0),
            'column_type_distribution': column_types,
            'constraint_summary': constraint_counts
        }


    def get_complete_table_details(self, table_name: str, database_name: str = None) -> Dict[str, Any]:
        try:
            table_details = {
                'database': database_name,
                'table_name': table_name,
                'basic_info': self._get_table_basic_info(table_name, database_name),
                'columns': self._get_table_columns(table_name, database_name),
                'indexes': self._get_table_indexes(table_name, database_name),
                'foreign_keys': self._get_foreign_keys(table_name, database_name),
                'constraints': self._get_table_constraints(table_name, database_name),
                'referential_constraints': self._get_referential_constraints(table_name, database_name),
                'create_statement': self._get_create_statement(table_name, database_name),
                'sample_data': self._get_sample_data(table_name, database_name, limit=3)
            }

            # Calculate derived information
            table_details['summary'] = self._calculate_table_summary(table_details)

            return table_details

        except Exception as e:
            raise Exception(f"Failed to get table details: {e}")


    def get_related_tables(self, table_name: str, database_name: str = None) -> Dict:
        try:
            if not database_name:
                with db_manager.get_cursor() as cursor:
                    cursor.execute("SELECT DATABASE() as db")
                    result = cursor.fetchone()
                    database_name = result['db'] if result else None

            related_tables = {
                'referenced_by': [],  # Tables that reference this table
                'references_to': []  # Tables that this table references
            }

            # Get tables that reference this table (foreign keys pointing TO this table)
            query_referenced_by = """
            SELECT DISTINCT
                kcu.TABLE_NAME as referencing_table,
                kcu.COLUMN_NAME as referencing_column,
                kcu.CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE kcu
            WHERE kcu.TABLE_SCHEMA = %s
                AND kcu.REFERENCED_TABLE_NAME = %s
            ORDER BY kcu.TABLE_NAME
            """

            with db_manager.get_cursor() as cursor:
                cursor.execute(query_referenced_by, (database_name, table_name))
                related_tables['referenced_by'] = cursor.fetchall()

            # Get tables that this table references (foreign keys FROM this table)
            # This uses the foreign_keys method we already have
            related_tables['references_to'] = self._get_foreign_keys(table_name, database_name)

            return related_tables

        except Exception as e:
            raise Exception(f"Failed to get related tables: {e}")


    def visualize_table_schema(self, table_name: str, database_name: str = None) -> str:
        details = self.get_complete_table_details(table_name, database_name)

        visualization = []
        visualization.append(f"┌──────────────────────────────────────┐")
        visualization.append(f"│ Table: {table_name:30} │")
        visualization.append(f"│ Database: {details['database']:27} │")
        visualization.append(f"└──────────────────────────────────────┘")
        visualization.append("")

        # Basic Info
        basic = details['basic_info']
        visualization.append(f"📊 BASIC INFORMATION")
        visualization.append(f"  Engine: {basic.get('ENGINE', 'N/A')}")
        visualization.append(f"  Rows: {basic.get('TABLE_ROWS', 0):,}")
        visualization.append(f"  Size: {basic.get('total_mb', 0)} MB")
        visualization.append(f"  Collation: {basic.get('TABLE_COLLATION', 'N/A')}")
        visualization.append("")

        # Columns
        visualization.append(f"📋 COLUMNS ({len(details['columns'])})")
        for col in details['columns']:
            key_symbol = ""
            if col['COLUMN_KEY'] == 'PRI':
                key_symbol = "🔑 "
            elif col['COLUMN_KEY'] == 'UNI':
                key_symbol = "⭐ "
            elif col['COLUMN_KEY'] == 'MUL':
                key_symbol = "🔗 "

            nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
            default = f" DEFAULT {col['COLUMN_DEFAULT']}" if col['COLUMN_DEFAULT'] else ""
            visualization.append(f"  {key_symbol}{col['COLUMN_NAME']:20} {col['COLUMN_TYPE']:15} {nullable}{default}")
        visualization.append("")

        # Indexes
        indexes = details['indexes']
        if indexes:
            visualization.append(f"📈 INDEXES ({len(indexes)})")
            for idx_name, idx_info in indexes.items():
                idx_type = "UNIQUE" if idx_info['is_unique'] else "INDEX"
                cols = ', '.join([col['column_name'] for col in idx_info['columns']])
                visualization.append(f"  {idx_name:20} ({idx_type}): {cols}")
            visualization.append("")

        # Foreign Keys
        fks = details['foreign_keys']
        if fks:
            visualization.append(f"🔗 FOREIGN KEYS ({len(fks)})")
            for fk in fks:
                visualization.append(
                    f"  {fk['COLUMN_NAME']} → {fk['REFERENCED_TABLE_NAME']}.{fk['REFERENCED_COLUMN_NAME']}")

        return "\n".join(visualization)

    # def get_full_schema_context(self, database_name: str = None) -> str:
    #     """Get the full database schema as a formatted string"""
    #     try:
    #         tables = self.get_table_list(database_name=database_name)
    #         schema_lines = []
    #
    #         for table in tables:
    #             details = self.get_complete_table_details(table, database_name)
    #             schema_lines.append(f"Table: {table}")
    #             for col in details['columns']:
    #                 schema_lines.append(f"  - {col['COLUMN_NAME']} ({col['COLUMN_TYPE']})")
    #             schema_lines.append("")
    #
    #         return "\n".join(schema_lines)
    #
    #     except Exception as e:
    #         raise Exception(f"Failed to get full schema context: {e}")


    def get_full_schema_context(self, database_name: str = None) -> str:
        """Return full schema context (complete details for every table) as a single JSON string."""
        try:
            if not database_name:
                with db_manager.get_cursor() as cursor:
                    cursor.execute("SELECT DATABASE() as db")
                    row = cursor.fetchone()
                    database_name = row["db"] if row else None

            if not database_name:
                raise ValueError("database_name is required (no active database selected)")

            tables = self.get_table_list(database_name=database_name)

            full_context = {
                "database": database_name,
                "table_count": len(tables),
                "tables": {},
            }

            for table_name in tables:
                full_context["tables"][table_name] = self.get_complete_table_details(
                    table_name=table_name,
                    database_name=database_name,
                )

            logger.info(full_context)

            return json.dumps(full_context, indent=2, default=str)

        except Exception as e:
            raise Exception(f"Failed to get full schema context: {e}")


schema_manager = SchemaManager()