import os
from dotenv import load_dotenv
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import PromptTemplate
from core.llm import hf_interface
from logger import get_logger

logger = get_logger(__name__)

load_dotenv()


class SQLOutputParser(BaseOutputParser):
    """Custom output parser to extract SQL from LLM response"""

    def parse(self, text: str):
        # Extract SQL query from the response
        lines = text.strip().split('\n')
        sql_query = None

        for line in lines:
            line = line.strip()
            if line.upper().startswith('SELECT') or \
                    line.upper().startswith('INSERT') or \
                    line.upper().startswith('UPDATE') or \
                    line.upper().startswith('DELETE') or \
                    line.upper().startswith('WITH'):
                sql_query = line
                # Remove code block markers if present
                sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
                # Remove trailing semicolon if we want to add it consistently
                if sql_query.endswith(';'):
                    sql_query = sql_query[:-1]
                break

        return sql_query




class NL2SQLAgent:
    def __init__(self):
        self.output_parser = SQLOutputParser()
        self.current_model = hf_interface.load_model()
        self.base_url = os.getenv("HF_API_URL")
        self.headers = {
            "Authorization": f"Bearer {os.getenv('HF_TOKEN')}",
            "Content-Type": "application/json"
        }
        self.client = hf_interface.load_model()
        if not self.client:
            raise RuntimeError("Failed to load LLM model for NL2SQLAgent")

    def generate_sql(self, natural_language_query, schema_context):
        """Generate SQL from natural language query"""
        logger.info(f"GQ NLQ: {self.current_model}")
        prompt_template = PromptTemplate(
            input_variables=["schema", "question"],
            template="""
                            You are a SQL expert. Convert the following natural language question into a SQL query using the database schema below.
                            You are an expert database engineer and SQL query generator.
                            You specialize in converting natural language requests into syntactically correct, optimized, and secure SQL queries.
                            You strictly follow the database schema provided.
                            You never hallucinate tables, columns, or relationships.
                            You understand indexing, query planning, and efficient data retrieval methods.
                            You intentionally avoid unnecessary complexity in queries and try to make the query as simple as possible.
                            You always return the SQL query in a single line without any explanations or additional text.
            
            
                            DATABASE SCHEMA:
                            {schema}
                            
                            Natural Language Question: {question}
                            
                            INSTRUCTIONS:
                            1. Generate only the SQL query without any explanations.
                            2. USE PROPER SQL SYNTAX.
                            3. ENSURE the query is OPTIMIZED for performance and accuracy.
                            4. Use ONLY the tables, columns, and relationships provided in the schema.
                            5. Do NOT assume missing columns or infer unnamed relationships.
                            6. PROPERLY analyze the natural language question to understand the INTENT and required data.
                            7. READ the schema CAREFULLY to avoid referencing non-existent tables or columns.
                            8. Analyze the database schema properly to identify relevant tables, keys, indexes and relationships in details.
                            9. Always use table aliases to improve query readability.
                            10. Make sure to use JOINs appropriately and only when required based on the relationships defined in the schema.
                            11. Validate the SQL query against the schema to ensure all referenced tables and columns exist.
                            12. Always return the query in a single line.
                            
                            SQL Query:
                       """
        )

        # Use the modern LangChain approach
        try:
            # Method 1: Use invoke (preferred in newer versions)
            if hasattr(self.current_model, 'invoke'):
                response = self.current_model.invoke(
                    prompt_template.format(
                        schema=schema_context,
                        question=natural_language_query
                    )
                )
                # Handle different response types
                if hasattr(response, 'content'):
                    response_text = response.content
                else:
                    response_text = str(response)
            else:
                # Method 2: Use __call__ for older compatibility
                response_text = self.current_model(
                    prompt_template.format(
                        schema=schema_context,
                        question=natural_language_query
                    )
                )
            logger.info(f"Response text: {response_text}")

            sql_query = self.output_parser.parse(response_text)
            logger.info(f"Response query: {sql_query}")

            return response_text

        except Exception as e:
            logger.info(f"Error generating SQL with LLM: {e}")
            # Fallback to rule-based generation
            return self.generate_sql_rule_based(natural_language_query)




    def generate_sql_rule_based(self, natural_language_query):
        """Simple rule-based SQL generation as fallback"""
        query_lower = natural_language_query.lower()

        rules = [
            (["engineer", "engineering"], "SELECT * FROM employees WHERE department = 'Engineering'"),
            (["hr", "human resources"], "SELECT * FROM employees WHERE department = 'HR'"),
            (["market", "marketing"], "SELECT * FROM employees WHERE department = 'Marketing'"),
            (["sales"], "SELECT * FROM employees WHERE department = 'Sales'"),
            (["average", "avg", "salary"], "SELECT department, AVG(salary) as average_salary FROM employees GROUP BY department"),
            (["high", "highest", "max", "salary"], "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 1"),
            (["low", "lowest", "min", "salary"], "SELECT name, salary FROM employees ORDER BY salary ASC LIMIT 1"),
            (["recent", "new", "hired", "hire date"], "SELECT name, hire_date FROM employees ORDER BY hire_date DESC"),
            (["project", "projects"], "SELECT p.name as project_name, d.name as department_name FROM projects p JOIN departments d ON p.department_id = d.id"),
            (["count", "how many", "employees"], "SELECT COUNT(*) as total_employees FROM employees"),
            (["department", "departments", "list"], "SELECT name, budget FROM departments"),
        ]

        for keywords, sql in rules:
            if any(keyword in query_lower for keyword in keywords):
                return sql

        return "SELECT * FROM employees LIMIT 10"


nl2sql_agent = NL2SQLAgent()