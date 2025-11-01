from typing import List, Type, Dict, ClassVar
from datetime import datetime
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import pandas as pd
import os, sys
from pathlib import Path
from google.oauth2.credentials import Credentials
import textwrap

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from utils.google_utils.google_util import spreadsheet_to_dataframe, GResult, MimeType, mkfile, auth

current_path = Path(__file__).resolve()
PROJECT_ROOT = current_path.parent.parent.parent.parent
CREDENTIALS_FILE_PATH = PROJECT_ROOT / 'credentials.json'
print(CREDENTIALS_FILE_PATH)

# 오늘 스케줄 Json 데이터로 가져오기
class getFormattedDailySchedule(BaseTool):
    """오늘의 스케줄, 프리핑 내용을 '알림용 메시지'로 포맷팅하여 가져올 때 사용합니다."""
    name: str = "get_formatted_daily_schedule_for_discord_alarm"
    description: str = "Gets today's schedule, and formatted as a JSON payload for discord channel alarm tool."

    # 도구 초기화 시 필요한 객체
    creds: Credentials = Field(description="Google API Credentials")

    # 상수
    DATE_COLUMN_NAME: ClassVar[str] = "날짜"
    TASK_COLUMN_NAME: ClassVar[str] = "내용"
    TASK_DETAIL_COLUMN_NAME: ClassVar[str] = "세부내용"
    ALARM_CHANNEL_NAME: ClassVar[str] = "알림채널"

    def _run(self) -> Dict[List[str], List[str]]:
        try:
            month = str(datetime.now().month)
            SCHEDULE_FILE_PATH = f"wantedash/포텐업_스케줄"
            SCHEDULE_SHEET_NAME = f"{month}월_스케줄"

            # 스케줄 파일을 찾기
            file_result = mkfile(self.creds, SCHEDULE_FILE_PATH, MimeType.spreadsheet)
            if not file_result.id:
                return {"error": "스케줄 파일을 찾거나 생성할 수 없습니다."}
            
            # spread sheet를 dataframe 형식으로 변환
            schedule = spreadsheet_to_dataframe(self.creds, file_result.id, SCHEDULE_SHEET_NAME)
            if schedule.empty:
                return {"error": "스케줄 파일을 불러오는 데 실패했습니다."}
            
            today_date = datetime.now().date()

            # Google sheets 에서 가져온 '날짜' 컬럼 전체를 날짜 객체로 변환.
            try:
                schedule[self.DATE_COLUMN_NAME] = pd.to_datetime(
                    schedule[self.DATE_COLUMN_NAME], format='%Y/%m/%d'
                ).dt.date
            except ValueError:
                # 위 format이 실패할 경우 판다스가 알아서 추측하도록
                schedule[self.DATE_COLUMN_NAME] = pd.to_datetime(
                    schedule[self.DATE_COLUMN_NAME]
                ).dt.date
            
            # 오늘 있을 스케줄을 찾기
            today_task = schedule[schedule[self.DATE_COLUMN_NAME] == today_date]

            if today_task.empty:
                message = {"channel_names": [], "contents": []}
                return message
            else:
                channels = []
                messages = []

                # 오늘 스케줄을 모두 알림 메시지로 변환
                for _, row in today_task.iterrows():
                    channels.append(str(row[self.ALARM_CHANNEL_NAME]).strip())

                    task_title = str(row[self.TASK_COLUMN_NAME]).strip()
                    task_detail = ""
                    
                    if self.TASK_DETAIL_COLUMN_NAME in row and  pd.notna(row[self.TASK_DETAIL_COLUMN_NAME]):
                        task_detail = str(row[self.TASK_DETAIL_COLUMN_NAME]).strip()

                    message_lines = [f"## {today_date.strftime('%Y-%m-%d')} 오늘 일정 알림"]
                    message_lines.append(f"\n- **{task_title}**")
                    if task_detail:
                        message_lines.append(f"\n {task_detail}")

                    full_message = "\n".join(message_lines)

                    messages.append(full_message)
                
                result = {"channel_names": channels, "contents": messages}
                return result
        
        except Exception as e:
            return {"error": f"스케줄 데이터로 생성 중 오류 발생: {e}"}
    
