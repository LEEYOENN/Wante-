import os
import sqlite3
import json
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_postgres import PGVector
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Tool 함수 임포트
from .tools import (
    create_router_chain,
    create_rag_chain,
    create_counseling_chain,
    create_chit_chat_chain,
    create_question_rewriter_chain,
    format_chat_history,
)

# DB 경로 및 로깅 설정
current_path = Path(__file__).resolve()
PROJECT_ROOT = current_path.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DB_PATH = str(DATA_DIR / "chat_logs.db")
DB_URL = os.getenv("DB_URL")

# DB_PATH = str(DATA_DIR / "vectorstore/chromadb_rag")
# LOG_DB_PATH = str(DATA_DIR / "chat_logs.db")
# CACHE_DB_PATH = str(DATA_DIR / "vectorstore/chromadb_cache")

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DB_PATH = os.path.join(BASE_DIR, "vectorstore/chromadb_rag")
# LOG_DB_PATH = os.path.join(BASE_DIR, "chat_logs.db")
# CACHE_DB_PATH = os.path.join(BASE_DIR, "vectorstore/chromadb_cache")


def setup_database():
    """Create the database and the 'chat_logs' table (if they don't already exist)."""
    conn = sqlite3.connect(LOG_DB_PATH, timeout=10)
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
        satisfaction INTEGER DEFAULT 0, -- [신규] 만족도 (0: N/A, 1: 유용, -1: 개선 필요)
        processed_for_cache INTEGER DEFAULT 0
    )
    """
    )

    try:
        cursor.execute("PRAGMA table_info(chat_logs)")
        columns = [col[1] for col in cursor.fetchall()]

        if "processed_for_cache" not in columns:
            print(
                "-> [DB 마이그레이션] 'processed_for_cache' 컬럼을 기존 chat_logs DB에 추가합니다."
            )
            cursor.execute(
                "ALTER TABLE chat_logs ADD COLUMN processed_for_cache INTEGER DEFAULT 0"
            )

    except sqlite3.OperationalError:
        # 테이블이 방금 생성되어 PRAGMA가 바로 작동 안 할 경우 등 예외 처리
        pass

    conn.commit()
    conn.close()
    print(f"-> 로그 DB '{LOG_DB_PATH}' 준비 완료.(캐시 라벨링 컬럼 포함)")


def log_chat(user_name, is_dm, question, answer, retrieved_docs, route):
    """Save chat history to SQLite DB. (include route)"""
    log_id = None  # 반환할 ID 초기화

    try:
        conn = sqlite3.connect(LOG_DB_PATH, timeout=10)
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

    # RAG retriever
    # if not os.path.exists(DB_PATH):
    #     raise FileNotFoundError(f"Not found vectorDB. '{DB_PATH}' Check your location")

    if not DB_URL:
        raise ValueError("[오류] .env 파일에 DATABASE_URL이 설정되지 않았습니다.")

    try:
        rag_vectorstore = PGVector(
            connection=DB_URL,
            embedding_function=embedding,
            collection_name="rag_documents",
        )
        rag_retriever = rag_vectorstore.as_retriever(
            search_type="similarity", search_kwargs={"k": 5}
        )
        print("-> RAG DB 로드 완료.")
    except Exception as e:
        raise Exception(f"RAG DB 'rag_documents' 컬렉션 연결 실패: {e}")

    # Semantic Cache retriever
    cache_retriever = None
    # if os.path.exists(CACHE_DB_PATH):
    print(f"-> Semantic DB 로드 중...")
    try:
        cache_vectorstore = PGVector(
            persist_directory=DB_URL,
            embedding_function=embedding,
            collection_name="semantic_cache",
        )
        # if cache_vectorstore.get(limit=1)["ids"]:
        #     print(
        #         f"-> Semantic DB 로드 완료. (문서 {len(cache_vectorstore.get()['ids'])} 개 발견"
        #     )
        #     # [핵심] DB가 비어있는 지 확인합니다.
        #     # .get(limit=1)['ids']가 비어있지 않아야 (문서가 1개라도 있어야) 리트리버를 생성합니다.
        cache_retriever = cache_vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"score_threshold": 0.95, "k": 1},
        )
        print(f"-> Semantic DB (PGVector) 로드 완료.")
        # else:
        # print(
        #     f"-> [경고] Semantic DB ({CACHE_DB_PATH})를 찾을 수 없습니다. 캐시 기능을 건너뜁니다."
        # )
    # except Exception as e:
    #     # 예: DB 파일 손상
    #     print(f"[오류] Semantic DB 로드 중 오류 발생: {e}. 캐시 기능을 건너뜁니다.")
    # else:
    #     print(
    #         f"-> [경고] 'Semantic DB' ({CACHE_DB_PATH})를 찾을 수 없습니다. 캐시 기능을 건너뜁니다."
    #     )
    except Exception as e:
        print(f"[경고] Semantic DB (PGVector) 로드 실패: {e}. 캐시 기능을 건너뜁니다.")

    question_rewriter_tool = create_question_rewriter_chain(llm)
    question_router_tool = create_router_chain(llm)
    rag_answer_tool = create_rag_chain(llm)
    counseling_tool = create_counseling_chain(llm)
    chit_chat_tool = create_chit_chat_chain(llm)

    # 그래프 노드 함수 정의
    # Cache Check Node
    def cache_check_node(state: GraphState, config: RunnableConfig):
        """
        [0 tokens] The first node in the graph. Check the Semantic DB first.
        """
        print("--- Node: cache_check_node ---")

        # 캐시 리트리버가 로드되지 않았으면 (DB 파일 없음) 건너뛰기
        if cache_retriever is None:
            print(
                "-> 'Semantic DB'가 없거나 비어있어 캐시를 건너뜁니다. 'router'로 이동."
            )
            question = state["messages"][-1].content
            return {"route": "continue", "question": question}

        question = state["messages"][-1].content

        # [토큰 0원] Semantic DB 검색
        cached_docs = cache_retriever.invoke(question, config)

        if cached_docs:  # cache Hit! (유사도 95% 이상)
            print(f"-> [Cache Hit] 유사 질문 발견! Semantic DB에서 답변을 반환합니다.")
            cached_answer = cached_docs[0].metadata["answer"]
            return {
                "answer": cached_answer,
                "route": "cache",  # cache route로 END
                "messages": [("ai", cached_answer)],
            }
        else:  # cache miss
            print("-> [Cache Miss] Semantic DB에 일치하는 항목 없음. route로 이동.")
            return {
                "route": "continue",
                "question": question,
            }  # continue 라우트로 route

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
        print("-> 질문 재구성 중...")
        messages = state["messages"]
        original_question = state["question"]

        question_to_use = ""

        if len(messages) > 1:
            print("-> 대화 기록 발견. 질문 재구성 중...")

            rewritten_question = question_rewriter_tool.invoke(
                {"messages": messages}, config
            )
            print(f"-> 원본 질문: {state['question']}")
            print(f"-> 재구성 된 질문: {rewritten_question}")
            question_to_use = rewritten_question
        else:
            print("-> 1. 첫 질문. 질문 재구성을 건너뜁니다.")
            question_to_use = original_question

        # Search for context
        print(f"-> '{question_to_use}' (으)로 문서 검색...")
        context_docs = rag_retriever.invoke(question_to_use, config)

        # Creatr RAG answer
        print(f"-> RAG 답변 생성...")
        answer = rag_answer_tool.invoke(
            {"question": question_to_use, "context": context_docs}, config
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
        # question = state["question"]
        messages_str = format_chat_history(state["messages"])
        response = chit_chat_tool.invoke({"messages": messages_str}, config)
        answer = response
        return {"answer": answer, "messages": [("ai", answer)]}

    # Graph Assemble
    print("--- LangGraph 조립 시작 ---")
    workflow = StateGraph(GraphState)

    # Add NODE
    workflow.add_node("cache_checker", cache_check_node)
    workflow.add_node("router", router_question)
    workflow.add_node("rag_agent_node", rag_node)
    workflow.add_node("counseling_agent_node", counseling_node)
    workflow.add_node("chit_chat_agent_node", chit_chat_node)

    # Set Entry Point
    workflow.set_entry_point("cache_checker")

    # Set Conditional Edge for cache_checker
    # cache (Hit) -> END
    # continue(Miss) -> router
    workflow.add_conditional_edges(
        "cache_checker",
        lambda state: state["route"],
        {
            "cache": END,
            "continue": "router",
        },
    )

    # Set Conditional Edges for route
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
    print("\n--- [TEST 1. Cache Hit] ---")
    config_1 = {"configurable": {"thread_id": "test-cache-hit"}}
    inputs_1 = {
        "messages": [("user", "2회 중도 포기 패널티 뭐야?")]
    }  # 95% 이상 유사한 질문
    for event in langgraph_chain.stream(inputs_1, config=config_1):
        if "cache_checker" in event:
            print(event)  # cache_checker가 cache 라우트를 반환해야 함
        if "answer" in event.get("cache_checker", {}):
            print(f"-> CACHED ANSWER: {event['cache_checker']['answer']}")

    print("\n--- [TEST 2. Cache Miss & RAG] ---")
    inputs_2 = {
        "messages": [("user", "훈련 장려금은 언제 지급되나요?")]
    }  # 캐시에 없는 질문
    config_2 = {"configurable": {"thread_id": "test-cache-miss"}}
    for event in langgraph_chain.stream(inputs_2, config=config_2):
        print(event)  # cache_checker -> route -> rag_agent_node 순서로 실행되어야 함
