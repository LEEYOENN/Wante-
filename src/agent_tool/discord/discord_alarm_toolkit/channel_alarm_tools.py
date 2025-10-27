# dm_alarm_tools.py
from typing import Type
import discord
from langchain_core.tools import BaseTool
from pydantic import BaseModel
import pandas as pd
from dotenv import load_dotenv
import os
import textwrap
import httpx

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_API_URL = "https://discord.com/api/v10"

# 채널로 공지 알림 보내기
# 1-1 채널로 전체 알림을 보내는 스키마 설정
class ChannelAlarm(BaseModel):
    channel_name: str
    content: str

# 1-2 채널로 전체 공지 알림을 보내는 도구 생성
class ChannelAlarmTool(BaseTool):
    name: str = "discord_channel_alarm"
    description: str = "DISCORD 공지 채널 이름과 공지 내용을 받아 채널로 공지 알림을 보냅니다."
    args_schema: Type[BaseModel] = ChannelAlarm

    # 동기 메서드는 사용하지 않음
    def _run(self, *args, **kwargs):
        raise NotImplementedError("ChannelAlarmTool은 비동기적으로 사용해야합니다.")
    
    async def _arun(self, channel_name: str, content: str) -> str:

        # 알림 전송할 채널 찾기
        try:
            discord_channels_info = pd.read_csv(r"C:\Users\user\potenup\Wante\data\discord_server_channel.csv")
        except FileNotFoundError:
            return "오류: discord_server_channel.csv 파일을 찾을 수 없습니다. "
        except Exception as e:
            return f"오류: CSV 파일 로드 중 에러 발생 - {e}"
        
        channel_id = 0
        for row in discord_channels_info.values:
            if row[1] == channel_name:
                channel_id = row[0]
                break
            
        if channel_id == 0:
            channel_id == os.getenv('DISCORD_NOTIFICATION_CHANNEL_ID')
        
        # 채널 알림 전송 로직 실행
        try:
            channel_id_int = int(channel_id)
            user_mentions = "@everyone"
            # 만약 Forbidden 에러가 발생한다면, 봇에게 'Send Messages'와 'Mention Everyone, Here, and All Roles' 권한이 없는 것

            alarm_message = textwrap.dedent(f"""
            # 📢 Potenup 공지 알림
            ## 📝 알림 내용                                       
            {content}

            --------------------------------

            **👤 알림 대상**
            {user_mentions}
            """)

            headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
            async with httpx.AsyncClient(headers=headers) as client:
                response = await client.post(
                    f"{DISCORD_API_URL}/channels/{channel_id_int}/messages",
                    json={"content": alarm_message}
                )
                response.raise_for_status() # 오류 시 예외 발생
            # await channel.send(alarm_message)
            return f"✅ '{channel_name}' 채널로 공지 알림을 성공적으로 보냈습니다."
        
        except discord.NotFound:
            # 존재하지 않는 사용자일 경우
            error_message = f"❌ '{channel_name}' 채널을 찾을 수 없습니다."
            print(error_message)
            return error_message

        except discord.Forbidden:
            # 봇이 DM을 보낼 수 없는
            error_message = f"❌ '{channel_name}' 해당 채널에 공지 알림을 보낼 수 없습니다. (권한이 있는지 확인해주세요.)"
            print(error_message)
            return error_message

        except Exception as e:
            error_message = f"❌ 채널 공지 알림 전송 중 오류 발생 {e}"
            print(error_message)
            return error_message


    
