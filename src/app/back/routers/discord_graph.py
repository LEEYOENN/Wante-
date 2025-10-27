from fastapi import FastAPI, Request, APIRouter
import sys
import os
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from fastapi.middleware.cors import CORSMiddleware
from utils.google_utils.google_util import auth, spreadsheet_to_dataframe

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from models.discord_langgraph import get_discord_langgraph

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from dto.dto import ChatbotRequestDTO, ChatbotResponseDTO

discord_router = APIRouter()

graph = get_discord_langgraph()

print(graph)

@discord_router.post("/api/chatbot")
async def chatbot(request: ChatbotRequestDTO):
    try:
        print(request.question)

        # config = RunnableConfig(
        #     recursion_limit=10,
        #     configurable={"thread_id":"user1"}
        # )

        result = None

        print("그래프 실행 시작")
        # result = await graph.ainvoke({"messages": [HumanMessage(content=request.question)]}, config=config)
        # for 대신 'async for'을 사용
        async for event in graph.astream({"messages": [HumanMessage(content=request.question)]}, stream_mode="values"):
            for key, value in event.items():
                print("-"*30, key, "-"*30)

                if key == "messages" and value:
                    value[-1].pretty_print()
                else:
                    print(value)
            result = event

        print("그래프 실행 완료")
        last_message = result['messages'][-1]
        return ChatbotResponseDTO(
            success=True,
            message="200 OK",
            data={
                "answer": last_message.content,
                "question": request.question
            }
        )
    except Exception as e:
        print(f"Error: {str(e)}")
        return ChatbotResponseDTO(
            success=False,
            message=f"오류가 발생했습니다: {str(e)}",
            data=None
        )