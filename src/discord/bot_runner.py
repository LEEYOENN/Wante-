import discord
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# 1. 전역적으로 사용할 클라이언트 객체와 상태 변수 정의
# 이 객체 공유하는 더 안정적인 방법을 사용해야 함

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

global_client = discord.Client(intents=intents)
is_client_ready = asyncio.Event() # 봇 준비 완료를 알리는 비동기 객체

@global_client.event
async def on_ready():
    """봇이 준비되면 이벤트 플래그를 설정합니다."""
    print(f"Tool-Bot Logged in as {global_client.user}. Client is ready.")

    is_client_ready.set()

def run_bot_in_background():
    """봇을 별도의 태스크로 실행하는 함수입니다."""
    try:
        # main.py의 asyncio.run()에 의해 시작된 현재 루프를 가져옵니다.
        loop = asyncio.get_running_loop()

        # .run() 대신 .start() 비동기 코루틴을 테스크로 등록합니다.
        loop.create_task(global_client.start(DISCORD_BOT_TOKEN))
        print("봇 시작 테스크를 이벤트 루프에 등록했습니다.")
    
    except RuntimeError as e:
        print(f"오류: {e} 봇을 시작하려면 main.py의 asyncio.run() 내부에서 호출해야합니다.")
    except Exception as e:
        print(f"봇 실행 중 오류 발생: {e}")
        

#run_bot_in_background() #함수를 에이전트 시작 시 호출하게 됩니다.
# -----------------------------------------------------------------