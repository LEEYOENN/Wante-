from typing import List
from langchain_core.tools import BaseTool
from langchain.agents.agent_toolkits.base import BaseToolkit
# 새로운 도구 추가
from .dm_tools import DMAlarmTool

class DmToolkit(BaseToolkit):
    """Discord 알림을 보내기 위한 툴킷입니다."""
    def get_tools(self) -> List[BaseTool]:
        return [DMAlarmTool()]
