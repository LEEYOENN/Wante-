import os
import sqlite3
import json
from datetime import datetime
from dotenv import load_dotenv

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Tool 함수 임포트
from tools import (
    create_router_chain,
    create_rag_chain,
    create_counseling_chain,
    create_chit_chat_chain,
)

# DB 경로 및 로깅 설정
DB_PATH = "vectorstore/chromadb_rag"
LOG_DB_PATH = "chat_logs.db"


def setup_database():
    """Create the database and the 'chat_logs' table (if they don't already exist)."""
    conn = sqlite3.connect(LOG_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        user_name TEXT NOT NULL,
        is_dm BOOLEAN NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        retrieved_context TEXT,
        route TEXT NOT NULL,  -- [신규] 어떤 라우터로 처리되었는지 기록 (rag, counseling, chit_chat)
        satisfaction INTEGER DEFAULT 0 -- [신규] 만족도 (0: N/A, 1: 유용, -1: 개선 필요)
    )
    """
    )
    conn.commit()
    conn.close()
    print(f"-> 로그 DB '{LOG_DB_PATH}' 준비 완료.")


def log_chat(user_name, is_dm, question, answer, retrieved_docs, route):
    """Save chat history to SQLite DB. (include route)"""
    log_id = None  # 반환할 ID 초기화

    try:
        conn = sqlite3.connect(LOG_DB_PATH)
        cursor = conn.cursor()

        # Retrieved_docs (Document 객체 리스트)를 JSON 문자열로 변환
        context_list = (
            [
                {"page_content": doc.page_content, "metadata": doc.metadata}
                for doc in retrieved_docs
            ]
            if retrieved_docs
            else []
        )
        context_str = json.dumps(context_list, ensure_ascii=False)

        cursor.execute(
            "INSERT INTO chat_logs (timestamp, user_name, is_dm, question, answer, retrieved_context, route) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now(), user_name, is_dm, question, answer, context_str, route),
        )
        conn.commit()
        log_id = cursor.lastrowid  # 방금 생성된 ID 가져오기
        conn.close()
        print(f"-> 채팅 로그 저장 완료: (ID: {log_id}, Route: {route})")
    except Exception as e:
        print(f"[오류] 로그 DB 저장 실패: {e}")
    return log_id


# LangGraph State 정의
# 그래프가 작업하는 동안 유지할 메모리 또는 상태
class GraphState(TypedDict):
    question: str  # 사용자의 원본 질문
    route: str  # 라우터의 결정
    context: List[str]  # RAG 노드가 찾은 문서
    answer: str  # 봇의 최종 답변
    messages: Annotated[list, add_messages]  # 대화 기록


# Create Graph
def create_langgraph_chain():
    """
    Assemble the tools in 'tools.py' to create a 3-Way routing "Toolkit" (graph)
    """
    print("--- RAG 핵심 로직 초기화 ---")
    load_dotenv()

    if not os.getenv("TAVILY_API_KEY"):
        print(
            "[경고] TAVILY_API_KEY가 .env 파일에 없습니다. Counseling Node가 검색을 못할 수 있습니다."
        )

    # Common LLM and Retriever (for RAG node)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    embedding = OpenAIEmbeddings(model="text-embedding-3-small")

    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Not found vectorDB. '{DB_PATH}' Check your location")

    vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embedding)
    retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5})

    question_router_tool = create_router_chain(llm)
    rag_answer_tool = create_rag_chain(llm)
    counseling_tool = create_counseling_chain(llm)
    chit_chat_tool = create_chit_chat_chain(llm)

    # 그래프 노드 함수 정의
    # Router Node
    def router_question(state: GraphState, config: RunnableConfig):
        print("--- Node: route_question ---")
        question = state["messages"][-1].content  # 마지막 사용자 메세지
        route = question_router_tool.invoke({"question": question}, config)

        # 라우터의 출력을 정리 (llm이 'rag.' 처럼 추가 문자를 넣을 수 있음)
        if "rag" in route.lower():
            route = "rag"
        elif "counseling" in route.lower():
            route = "counseling"
        else:
            route = "chit_chat"

        print(f"-> Route determined: {route}")
        return {"route": route, "question": question}  # state update

    # RAG Node
    def rag_node(state: GraphState, config: RunnableConfig):
        print("--- Node: rag_node ---")
        question = state["question"]

        # Search for context
        context_docs = retriever.invoke(question, config)

        # Creatr RAG answer
        answer = rag_answer_tool.invoke(
            {"question": question, "context": context_docs}, config
        )

        return {"context": context_docs, "answer": answer, "messages": [("ai", answer)]}

    # Counseling Node
    def counseling_node(state: GraphState, config: RunnableConfig):
        print("--- Node: counseling_node ---")

        system_prompt = """당신은 교육생들의 진로와 취업 고민을 들어주는 따뜻하고 전문적인 '커리어 코치'입니다.
