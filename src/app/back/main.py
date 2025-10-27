from fastapi import FastAPI, Request
import uvicorn
import os
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.back.routers import google_ai_agent
from app.back.routers import discord_graph
from utils.google_utils.google_util import auth, spreadsheet_to_dataframe

from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()


# FastAPI 생명주기 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("FastAPI applitcation statr..")

    yield

    # 애플리케이션 종료시 실행
    print("FastAPI applitcation stop..")

####### FastAPI 서버 세팅 #######

app = FastAPI(lifespan=lifespan, title="WanteDash AI Agent server", vision="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


@app.get("/")
def init():
    return RedirectResponse(url="/index.html")

@app.get("/jobs")
def jobs():
    creds = auth('./credentials.json')
    ## .env 파일 ID 사용
    spreadsheet_id = os.getenv('STANDARD_INFO_SPREADSHEET_ID')
    worksheet_name = 'code'
    df = spreadsheet_to_dataframe(creds,spreadsheet_id,worksheet_name)
    return {
        'jobs':df['업무'].to_list()
    }

# 라우터 등록
app.include_router(google_ai_agent.google_router, prefix="/api", tags=["google"])
app.include_router(discord_graph.discord_router, prefix="/api", tags=["discord"])
print('static folder......')
# static 등록
# os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    # Render는 PORT 환경변수를 제공
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
