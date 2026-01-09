from typing import Tuple, Optional
import re
import os
import requests
import logging

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import BaseOutputParser

from core.llm import hf_interface

load_dotenv()
logger = logging.getLogger(__name__)


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
        print(f"GQ NLQ: {self.current_model}")
        prompt_template = PromptTemplate(
            input_variables=["schema", "question"],
            template="""
                           You are a SQL expert. Convert the following natural language question into a SQL query using the database schema below.

                           Database Schema:
                           {schema}

                           Natural Language Question: {question}

                           Instructions:
                           1. Generate only the SQL query without any explanations
                           2. Use proper SQL syntax
                           3. Only query the tables that are necessary
                           4. Return the query in a single line

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
            print(f"Response text: {response_text}")
            sql_query = self.output_parser.parse(response_text)
            return sql_query

        except Exception as e:
            print(f"Error generating SQL with LLM: {e}")
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