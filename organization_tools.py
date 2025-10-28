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

@tool
def refine_qa_for_cache(question: str, answer: str) -> str:
    """
    (캐시 구축 스크립트 전용)
    LLM을 사용해 주어진 Q&A 쌍을 분석하여 Semantic Cache에 저장할 가치가 있는지 평가합니다.
    - Q&A가 고품질이고, 완전하며, 재사용 가능하면 '정제된 답변'을 반환합니다.
    - Q&A가 저품질(예: 농담, 단순 인사, 불완전)이면 'REJECT' 문자열을 반환합니다.
    """
    print(f"---Tool: refine_qa_for_cache (Q: {question[:30]}...) ---")

    try:
        refine_llm = ChatOpenAI(model= "gpt-4o-mini", temperature= 0)
        prompt = ChatPromptTemplate.from_template(
            """당신은 'Semantic Cache 품질 관리자'입니다.
            주어진 '질문'과 '답변' 쌍이 "모범 답안"으로 캐시에 저장될 가치가 있는지 평가해야 합니다.

            [평가 기준]
            1.  **유용한가?**: 질문과 답변이 실제 정보를 포함하고 있습니까?
                (예: "결석 규정" -> "20%입니다...") -> OK
            2.  **부적절하지 않은가?**: 단순 인사, 감사, 농담, 비속어가 아닙니까?
                (예: "ㅋㅋㅋ" -> "ㅋㅋㅋ", "고마워요" -> "도움이 되어 기뻐요") -> REJECT
            3.  **완결성이 있는가?**: 답변이 그 자체로 완전한 의미를 가집니다.
                (예: "네, 맞아요.") -> REJECT
                (예: "네, 결석은 20%까지 가능합니다.") -> OK

            [지시 사항]
            - 위 기준을 통과하면, 캐시로 저장하기에 적합한 '답변' 내용을 그대로 (또는 살짝 다듬어서) 반환하세요.
            - 위 기준을 하나라도 통과하지 못하면, 오직 'REJECT' 라는 단어 하나만 반환하세요.

            ---
            [질문]: {question}
            [답변]: {answer}
            ---
            [평가 결과 (답변 또는 REJECT)]:
            """
        )
        refine_chain = prompt | refine_llm | StrOutputParser()

        return refine_chain.invoke({"question": question, "answer": answer})
    
    except Exception as e:
        print(f"[Error] refine_qa_for_cache 실행 중 오류: {e}")
        return "REJECT"