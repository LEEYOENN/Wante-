from langchain_core.tools.base import BaseTool
from typing import List
from langchain_core.tools import BaseTool
from langchain.agents.agent_toolkits.base import BaseToolkit
from google.oauth2.credentials import Credentials
from pydantic import Field
from .spread_sheets_tools import getFormattedDailySchedule, GetUnsubmitReportTargets

class SpreadSheetsToolkit(BaseToolkit):
    """toolkit for read spreadsheets and return formatted data for discord alarm tools"""
    creds: Credentials = Field(description="Google API Credentials")

    class Config:
        # Pydantic이 'Resource' 같은 비-Pydantic 타입을 허용하도록 설정
        arbitrary_types_allowed = True
    
    def get_tools(self) -> List[BaseTool]:
        return [
            getFormattedDailySchedule(creds=self.creds),
            GetUnsubmitReportTargets(creds=self.creds)
        ]