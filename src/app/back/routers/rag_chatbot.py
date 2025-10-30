from fastapi import APIRouter
from langchain_core.runnables import RunnableConfig
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))
from src.lib.rag.rag_core import create_langgraph_chain, setup_database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from dto.dto import ChatbotRequestDTO, ChatbotResponseDTO

rag_router = APIRouter()

# Loed to chain from yeon's LangGraph
try:
    setup_database()
    langgraph_chain = create_langgraph_chain()
    print("RAG LangGraph Chain loaded successfully")
except Exception as e:
    print(f"Error loading RAG chain: {e}")
    langgraph_chain = None


@rag_router.post("/chatbot/rag")
async def chatbot(request: ChatbotRequestDTO):
    if langgraph_chain is None:
        return ChatbotResponseDTO(
            success=False, message="500 RAG 챗봇이 로드되지 않았습니다.", data=None
        )

    try:
        print(f"RAG 챗봇 호출: {request.question}")

        # RUN teo's RAG chatbot
        # Discord 봇과 동일하게 스레드 ID는 임시로 사용
        config = {"configurable": {"thread_id": f"rag_session_{request.question[:5]}"}}
        inputs = {"messages": [("user", request.question)]}

        final_state = langgraph_chain.invoke(inputs, config=config)

        answer = final_state.get("answer", "답변을 생성하지 못했습니다.")

        return ChatbotResponseDTO(
            success=True,
            message="200 OK",
            data={"answer": answer, "question": request.question},
        )
    except Exception as e:
        print(f"Error during RAG chat: {str(e)}")
        return ChatbotResponseDTO(
            success=False, message=f"RAG 챗봇 오류 {str(e)}", data=None
        )
