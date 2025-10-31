import os, shutil, sys
from datetime import datetime
from dotenv import load_dotenv
from fastapi import APIRouter, UploadFile, Form, File
from typing import Annotated, Optional
from pydantic import BaseModel
from pathlib import Path
from langchain_core.messages import AIMessage, HumanMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))
from models.general_agent import GeneralAgent  # chat, reset_agent

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from utils.google_utils.google_util import auth
from lib.google.prompts.prompt_generator import make_prompt
from lib.google.prompts.system_prompt import GENERAL_PROMPT
from utils.postgres_utils.postgresql_memory import get_session_history

current_path = Path(__file__).resolve()
PROJECT_ROOT = current_path.parent.parent.parent.parent.parent
CREDENTIALS_FILE_PATH = PROJECT_ROOT / "credentials.json"
print(CREDENTIALS_FILE_PATH)

google_router = APIRouter()

load_dotenv()

project_name = "wanted_2nd_wantedash"
os.environ["LANGSMITH_PROJECT"] = project_name
UPLOAD_DIRECTORY = "./uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

creds_file = CREDENTIALS_FILE_PATH
creds = auth(creds_file)

g_agent = GeneralAgent(creds, GENERAL_PROMPT.format(**make_prompt(creds)))


@google_router.get("/reset")
def reset():
    g_agent.reset_agent(GENERAL_PROMPT.format(**make_prompt(creds)))
    return {"result": "reset"}

@google_router.get("/messages/{id}")
def messages(id:str):
    print(id)
    history = get_session_history(session_id=id)
    results = []
    for message in history:
        results.append(
            {
                'type':'AI' if isinstance(message, AIMessage) else 'HUMAN' if isinstance(message, HumanMessage) else 'BASE',
                'content': message.content,
                'conversation_id': message.conversation_id,
                'created_at': message.created_at
            }
        )
    # print(results)
    return {"result":results}

@google_router.post("/chatbot/submit")
async def for_student(
    id: Annotated[str, Form()],
    message: Annotated[str, Form()],
    file: Annotated[Optional[UploadFile], File()] = None,
):
    #print(message)
    print(file)
    # 1. 파일 로컬에 저장
    if file and file.filename:
        _name, _ext = os.path.splitext(file.filename)
        _filename = f'{_name}-{datetime.today().strftime("%Y%m%d%H%M-%f")}{_ext}'
        _file_path = os.path.join(UPLOAD_DIRECTORY, _filename)
        print("****** file upload ******", _file_path)
        try:
            ## 저장될 파일명은 기존 파일명에 "%Y%m%d%H%M-%f" 붙여 생성
            # shutil.copyfileobj를 사용해 파일을 복사합니다.
            with open(_file_path, "wb") as fp:
                shutil.copyfileobj(file.file, fp)
            message = f"{message}, 업로드 파일은 {_filename} 입니다."
        except Exception as e:
            print(f"message: 파일 업로드 중 오류 발생: {e}")
        finally:
            file.file.close()
    # 2. 메시지에 추가 : '로컬 파일 경로' 는 '저장된 파일 패스' 입니다.
    ## 세션 처리 방법 고민 필요 -> 클라이언트에서 생성하여 전송
    cfg = {"configurable": {"session_id": id}}
    result = g_agent.chat(message, cfg)
    print(result)
    return result
