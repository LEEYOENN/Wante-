from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Type, Literal
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from lib.google_util import (
    MimeType, GResult,
    find, spreadsheet_to_dataframe, query, gnew,
    mkdir, mkfile, append_datas_to_spreadsheet, upload_msword
)

def tool_result(result : GResult):
    return (
        f" RESULT = {result.result}\n"
        f" MESSAGE = {result.message}\n"
        f" ID = {result.id}\n"
        f" NAME = {result.file}\n"
        f" LINK = {result.link}"
        )

class PathData(BaseModel):
    """google api new spreadsheet tool : file name"""
    path_name: str =  Field(..., description="file or folder path, ex)/wantedash/study/스터디")

class NewSpreadsheet(BaseTool):
    """
    Create a new spreadsheet file in the specified folder
    path_name : str, /wantedash/study/스터디 = /wantedash/stdy 폴더에 스터디 스프레드시트 파일 생성
    """
    name: str = "new_spreadsheet"
    description: str = "A tool to find file or folder."
    args_schema: Type[BaseModel] = PathData
    ## auth
    creds : Credentials = Field(description='credential object for google api')

    def _run(self, path_name: str) -> str:
        results = mkfile(self.creds, path_name, MimeType.spreadsheet)
        return tool_result(results)
        # if results.id:
        #     return f"FILE_ID : {spread_id}"
        # else:
        #     return "알 수 없는 오류 발생 : 생성 실패"

class SheetData(BaseModel):
    """google api add csv data to spreadsheet tool : file name, csv data"""
    path_name: str =  Field(..., description="spreadsheet file path, ex)/wantedash/study/스터디")
    sheet_name: str = Field(..., description="sheet name to add csv data to")
    csv_string: str = Field(..., description="csv format data to add to spreadsheet, ex)이름,과정,전화번호")
class AppendSpreadSheet(BaseTool):
    """Add a single line of CSV data into a spreadsheet"""
    name: str = "append_csvstring_to_spreadsheet"
    description: str = "A tool to find file or folder."
    args_schema: Type[BaseModel] = SheetData
    ## auth
    creds : Credentials = Field(description='credential object for google api')
    
    def _run(self, path_name: str, sheet_name: str, csv_string: str) -> str:
        ## search spreadsheet file
        results = mkfile(self.creds,path_name,MimeType.spreadsheet)
        ## append csv_string to spreadsheet
        results = append_datas_to_spreadsheet(self.creds, results.id, sheet_name, csv_string)
        return tool_result(results)

class UploadData(BaseModel):
    """local MS Word files path, google drive folder path"""
    local_path: str =  Field(..., description="MSWord local file path, extension docx, doc")
    drive_path: str = Field(..., description="Google Drive path to upload")
class UploadMSWordFile(BaseTool):
    """Upload local MS Word files to Google Drive, File extension docx, doc"""
    name: str = "upload_msword_to_drive"
    description: str = "A tool to find file or folder."
    args_schema: Type[BaseModel] = UploadData
    ## auth
    creds : Credentials = Field(description='credential object for google api')
    
    def _run(self, local_path: str, drive_path: str) -> str:
        ## upload
        results = upload_msword(self.creds,local_path, drive_path)
        return tool_result(results)
