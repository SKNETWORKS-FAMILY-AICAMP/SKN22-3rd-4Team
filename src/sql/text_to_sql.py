"""
Text-to-SQL engine for querying financial data
Converts natural language questions to SQL queries
"""

import logging
from typing import Dict, List, Optional
import duckdb
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)


class TextToSQL:
    """
    Converts natural language questions to SQL queries
    for financial data analysis
    """

    def __init__(
        self,
        database_url: str = "duckdb:///:memory:",
        llm_model: str = "gpt-4-turbo-preview",
        api_key: Optional[str] = None,
    ):
        """
        Initialize Text-to-SQL engine

        Args:
            database_url: Database connection string
            llm_model: LLM model for SQL generation
            api_key: OpenAI API key
        """
        self.database_url = database_url
        self.llm = ChatOpenAI(model=llm_model, temperature=0, openai_api_key=api_key)

        # Initialize database connection
        if "duckdb" in database_url:
            self.conn = duckdb.connect(database=":memory:")
        else:
            self.engine = create_engine(database_url)

        self.schema_info = None

    def create_financial_tables(self):
        """Create standard financial tables (Supabase Schema Mirror)"""

        # companies
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id UUID PRIMARY KEY,
                ticker TEXT NOT NULL UNIQUE,
                company_name TEXT NOT NULL,
                cik TEXT,
                industry TEXT,
                sector TEXT,
                description TEXT,
                logo_url TEXT,
                market_cap DECIMAL,
                employees INTEGER,
                exchange TEXT,
                website TEXT,
                created_at TIMESTAMPTZ DEFAULT now(),
                founded_year INTEGER,
                headquarters TEXT
            )
        """
        )

        # annual_reports
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS annual_reports (
                id UUID PRIMARY KEY,
                company_id UUID,
                fiscal_year INTEGER NOT NULL,
                period_ended DATE,
                revenue DECIMAL,
                cost_of_revenue DECIMAL,
                gross_profit DECIMAL,
                operating_income DECIMAL,
                net_income DECIMAL,
                eps DECIMAL,
                total_assets DECIMAL,
                total_liabilities DECIMAL,
                stockholders_equity DECIMAL,
                operating_cash_flow DECIMAL,
                investing_cash_flow DECIMAL,
                financing_cash_flow DECIMAL,
                profit_margin DECIMAL,
                roe DECIMAL,
                roa DECIMAL,
                debt_to_equity DECIMAL,
                current_ratio DECIMAL,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            )
        """
        )

        # quarterly_reports
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quarterly_reports (
                id UUID PRIMARY KEY,
                company_id UUID,
                fiscal_year INTEGER NOT NULL,
                fiscal_quarter INTEGER NOT NULL,
                period_ended DATE NOT NULL,
                revenue DECIMAL,
                gross_profit DECIMAL,
                operating_income DECIMAL,
                net_income DECIMAL,
                eps DECIMAL,
                operating_cash_flow DECIMAL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """
        )

        # stock_prices
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_prices (
                id UUID PRIMARY KEY,
                company_id UUID,
                price_date DATE NOT NULL,
                open_price DECIMAL,
                high_price DECIMAL,
                low_price DECIMAL,
                close_price DECIMAL,
                adjusted_close DECIMAL,
                volume BIGINT,
                market_cap DECIMAL,
                pe_ratio DECIMAL,
                pb_ratio DECIMAL,
                ps_ratio DECIMAL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """
        )

        # company_relationships
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS company_relationships (
                id UUID PRIMARY KEY,
                source_company TEXT NOT NULL,
                source_ticker TEXT,
                target_company TEXT NOT NULL,
                target_ticker TEXT,
                relationship_type TEXT NOT NULL,
                confidence DECIMAL DEFAULT 0.5,
                extracted_from TEXT,
                filing_date DATE,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """
        )

        # document_sections
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_sections (
                id UUID PRIMARY KEY,
                company_id UUID,
                content TEXT NOT NULL,
                section_name TEXT,
                report_type TEXT,
                report_date DATE,
                metadata JSON,
                created_at TIMESTAMPTZ DEFAULT now(),
                ticker TEXT,
                filing_date DATE
            )
        """
        )

        # documents (Vector Store placeholder)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY,
                content TEXT,
                metadata JSON,
                embedding FLOAT[]
            )
        """
        )

        logger.info("Created Supabase-compatible financial tables schema")
        self._update_schema_info()

    def _update_schema_info(self):
        """Update schema information for the LLM"""
        try:
            tables_info = self.conn.execute(
                """
                SELECT table_name, column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'main'
                ORDER BY table_name, ordinal_position
            """
            ).fetchdf()

            schema_text = "Database Schema:\n\n"

            for table in tables_info["table_name"].unique():
                schema_text += f"Table: {table}\n"
                table_cols = tables_info[tables_info["table_name"] == table]

                for _, row in table_cols.iterrows():
                    schema_text += f"  - {row['column_name']}: {row['data_type']}\n"

                schema_text += "\n"

            self.schema_info = schema_text

        except Exception as e:
            logger.error(f"Error updating schema info: {str(e)}")
            self.schema_info = "Schema information not available"

    def natural_language_to_sql(self, question: str) -> Dict:
        """
        Convert natural language question to SQL

        Args:
            question: Natural language question

        Returns:
            Dictionary with SQL query and explanation
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert SQL developer specializing in financial data analysis.
            Convert the user's natural language question into a valid SQL query.
            
            {schema}
            
            Guidelines:
            - Use proper SQL syntax for DuckDB
            - Include appropriate JOINs when querying multiple tables
            - Use aggregate functions when needed (SUM, AVG, COUNT, etc.)
            - Add appropriate WHERE clauses for filtering
            - Include ORDER BY and LIMIT when relevant
            - Calculate financial ratios when asked
            - Handle date ranges appropriately
            - The table 'annual_reports' contains yearly data, 'quarterly_reports' contains quarterly.
            - Stock prices are in 'stock_prices' table.
            
            Return ONLY the SQL query without any explanation or markdown formatting.
            """,
                ),
                ("user", "{question}"),
            ]
        )

        try:
            chain = prompt | self.llm
            response = chain.invoke(
                {
                    "schema": self.schema_info or "Schema not available",
                    "question": question,
                }
            )

            sql_query = response.content.strip()

            # Clean up the SQL (remove markdown code blocks if present)
            if sql_query.startswith("```"):
                sql_query = sql_query.split("```")[1]
                if sql_query.startswith("sql"):
                    sql_query = sql_query[3:]
                sql_query = sql_query.strip()

            return {"question": question, "sql": sql_query, "success": True}

        except Exception as e:
            logger.error(f"Error generating SQL: {str(e)}")
            return {
                "question": question,
                "sql": None,
                "success": False,
                "error": str(e),
            }

    def execute_query(self, sql: str) -> Dict:
        """Execute SQL query and return results"""
        try:
            result_df = self.conn.execute(sql).fetchdf()

            return {
                "success": True,
                "data": result_df,
                "row_count": len(result_df),
                "columns": list(result_df.columns),
            }

        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            return {"success": False, "error": str(e), "data": None}

    def query_with_natural_language(self, question: str) -> Dict:
        """Complete pipeline: NL question -> SQL -> Results"""
        sql_result = self.natural_language_to_sql(question)

        if not sql_result["success"]:
            return sql_result

        execution_result = self.execute_query(sql_result["sql"])

        return {
            "question": question,
            "sql": sql_result["sql"],
            "success": execution_result["success"],
            "data": execution_result.get("data"),
            "row_count": execution_result.get("row_count"),
            "error": execution_result.get("error"),
        }

    def load_data_from_dataframe(self, df: pd.DataFrame, table_name: str):
        """Load data from pandas DataFrame into database"""
        try:
            self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
            logger.info(f"Loaded {len(df)} rows into {table_name}")
            self._update_schema_info()

        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")

    def get_sample_questions(self) -> List[str]:
        """Get sample questions for the UI"""
        return [
            "What is the total revenue for Apple in 2023?",
            "Compare the net income of Microsoft and Google in the last 3 years",
            "Which companies have the highest profit margin?",
            "Show me the debt-to-equity ratio for all tech companies",
            "Calculate the operating cash flow trend for Tesla",
        ]
