from core.database import db_manager
from core.schema import schema_manager
from core.llm import hf_interface
from core.agent import nl2sql_agent
from logger import get_logger, setup_file_logging

setup_file_logging("server.log")
logger = get_logger(__name__)

if __name__ == "__main__":
    db = db_manager
    try:
        db.connect()
        logger.info("Connected to database")
        logger.info("Is connected: ", db.is_connected())

        if db.is_connected():
            # Get complete table details
            db_name = "test_db"
            table_name = "employee"  # Replace with your table name
            details = schema_manager.get_schema_string(db_name)

            logger.info(f"Retrieved schema details for table: {details}")
            #
            # print("=" * 60)
            # print(f"COMPLETE TABLE ANALYSIS: {table_name}")
            # print("=" * 60)
            #
            # # Print summary
            # summary = details['summary']
            # print(f"\n📊 SUMMARY:")
            # print(f"  Total Columns: {summary['total_columns']}")
            # print(f"  Primary Keys: {summary['primary_key_columns']}")
            # print(f"  Foreign Keys: {summary['foreign_key_count']}")
            # print(f"  Indexes: {summary['total_indexes']} ({summary['unique_indexes']} unique)")
            # print(f"  Estimated Rows: {summary['estimated_rows']:,}")
            # print(f"  Table Size: {summary['table_size_mb']} MB")
            #
            # # Print column details
            # print(f"\n📋 COLUMNS ({len(details['columns'])}):")
            # for col in details['columns']:
            #     print(f"  {col['position']:2}. {col['COLUMN_NAME']:20} {col['COLUMN_TYPE']:20} "
            #           f"{col['COLUMN_KEY'] or '':5} {col['IS_NULLABLE']:10}")
            #
            # # Print indexes
            # if details['indexes']:
            #     print(f"\n📈 INDEXES:")
            #     for idx_name, idx_info in details['indexes'].items():
            #         print(f"  {idx_name}:")
            #         for col in idx_info['columns']:
            #             print(f"    - {col['column_name']}")
            #
            # # Print foreign keys
            # if details['foreign_keys']:
            #     print(f"\n🔗 FOREIGN KEYS:")
            #     for fk in details['foreign_keys']:
            #         print(f"  {fk['CONSTRAINT_NAME']}:")
            #         print(f"    {fk['COLUMN_NAME']} → {fk['REFERENCED_TABLE_NAME']}.{fk['REFERENCED_COLUMN_NAME']}")
            #         print(f"    On Update: {fk.get('UPDATE_RULE', 'N/A')}")
            #         print(f"    On Delete: {fk.get('DELETE_RULE', 'N/A')}")
            #
            # # Get related tables
            # related = schema_manager.get_related_tables(table_name)
            # if related['referenced_by'] or related['references_to']:
            #     print(f"\n🔄 TABLE RELATIONSHIPS:")
            #
            #     if related['references_to']:
            #         print("  This table REFERENCES:")
            #         for rel in related['references_to']:
            #             print(f"    - {rel['REFERENCED_TABLE_NAME']} via {rel['COLUMN_NAME']}")
            #
            #     if related['referenced_by']:
            #         print("  Referenced BY:")
            #         for rel in related['referenced_by']:
            #             print(f"    - {rel['referencing_table']} via {rel['referencing_column']}")
            #
            # # Visualize schema
            # print(f"\n🎨 SCHEMA VISUALIZATION:")
            # print(schema_manager.visualize_table_schema(table_name, db_name))
            #
            # # Export to JSON if needed
            # import json
            #
            # with open(f"{table_name}_schema.json", "w") as f:
            #     json.dump(details, f, indent=2, default=str)
            # print(f"\n✅ Schema exported to {table_name}_schema.json")
            #
            # client = hf_interface.load_model()
            # logger("Loaded model: ", model)

            # nl = "List the names of employees hired after 2020"
            nl = "Get details of all the projects and compute the spent budget over employee salary on each project and determine if project is costing more than allocated budget along with the remaining budget"
            sql = nl2sql_agent.generate_sql(nl, details)
            logger.info(f"Generated SQL: {sql}")

    finally:
        db.close()