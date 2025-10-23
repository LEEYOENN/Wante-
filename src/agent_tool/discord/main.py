import asyncio
from bot_runner import run_bot_in_background, global_client
from discord_alarm_toolkit.discord_toolkit import DiscordAlarmToolkit
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "./")))

load_dotenv()

async def main():
    # 1. 봇을 백그라운드에서 실행
    run_bot_in_background()

    # 2. 봇이 Discord에 연결 될 때까지 잠시 기다립니다.
    await asyncio.sleep(3)

    # 3. 툴을 생성하고 모델에 전달
    dm_toolkits = DiscordAlarmToolkit()
    tools = dm_toolkits.get_tools()

    print(tools)
    # --- 에이전트 실행 테스트 ---
    print("--- 툴 실행 테스트 시작 ---")

    # 툴의 _arun 메서드를 직접 호출하여 테스트합니다. (실제 에이전트는 이 부분을 대신호출)
    test_user_ids = ['1108003654344134686',]
    test_content = "포텐업 위키 링크 공유드립니다.\n링크:https://lean-mahogany-686.notion.site/POTENUP-WIKI-1e109c484bff80a3a6a9f5159d348537"

    results = await tools[0]._arun(test_user_ids, test_content)
    print("\n[DM 툴 실행 결과]")
    print(results)

    channel_id = os.getenv('DISCORD_NOTIFICATION_CHANNEL_ID')
    results = await tools[1]._arun(str(channel_id), test_content)
    print("\n[채널 툴 실행 결과]")
    print(results)

    print("--- 툴 실행 테스트 완료 ---")

    # 작업이 끝나면 봇을 종료
    await global_client.close()

if __name__ == "__main__":
    # 비동기 루프에서 main 실행
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"툴 실행 중 오류 발생: {e}")