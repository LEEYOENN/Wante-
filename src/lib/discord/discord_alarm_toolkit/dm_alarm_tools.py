# dm_alarm_tools.py
from typing import List, Type
import discord
from langchain_core.tools import BaseTool
from pydantic import BaseModel
import pandas as pd
import textwrap
import httpx
from dotenv import load_dotenv
import os

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_API_URL = "https://discord.com/api/v10"

# dm 알림 보내기
# 1-1 DM으로 알림을 보내는 스키마 설정
class DMAlarm(BaseModel):
    user_names: List[str] 
    content: str

# 1-2 DM으로 알림을 보내는 도구 생성
class DMAlarmTool(BaseTool):
    name: str = "discord_dm_alarm"
    description: str = "DM을 전송할 사용자 Discord name을 리스트로 받아 개인으로 DM으로 공지 알림을 보냅니다."
    args_schema: Type[BaseModel] = DMAlarm

    # 동기 메서드는 사용하지 않음
    def _run(self, *args, **kwargs):
        raise NotImplementedError("DMAlarmTool은 비동기적으로 사용해야합니다.")
    
    async def _arun(self, user_names: List[str], content: str, ) -> str:

        results = []

        # csv 파일에서 사용자 discord id를 가져오기
        try:
            discord_members_info = pd.read_csv(r"C:\Users\user\potenup\Wante\data\discord_server_member.csv")
        except FileNotFoundError:
            return "오류: discord_server_member.csv 파일을 찾을 수 없습니다. "
        except Exception as e:
            return f"오류: CSV 파일 로드 중 에러 발생 - {e}"
        
        user_ids = []

        for row in discord_members_info.values:
            if row[2] in user_names:
                user_ids.append(row[0])

        if len(user_ids) == 0:
            return "사용자를 찾을 수 없습니다."
        
        # HTTPX 비동기 클라이언트
        headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}

        async with httpx.AsyncClient(headers=headers) as client:
            for user_id in user_ids:
                user_id_int = int(user_id)
                user_mentions = f"<@{user_id_int}>"
                try:

                    alarm_message = textwrap.dedent(f"""
                    # 📢 Potenup 공지 알림
                    ## 📝 알림 내용
                    {content}

                    --------------------------------

                    **👤 알림 대상**
                    {user_mentions}

                    """)
                    
                    # 사용자에게 DM 보낼 채널 생성
                    dm_channel_response = await client.post(
                        f"{DISCORD_API_URL}/users/@me/channels",
                        json={"recipient_id": user_id_int}
                    )
                    dm_channel_response.raise_for_status() # 오류 시 에러 발생
                    dm_channel_id = dm_channel_response.json()["id"]
                    
                    # 생성된 DM 채널에 메시지 전송
                    await client.post(
                        f"{DISCORD_API_URL}/channels/{dm_channel_id}/messages",
                        json={"content": alarm_message}
                    )
                    results.append(f"Success: {user_mentions}님에게 DM을 성공적으로 보냈습니다.")

                except discord.NotFound:
                    # 존재하지 않는 사용자일 경우
                    error_message = f"Error: '{user_mentions}' 사용자를 찾을 수 없습니다."
                    print(error_message)
                    results.append(error_message)

                except discord.Forbidden:
                    # 봇이 DM을 보낼 수 없는
                    error_message = f"Error: '{user_mentions}' 해당 사용자에게 DM을 보낼 수 없습니다. (사용자가 같은 서버에 있는지 확인해주세요.)"
                    print(error_message)
                    results.append(error_message)

                except Exception as e:
                    error_message = f"Error: DM 전송 중 오류 발생 {e}"
                    print(error_message)
                    results.append(error_message)

        return "\n".join(results)
    
