# dm_alarm_tools.py
from typing import List, Type
import discord
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from ..bot_runner import global_client as client
from ..bot_runner import is_client_ready
import pandas as pd
import textwrap

# dm 알림 보내기
# 1-1 DM으로 알림을 보내는 스키마 설정
class DMAlarm(BaseModel):
    user_names: List[str] 
    content: str

# 1-2 DM으로 알림을 보내는 도구 생성
class DMAlarmTool(BaseTool):
    name: str = "discord_dm_alarm"
    description: str = "DM을 전송할 사용자 DISCORD ID를 리스트로 받아 개인으로 DM으로 공지 알림을 보냅니다."
    args_schema: Type[BaseModel] = DMAlarm

    # 동기 메서드는 사용하지 않음
    def _run(self, *args, **kwargs):
        raise NotImplementedError("DMAlarmTool은 비동기적으로 사용해야합니다.")
    
    async def _arun(self, user_names: List[str], content: str, ) -> str:
        # 봇이 Discord에 완전히 로그인 될 때까지 기다립니다.
        # is_client_ready 플래그가 설정될 때까지 비동기적으로 대기합니다.
        await is_client_ready.wait()

        results = []

        # csv 파일에서 사용자 discord id를 가져오기
        discord_members_info = pd.read_csv(r"C:\Users\user\potenup\Wante\data\discord_server_member.csv")

        user_ids = []

        for row in discord_members_info.values:
            if row[2] in user_names:
                user_ids.append(row[0])

        if len(user_ids) == 0:
            return "사용자를 찾을 수 없습니다."
        # DM 전송 로직 실행
        for user_id in user_ids:
            try:
                user_id_int = int(user_id)
                user = await client.fetch_user(user_id_int)
                user_mentions = f"<@{user.id}>"

                alarm_message = textwrap.dedent(f"""
                # 📢 Potenup 공지 알림
                ## 📝 알림 내용
                {content}

                --------------------------------

                **👤 알림 대상**
                {user_mentions}

                """)
                
                await user.send(alarm_message)
                results.append(f"✅ {user.name}님에게 DM을 성공적으로 보냈습니다.")
            
            except discord.NotFound:
                # 존재하지 않는 사용자일 경우
                error_message = f"❌ '{user.name}' 사용자를 찾을 수 없습니다."
                print(error_message)
                results.append(error_message)

            except discord.Forbidden:
                # 봇이 DM을 보낼 수 없는
                error_message = f"❌ '{user.name}' 해당 사용자에게 DM을 보낼 수 없습니다. (사용자가 같은 서버에 있는지 확인해주세요.)"
                print(error_message)
                results.append(error_message)

            except Exception as e:
                error_message = f"❌ DM 전송 중 오류 발생 {e}"
                print(error_message)
                results.append(error_message)

        return "\n".join(results)
    