- 사용자의 질문에 공감하며 전문적인 조언을 제공하세요.
- '취업 동향', '전망', '최신 기술' 등 실시간 정보가 필요한 경우, 반드시 'tavily_search' 도구를 사용하여 최신 정보를 검색하고 그 결과를 바탕으로 답변해야 합니다.
- 그 외의 대화나 간단한 조언은 당신의 지식으로 답하세요."""

        messages_with_persona = [SystemMessage(content=system_prompt)] + state[
            "messages"
        ]

        response = counseling_tool.invoke({"messages": messages_with_persona}, config)

        answer = response["messages"][-1].content

        return {"answer": answer, "messages": [("ai", answer)]}

    # Chit_chat Node
    def chit_chat_node(state: GraphState, config: RunnableConfig):
        print("--- Node: chit_chat_node ---")
        question = state["question"]
        answer = chit_chat_tool.invoke({"question": question}, config)
        return {"answer": answer, "messages": [("ai", answer)]}

    # Graph Assemble
    print("--- LangGraph 조립 시작 ---")
    workflow = StateGraph(GraphState)

    # Add NODE
    workflow.add_node("router", router_question)
    workflow.add_node("rag_agent_node", rag_node)
    workflow.add_node("counseling_agent_node", counseling_node)
    workflow.add_node("chit_chat_agent_node", chit_chat_node)

    # Set Entry Point
    workflow.set_entry_point("router")

    # Set Conditional Edges
    workflow.add_conditional_edges(
        "router",
        lambda state: state["route"],
        {
            "rag": "rag_agent_node",
            "counseling": "counseling_agent_node",
            "chit_chat": "chit_chat_agent_node",
        },
    )

    # Set End points
    workflow.add_edge("rag_agent_node", END)
    workflow.add_edge("counseling_agent_node", END)
    workflow.add_edge("chit_chat_agent_node", END)

    # 컴파일 및 메모리(Checkpointer) 연결
    # (프로토타입 단계에서는 인메모리 사용, 운영 시 SqliteSaver 사용)
    # memory = SqliteSaver.from_conn_string(":memory:")
    # langgraph_chain = workflow.compile(checkpointer=memory)
    # memory = SqliteSaver.from_conn_string("conversations.db")
    conn = sqlite3.connect("conversations.db", check_same_thread=False)

    memory = SqliteSaver(conn=conn)

    # Discord 봇은 스레드 ID 관리가 복잡하므로, 우선 메모리 없이 컴파일합니다.
    langgraph_chain = workflow.compile(checkpointer=memory)

    print("Complete LangGraph Compile")
    return langgraph_chain


if __name__ == "__main__":
    setup_database()  # create db table
    langgraph_chain = create_langgraph_chain()  # creat graph

    # Test 1. RAG
    print("\n--- [TEST 1. RAG] ---")
    inputs = {"messages": [("user", "2회 중도 포기 패널티 뭐야?")]}
    config = {"configurable": {"thread_id": "test-rag"}}  # Thread ID (in memory)
    for event in langgraph_chain.stream(inputs, config=config):
        print(event)

    # Test 2. Counseling
    print("\n--- [TEST 2. Counseling] ---")
    inputs = {"messages": [("user", "IT 업계 취업하고 싶은데 전망이 어때?")]}
    config = {"configurable": {"thread_id": "test-counseling"}}
    for event in langgraph_chain.stream(inputs, config=config):
        print(event)

    # Test 3. Chit-chat
    print("\n--- [TEST 3. Chit-chat] ---")
    inputs = {"messages": [("user", "ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ")]}
    config = {"configurable": {"thread_id": "test-chitchat"}}
    for event in langgraph_chain.stream(inputs, config=config):
        print(event)