# 보고서 미제출 DM 발송 목록 가져오기
class GetUnsubmitReportTargets(BaseTool):
    """discord dm_alarm_tools 도구의 입력값으로 바로 사용할 수 있는 Json 객체를 반환합니다."""
    name: str = "get_unsubmit_report_targets"
    description: str = "Gets a users who missed project reports, and formatted as a JSON payload for a discord dm alarm tool."

    creds: Credentials = Field(description="Google API Credentials")

    # 상수
    REPORT_STATUS_COLUMN_NAME: ClassVar[str] = "프로젝트보고서 제출여부"
    TARGET_MEMBER_COLUMN_NAME: ClassVar[List[str]] = ["팀원1", "팀원2", "팀원3"]

    def _run(self) -> Dict[List[str], str]:
        try:

            month = str(datetime.now().month)
            PROJECT_MANAGEMENT_FILE_PATH = f"wantedash/포텐업_프로젝트_관리"
            PROJECT_MANAGEMENT_SHEET_NAME = f"{month}월_프로젝트_관리"

            file_result = mkfile(self.creds, PROJECT_MANAGEMENT_FILE_PATH, MimeType.spreadsheet)
            if not file_result.id:
                return {"error": "스케줄 파일을 찾거나 생성할 수 없습니다."}
            
            # spread sheet를 dataframe 형식으로 변환
            project_management = spreadsheet_to_dataframe(self.creds, file_result.id, PROJECT_MANAGEMENT_SHEET_NAME)
            if project_management.empty:
                return {"error": "스케줄 파일을 데이터 프레임으로 불러오는 데 실패했습니다."}
            
            # 보고서를 제출하지 않은 팀 데이터를 찾기
            unsubmitted_team = project_management[project_management[self.REPORT_STATUS_COLUMN_NAME] == ""]
            
            if unsubmitted_team.empty:
                return {"user_names": [], "content": ""}

            else:
                target_members = []
                for _, row in unsubmitted_team.iterrows():
                    for member in self.TARGET_MEMBER_COLUMN_NAME:
                        if row[member]:
                            target_members.append(row[member])

                message = textwrap.dedent(f"""
                📋 **{month}월 프로젝트 보고서 미제출 안내**

                안녕하세요! 👋
                {month}월 프로젝트 보고서가 아직 제출되지 않았습니다.

                ⏰ 빠른 시일 내에 제출 부탁드립니다.

                궁금한 점이 있으시면 언제든 연락주세요! 😊
                """)
                result = {"user_names": target_members, "content": message}
                return result
        
        except Exception as e:
            return {"error": f"보고서 미제출 목록 생성 중 오류 발생: {e}"}




# # --- 실행 코드 ---
# if __name__ == "__main__":
#     print("Google API 인증을 시작합니다...")
#     try:
#         # 1. Google 인증 (google_util.py의 auth 함수 사용)
#         # credentials.json 파일이 같은 위치에 있어야 함
#         creds = auth(CREDENTIALS_FILE_PATH)
#         print("인증 성공!")

#         # 2. 'getFormattedDailySchedule' 툴 테스트
#         print("\n--- 1. 스케줄 알림 툴 테스트 ---")
#         schedule_tool = getFormattedDailySchedule(creds=creds)
#         schedule_result = schedule_tool._run()
#         print("결과:", schedule_result)

#         # 3. 'GetUnsubmitReportTargets' 툴 테스트
#         print("\n--- 2. 보고서 미제출 툴 테스트 ---")
#         report_tool = GetUnsubmitReportTargets(creds=creds)
#         report_result = report_tool._run()
#         print("결과:", report_result)

#     except Exception as e:
#         print(f"\n[오류] 테스트 실행 중 오류 발생: {e}")