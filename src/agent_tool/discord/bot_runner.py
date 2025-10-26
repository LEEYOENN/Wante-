import discord
import os
import asyncio
import threading # 1. threading 모듈 추가
from dotenv import load_dotenv

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

global_client = discord.Client(intents=intents)
is_client_ready = asyncio.Event() # 봇 준비 완료 (FastAPI 메인 루프에서 생성됨)
main_loop = None # 2. FastAPI의 메인 루프를 저장할 변수

@global_client.event
async def on_ready():
    """봇이 준비되면 이벤트 플래그를 설정합니다."""
    print(f"Tool-Bot Logged in as {global_client.user}. Client is ready.")
    
    # 3. 봇의 스레드에서 FastAPI의 메인 루프로 "준비 완료" 신호를 보냄
    # .set()은 스레드에 안전하지 않으므로 call_soon_threadsafe 사용
    if main_loop:
        main_loop.call_soon_threadsafe(is_client_ready.set)

def _run_bot():
    """[스레드 타겟] 봇을 위한 새 이벤트 루프를 생성하고 실행합니다."""
    try:
        # 4. 봇 스레드 전용의 새 이벤트 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 5. .start()를 새 루프에서 끝날 때까지 실행
        loop.run_until_complete(global_client.start(DISCORD_BOT_TOKEN))
    except Exception as e:
        print(f"봇 스레드에서 오류 발생: {e}")
    finally:
        if loop.is_running():
            loop.run_until_complete(global_client.close())
        loop.close()
        print("봇 스레드 및 이벤트 루프 종료.")

def run_bot_in_background():
    """봇을 별도의 데몬 스레드로 실행하는 함수입니다."""
    global main_loop
    try:
        # 6. 현재 실행 중인 메인(FastAPI/Uvicorn) 루프를 저장
        main_loop = asyncio.get_running_loop()
        
        # 7. 별도 스레드를 생성하고 _run_bot 함수를 타겟으로 지정
        bot_thread = threading.Thread(target=_run_bot, daemon=True)
        bot_thread.start()
        print("봇 시작 스레드를 등록했습니다.")
    
    except RuntimeError as e:
        print(f"오류: {e}")
    except Exception as e:
        print(f"봇 실행 중 오류 발생: {e}")
# import discord
# import os
# import asyncio
# from dotenv import load_dotenv

# load_dotenv()
# DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# # 1. 전역적으로 사용할 클라이언트 객체와 상태 변수 정의
# # 이 객체 공유하는 더 안정적인 방법을 사용해야 함

# intents = discord.Intents.default()
# intents.members = True
# intents.message_content = True

# global_client = discord.Client(intents=intents)
# is_client_ready = asyncio.Event() # 봇 준비 완료를 알리는 비동기 객체

# @global_client.event
# async def on_ready():
#     """봇이 준비되면 이벤트 플래그를 설정합니다."""
#     print(f"Tool-Bot Logged in as {global_client.user}. Client is ready.")

#     is_client_ready.set()

# def run_bot_in_background():
#     """봇을 별도의 태스크로 실행하는 함수입니다."""
#     try:
#         # main.py의 asyncio.run()에 의해 시작된 현재 루프를 가져옵니다.
#         loop = asyncio.get_running_loop()

#         # .run() 대신 .start() 비동기 코루틴을 테스크로 등록합니다.
#         loop.create_task(global_client.start(DISCORD_BOT_TOKEN))
#         print("봇 시작 테스크를 이벤트 루프에 등록했습니다.")
    
#     except RuntimeError as e:
#         print(f"오류: {e} 봇을 시작하려면 main.py의 asyncio.run() 내부에서 호출해야합니다.")
#     except Exception as e:
#         print(f"봇 실행 중 오류 발생: {e}")
        

# if __name__ == "__main__":
#     # ✅ 수정: async 함수로 래핑하거나 직접 봇을 실행
#     async def main():
#         await global_client.start(DISCORD_BOT_TOKEN)
    
#     asyncio.run(main())