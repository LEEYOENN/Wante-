from google.oauth2.credentials import Credentials
from utils.google_utils.google_util import auth, spreadsheet_to_dataframe
from dotenv import load_dotenv
import os

load_dotenv()

job_prompt_template = """
### {title}
* **필수 정보 (사용자 제공 {user_inputs_len}개):**
    {user_inputs}
* **수행 작업 (시트 기록):**
    * `path_name`: '{folder_name}/{file_name}'
    * `sheet_name`: '{sheet_name}'
    * `csv_string`: `[{csv_string}]` (CSV 형식 문자열로 변환)
"""
job_prompt_template_and_upload = """
### {title}
* **필수 정보 (사용자 제공 {total_len}개):**
    {user_inputs}
    {total_len}.  **로컬 파일 패스** (업로드 할 MS 워드 로컬 파일을 파일선택 기능을 이용하여 업로드하세요)
* **수행 작업 1 (파일 업로드):**
    * `local_path`: [{total_len}번 항목으로 전달받은 경로]
    * `driver_path`: '{folder_name}/temp'
    * `upload_msword_to_drive` 툴에서 반환된 **'업로드 링크'**를 변수에 저장합니다.
* **수행 작업 2 (시트 기록):**
    * **[에이전트 처리 정보 생성]**
        1.  **제출 서류 구글 드라이브 링크**: `수행 작업 1`에서 저장한 '업로드 링크'
    * **[시트 기록 실행]**
        * `path_name`: '{folder_name}/{file_name}'
        * `sheet_name`: '{sheet_name}'
        * `csv_string`: `[{csv_string}]` `[1 ~ {user_inputs_len}번 항목], [생성된 링크]` (총 {total_len}개 항목을 CSV 형식 문자열로 변환)
"""

def make_prompt(creds:Credentials):
    ## 설정 파일 ID
    ## .env 파일 ID 사용
    spreadsheet_id = os.getenv('STANDARD_INFO_SPREADSHEET_ID')
    worksheet_name = 'code'
    df = spreadsheet_to_dataframe(creds,spreadsheet_id,worksheet_name)
    job_titles = []
    job_prompts = []
    for idx in range(len(df)):
        title = df.loc[idx,'업무']
        job_titles.append(f'**{chr(idx+65)}.{title}**')
        user_inputs = df.loc[idx,'항목'].split(',')
        folder_name = df.loc[idx,'폴더']
        file_name = df.loc[idx,'파일']
        sheet_name = df.loc[idx,'시트']
        is_upload = df.loc[idx,'파일첨부']
        csv_string = ",".join([f"'{item}'" for i,item in enumerate(user_inputs)])

        params = {
            'title': f"{chr(idx+65)}. [{title}]",
            'user_inputs': "\n    ".join([f'{i+1}. {item}' for i,item in enumerate(user_inputs)]),
            'user_inputs_len': len(user_inputs),
            'total_len': len(user_inputs) + 1,
            'folder_name': folder_name,
            'file_name':file_name,
            'sheet_name': sheet_name,
            'csv_string': csv_string
        }
        
        if is_upload == 'Y':
            prompt_template = job_prompt_template_and_upload
        else:
            prompt_template = job_prompt_template
        job_prompts.append(prompt_template.format(**params))
    return {
        'job_titles':' , '.join(job_titles),
        'job_prompt':'\n---\n'.join(job_prompts)
    }