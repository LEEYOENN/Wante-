# dm_alarm_tools.py
from typing import Type, List
import discord
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import pandas as pd
from dotenv import load_dotenv
import os
import textwrap
import httpx
import datetime

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_API_URL = "https://discord.com/api/v10"

# 채널로 공지 알림 보내기
# 1-1 채널로 전체 알림을 보내는 스키마 설정
class ChannelAlarm(BaseModel):
    channel_names: List[str] = Field(description = "The name list of the Discord channel to which announcement notifications will be sent. For example, ['공지', '일반'] This name is retrieved from a CSV file registered in the system.")
    contents: List[str] = Field(description = "The actual message (announcement) list to be sent to the channel. May include Markdown format.")

# 1-2 채널로 전체 공지 알림을 보내는 도구 생성
class ChannelAlarmTool(BaseTool):
    name: str = "discord_channel_alarm"
    description: str = (
        "Sends a **public announcement notification** to the specified Discord channel."
        "This tool first looks up the channel name in a CSV file to find its ID."
        "If the channel name isn't found in the CSV, it sends the message to the **preset default announcement channel**."
        "Use this for important announcements, urgent notifications, etc. that need to be sent to all server members."
    )
    args_schema: Type[BaseModel] = ChannelAlarm

    # 동기 메서드는 사용하지 않음
    def _run(self, *args, **kwargs):
        raise NotImplementedError("ChannelAlarmTool은 비동기적으로 사용해야합니다.")
    
    async def _arun(self, channel_names: List[str], contents: List[str]) -> str:

        # channel_names 리스트와 contents 리스트의 길이가 같은지 확인
        if len(channel_names) != len(contents):
            return "오류: 채널 이름 리스트와 알림 내용 리스트의 길이가 일치하지 않습니다."
        
        results = []

        # 알림 전송할 채널 찾기
        try:
            discord_channels_info = pd.read_csv(r"C:\Users\user\potenup\Wante\data\discord_server_channel.csv")
        except FileNotFoundError:
            return "오류: discord_server_channel.csv 파일을 찾을 수 없습니다. "
        except Exception as e:
            return f"오류: CSV 파일 로드 중 에러 발생 - {e}"
        

        headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
        async with httpx.AsyncClient(headers=headers) as client:
            # 리스트 순회하며 각 채널에 메시지 전송
            for i in range(len(channel_names)):
                channel_name = channel_names[i]
                content = contents[i]
          
                channel_id = 0
                for row in discord_channels_info.values:
                    if row[1] == channel_name:
                        channel_id = row[0]
                        break
                fallback_used = False   
                if channel_id == 0:
                    channel_id = os.getenv('DISCORD_NOTIFICATION_CHANNEL_ID')
                    fallback_used = True

                # 채널 알림 전송 로직 실행
                try:
                    channel_id_int = int(channel_id)
                    user_mentions = "@everyone"
                    # 만약 Forbidden 에러가 발생한다면, 봇에게 'Send Messages'와 'Mention Everyone, Here, and All Roles' 권한이 없는 것

                    main_message = f"{user_mentions}님, 새로운 공지사항이 도착했습니다.\n# ✨ Potenup 공지 알림\n\n## 📌 공지 내용 \n{content}\n\n"
                    embed_payload = {
                        "content": main_message,
                        "embeds": [
                            {
                                "color": 0x5865F2, # 10진수 5793266 (디스코드 블루)
                                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                "fields": [                                    
                                    {
                                        "name": "🧑‍💻 알림 대상\n",
                                        "value": user_mentions,
                                        "inline": False
                                    }
                                ],
                                "footer": {
                                    "text": "Potenup"
                                }
                            }
                        ]
                    }

                    response = await client.post(
                        f"{DISCORD_API_URL}/channels/{channel_id_int}/messages",
                        json=embed_payload# {"content": alarm_message}
                    )
                    response.raise_for_status() # 오류 시 예외 발생
            
                    # await channel.send(alarm_message)
                    if fallback_used:
                        results.append(f"Success: CSV에서 '{channel_name}' 채널을 찾지 못했지만, **기본 채널(ID: {channel_id_int})**로 공지 알림을 성공적으로 보냈습니다.")
                    else: results.append(f"Success: '{channel_name}' 채널로 공지 알림을 성공적으로 보냈습니다.")
                
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        error_message = f"Error: 채널(ID: {channel_id})을 찾을 수 없습니다. (CSV 또는 .env의 ID가 유효한지 확인하세요)"
                    
                    elif e.response.status_code == 403:
                        error_message = f"Error: 해당 채널(ID: {channel_id})에 메시지를 보낼 권한이 없습니다. (봇 권한, 특히 'Send Messages' 및 'Mention Everyone' 권한을 확인하세요)"
                    
                    else:
                        error_message = f"Error: HTTP 오류 발생 (채널: {channel_name}, ID: {channel_id}): {e}"
                    print(error_message)
                    results.append(error_message)

                except Exception as e:
                    error_message = f"Error: 채널 공지 알림 전송 중 오류 발생 {e}"
                    print(error_message)
                    results.append(error_message)
        
        return "\n".join(results)


    
