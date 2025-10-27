import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

LOG_DB_PATH = "chat_logs.db"
REPORT_SAVE_PATH = "reports"  # 리포트 저장 폴더


# Tool 1. Search logs in DB
@tool
def get_chat_logs(days_ago: int = 7, route: str = None) -> str:
    """
    Search for logs in 'chat_logs.db' for a specified period (the last N days).
    You cna filter by 'route' (e.g., 'rag', 'counseling').
    The results are returned as a Pandas DataFrame (string) using .to_string().
    """
    print(f"--- Tool: get_chat_logs (days_ago= {days_ago}, route= {route}) 실행 ---")
    try:
        conn = sqlite3.connect(LOG_DB_PATH, timeout= 10)

        # Data Calculation
        start_date = (datetime.now() - timedelta(days=days_ago)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Create a Query
        query = "SELECT timestamp, user_name, route, question, answer, satisfaction FROM chat_logs WHERE timestamp >= ?"
        params = [start_date]

        if route:
            query += " AND route = ?"
            params.append(route)

        # Load to Data
        df = pd.read_sql_query(query, conn, params=tuple(params))
        conn.close()

        if df.empty:
            return f"There are no '{route or 'all'}' logs for {days_ago} days."

        return df.to_string()
    except Exception as e:
        return f"An error occurred while searching the DB: {e}"


@tool
def analyze_log_trends(logs_string: str) -> str:
    """
    Analyze the log string (DataFrame.to_string()) received via 'get_chat_logs' using LLM.
    It returns the 'Top 5 Most Frequently Asked Questions', 'Major Chat Topics' and 'Satisfaction Summary'.
    """
    print("--- Tool: Run analyze_log_trends ---")
    if not logs_string or "No logs" in logs_string:
        return "No logs to analyze"

    # LLM for analysis(gpt-4o-mini or gpt 4o)
    analyzer_llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """#You must write the report in Korean.
         You are the 'Organization AI Agent' analyzing the logs of 'WanteDash'.
         Please analyze the given chat log (a Pandas DataFrame string) and summarize the following three items in a concise Markdown report.
         1. **Top 5 Key Questions:** (Most frequently asked questions and number of times asked)
         2. **Key Topics:** (Key concerns revealed in the logs, e.g., Penalty Regulations, Career Counseling)
         3. **Satisfaction Summary:** (Summary of positive/negative ratio based on the satisfaction column(1: Useful, -1: Needs Improvement))
         """,
            ),
            ("user", "Please analyze the following logs: \n\n{logs}"),
        ]
    )

    analysis_chain = prompt | analyzer_llm | StrOutputParser()

    try:
        return analysis_chain.invoke({"logs": logs_string})
    except Exception as e:
        return f"An error occurred while analyzing the log: {e}"


@tool
def save_report_to_markdown(report_content: str, filename: str) -> str:
    """
    Save the completed report (Markdown string) as an .md file in the reports folder.
    Filename example: 'weekly_report_2025-10-26.md'
    """
    print(f"--- Tool: save_report_to_markdown (filename= {filename}) 실행 ---")
    if not os.path.join(REPORT_SAVE_PATH, filename):
        os.makedirs(REPORT_SAVE_PATH)

    file_path = os.path.join(REPORT_SAVE_PATH, filename)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        return f"Report saved successfully: {file_path}"
    except Exception as e:
        return f"An error occurred while saving the file: {e}"
