from fastapi import FastAPI, Request
import sys
import os
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from contextlib import asynccontextmanager

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from agent_tool.discord.bot_runner import run_bot_in_background, global_client, is_client_ready

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from models.discord_langgraph import get_discord_langgraph

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from dto.dto import ChatbotRequestDTO, ChatbotResponseDTO

# FastAPI 생명주기 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("FastAPI applitcation statr..")
    run_bot_in_background()

    print("Discord bot이 시작되길 기다리는 중")
    await is_client_ready.wait()
    print("Discord bot이 준비되었습니다.")
    yield

    # 애플리케이션 종료시 실행
    print("FastAPI applitcation stop..")
    #await global_client.close()

####### FastAPI 서버 세팅 #######

app = FastAPI(lifespan=lifespan)

graph = get_discord_langgraph()

print(graph)

@app.post("/api/chatbot")
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