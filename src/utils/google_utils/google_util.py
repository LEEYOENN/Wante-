import os, gspread
import pandas as pd
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Literal
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
## 인증 처리
def auth(credentials_file:str) -> Credentials:
    """Authentication processing and saving token file to local folder"""
    creds : Credentials | None = None
    # creds: Optional[Credentials] = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # 유효한 인증 정보가 없으면, 사용자에게 로그인을 요청
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        # 다음 실행을 위해 인증 정보를 저장합니다.
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

def spreadsheet_to_dataframe(creds:Credentials, spreadsheet_id, sheet_name):
    """
    스프레드시트의 데이터 읽어 DataFrame 생성
    """
    df = pd.DataFrame()
    try:
        # service = build("sheets", "v4", credentials=creds)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
    except HttpError as error:
        print(f"an error occured: {error}")
        ## if exception, empty dataframe
    return df

class MimeType(Enum):
    all = 'all'
    spreadsheet =   'application/vnd.google-apps.spreadsheet'  # Google Sheets
    folder =        'application/vnd.google-apps.folder'       # Google Drive Folder
    document =      'application/vnd.google-apps.document'     # Google Docs
    presentation =  'application/vnd.google-apps.presentation' # Google Slides
    ms_excel =      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' # xlsx file
    ms_excel_old =  'application/vnd.ms-excel'                 #xls file
    
def query(mtype:MimeType, name: str, folder_id: str | None = None) -> str:
    if mtype == MimeType.all:
        mime_type = ' or mimeType='.join([f"'{mtype.value}'" for mtype in MimeType if mtype != MimeType.all])
        query = f"name = '{name}' and " + \
            f" ( mimeType={mime_type} )"
    else:
        query = f"name = '{name}'" + \
            f" and mimeType='{mtype.value}'"
    if folder_id:
        query = query + f" and '{folder_id}' in parents"
    query = query + f" and trashed = false"
    print(f"검색 쿼리: {query}")
    return query

GRESULT_TYPE = Literal["success", "fail", "exception", "error"]
class GResult(BaseModel):
    result : GRESULT_TYPE = Field(...,description='api doing result')
    message : str = Field(...,description='result message')
    id : str | None = Field(default=None, description='file or folder id')
    file : str | None = Field(default=None, description='file name(path?)')
    link : str | None = Field(default=None, description='web link of file or folder')    

def api_result(
        title : str, ## 호출시 출력 구분
        result:GRESULT_TYPE, message:str, 
        id:str|None=None,file:str|None=None,link:str|None=None
    ):
    print(f'Result : {result}, {message}, {id}, {file}, {link}')
    return GResult(
        result = result,
        message = message,
        id = id,
        file = file,
        link = link
    )

def append_datas_to_spreadsheet(
    creds: Credentials, spreadsheet_id: str, sheet_name: str, csv_string: str
) -> GResult:
    """
    Checks if a specific sheet exists, creates it if it doesn't exist, and then adds data to it.
    csv_string format is csv string
    """
    datas = [csv_string.split(',')]
    print(f"데이터 : {datas}\n - ({csv_string})")
    try:
        sheet_service = build("sheets", "v4", credentials=creds)
        # 1. check sheet_name
        sheet_metadata = sheet_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get('sheets', '')
        sheet_exists = False
        for sheet in sheets:
            if sheet.get("properties", {}).get("title", "") == sheet_name:
                sheet_exists = True
                break
        # 2. if not sheet, add new sheet
        if not sheet_exists:
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }]
            }
            sheet_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()
            print(f"시트 추가 '{sheet_name}'")
        # 3. append data from last rows
        body = {'values': datas}
        result = sheet_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
        return api_result('append_datas_to_spreadsheet','success',
                    f"데이터 추가 완료 : {result.get('updates').get('updatedCells')}",
                    spreadsheet_id
                )
    except HttpError as error:
        return api_result('append_datas_to_spreadsheet','error',
                    'Error creating spreadsheet file : {error}',
                    spreadsheet_id
                )

def find(creds : Credentials, name: str, mtype: MimeType, folder_id: str | None = None) -> GResult:
    """
    파일 혹은 폴더 명을 받아 ID 찾기
    """
    _query = query(name=name,mtype=mtype, folder_id=folder_id)
    print(f"\n[툴 실행] 검색 쿼리: {_query}")
    try:
        service = build("drive", "v3", credentials=creds)
        results = service.files().list(
            q=_query,
            pageSize=1, # 일치하는 하나만 찾아오기
            fields="files(id, name, webViewLink, mimeType)"
        ).execute()
        items = results.get('files', [])
        if not items:
            return api_result('find','success',
                    f"파일 없음 : {name}",
                )
        item = items[0]
        return api_result('find','success',
                    f"파일: {item['name']}, id: {item['id']}, type: {item['mimeType']}, link: {item['webViewLink']}",
                    item['id'],
                    item['name'],
                    item['webViewLink']
                )
    except HttpError as error:
        return api_result('find','error',
                    f"API 오류 발생 : {error}",
                )
    except Exception as e:
        return api_result('find','error',
                    f"알 수 없는 오류 발생 : {e}",
                )

