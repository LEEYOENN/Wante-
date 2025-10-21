import asyncio
from bot_runner import run_bot_in_background, global_client
from discord_alarm_toolkit.dm_toolkit import DMAlarmTool
from discord_alarm_toolkit import dm_toolkit

async def main():
    # 1. 봇을 백그라운드에서 실행
    run_bot_in_background()

    # 2. 봇이 Discord에 연결 될 때까지 잠시 기다립니다.
    await asyncio.sleep(3)

    # 3. 툴을 생성하고 모델에 전달
    dm_toolkits = DMAlarmTool()
    tools = dm_toolkits.get_tools()

    print(tools)
    # --- 에이전트 실행 테스트 ---
    print("--- 툴 실행 테스트 시작 ---")

    # 툴의 _arun 메서드를 직접 호출하여 테스트합니다. (실제 에이전트는 이 부분을 대신호출)
    test_user_ids = ['881770934262976572', '1108003654344134686']
    test_content = "10월 발표자료 구글 드라이브에 업로드 부탁드립니다.\n팀원들에게 전달 부탁드립니다."

    results = await tools[0]._arun(test_user_ids, test_content)
    print("\n[DM 툴 실행 결과]")
    print(results)

    # 작업이 끝나면 봇을 종료
    await global_client.close()

if __name__ == "__main__":
    # 비동기 루프에서 main 실행
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"툴 실행 중 오류 발생: {e}")