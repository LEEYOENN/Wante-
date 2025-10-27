from langchain_core.tools.base import BaseTool
from typing import List,Dict,Optional
from langchain_core.tools import BaseTool
from langchain.agents.agent_toolkits.base import BaseToolkit
from google.oauth2.credentials import Credentials
from pydantic import Field
from lib.tools.google.tools import NewSpreadsheet, AppendSpreadSheet, UploadMSWordFile

class GoogleToolkit(BaseToolkit):
    """toolkit for google api Tools"""
    creds : Credentials = Field(..., description='credential object for tools')

    class Config:
        # Pydantic이 'Resource' 같은 비-Pydantic 타입을 허용하도록 설정
        arbitrary_types_allowed = True
    
    def get_tools(self) -> List[BaseTool]:
        return [
            AppendSpreadSheet(creds=self.creds),
            UploadMSWordFile(creds=self.creds)
        ]