def gnew(creds : Credentials, name: str, mtype: MimeType, folder_id: str | None = None) -> GResult:
    """
    파일 혹은 폴더 생성
    """
    # _query = query(name=name,mtype=mtype, folder_id=folder_id)
    file_metadata = {
        'name': name,
        'mimeType': mtype.value,
        # 'parents'를 지정하지 않으면 root에 생성됩니다.
        'parents': [folder_id if folder_id else 'root'] 
    }
    print(f"\n[툴 실행] 생성 쿼리: {file_metadata}")
    try:
        service = build("drive", "v3", credentials=creds)
        results = service.files().create(
            body=file_metadata,
            fields='id, name, webViewLink'
        ).execute()
        name = results.get('name')
        id = results.get('id')
        link = results.get('webViewLink')
        print(f"New File/Folder : {name}\nID: {id}")
        return api_result('gnew','success',
                    f"{'폴더' if mtype == MimeType.folder else '파일'} 생성 완료 : {name} / {id} / {link}",
                    id, name, link
                )
    except HttpError as error:
        return api_result(
            'gnew','error',
            f'API 오류 발생 : {error}'
        )
    except Exception as e:
        return api_result(
            'gnew','error',
            f'알 수 없는 오류 발생 : {e}'
        )

def mkdir(creds: Credentials, dir_path: str) -> GResult:
    """
    디렉토리 패스에 맞는 폴더 ID 찾아줌, 없으면 폴더 생성, 항상 root 기준으로 생성
    예) abc/ddd -> root -> abc -> ddd
    """
    dir_path = dir_path.strip()
    dirs = dir_path[1:].split('/') if dir_path.startswith('/') else dir_path.split('/')
    results = None
    parent_id = 'root'
    for path in dirs:
        path = path.strip()
        if path == '':
            continue
        # 1. 찾기
        results = find(creds=creds, name=path, mtype=MimeType.folder, folder_id=parent_id)
        # 2. 있으며 다음, 없으면 생성
        if results is None or results.id is None:
            results = gnew(creds,path,MimeType.folder,parent_id)
        # 3. parents 에 저장
        parent_id = results.id
    # 최종 폴더 ID 리턴
    return api_result(
        'mkdir','success',
        f'폴더 생성 완료 : {dir_path}',
        results.id if results else None,
        results.file if results else None,
        results.link if results else None
    )

def mkfile(creds: Credentials, file_path: str, mtype:MimeType) -> GResult:
    """
    패스에 맞는 파일 있으면 해당 파일 ID 리턴, 없으면 생성 후 ID 리턴
    """
    if mtype == MimeType.folder:
        return api_result(
            'mkfile','exception',
            f'mime type 타입 오류 : {mtype}',
            None, file_path
        )
    last_slash = file_path.rfind("/")
    folder_id = None
    if last_slash > 0:
        ## 폴더 생성 후 파일 생성
        results = mkdir(creds,file_path[:last_slash])
        folder_id = results.id if results.id else 'root'
    ## 파일 찾기
    results = find(creds, file_path[last_slash+1:], mtype, folder_id)
    ## 파일 생성
    if results is None or results.id is None:
        results = gnew(creds,file_path[last_slash+1:],mtype)
    return api_result(
        'mkfile','success',
        f'파일 생성 완료 : {results.file} / {results.id} / {results.link}',
        results.id, results.file, results.link
    )

def upload_msword(creds: Credentials, local_file_path: str, folder_path: str|None = None) -> GResult:
    """
    정해진 구글 드라이브의 폴더에 로컬 파일(ms 워드파일) 업로드
    """
    local_file_path = local_file_path.strip()
    folder_path = folder_path.strip() if folder_path else ''
    file_name = os.path.basename(local_file_path)
    file_name, file_ext = os.path.splitext(file_name)
    mtype =""
    if file_ext == "docx":
        mtype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif file_ext == "doc":
        mtype = 'application/msword'
    # .docx: application/vnd.openxmlformats-officedocument.wordprocessingml.document
    # .doc: application/msword
    try:
        service = build("drive", "v3", credentials=creds)
        # 파일 메타데이터 정의 (파일 이름)
        file_metadata = {
            'name': file_name # 파일의 이름 부분을 구글 생성 파일명으로 사용
            # 'parents': ['YOUR_FOLDER_ID'] # 특정 폴더에 넣으려면 주석 해제
        }
        if folder_path != "":
            results = mkdir(creds,folder_path)
            if results.id:
                file_metadata['parents'] = [results.id]
        # 업로드할 미디어(파일 본문) 정의
        media = MediaFileUpload(
            local_file_path,
            mimetype=mtype,
            resumable=True # 대용량 파일은 resumable=True 권장
        )
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()
        return api_result(
            'upload_msword','success',
            f"파일 업로드 완료 : {file.get('name')} / {file.get('id')} / {file.get('webViewLink')}",
            file.get('id'), file.get('id'), file.get('webViewLink')
        )
    except FileNotFoundError as error:
        return api_result(
            'upload_msword','error',
            f"오류 발생 : {error}"
        )
    except HttpError as e:
        return api_result(
            'upload_msword','error',
            f"API 오류 발생 : {e}"
        )