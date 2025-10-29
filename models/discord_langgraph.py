from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import Annotated, TypedDict, Literal, List
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt.tool_node import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage
import operator
from langgraph.checkpoint.memory import MemorySaver
import sys
import os
from pathlib import Path
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableConfig
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from lib.discord.discord_toolkit import DiscordAlarmToolkit
from lib.spread_sheets.spread_sheets_toolkit import SpreadSheetsToolkit
from src.utils.google_utils.google_util import auth

current_path = Path(__file__).resolve()
PROJECT_ROOT = current_path.parent.parent
CREDENTIALS_FILE_PATH = PROJECT_ROOT / 'credentials.json'
print(CREDENTIALS_FILE_PATH)

def get_discord_langgraph() -> CompiledStateGraph:

    # 노드가 주고받을 상태(State) 정의
    class State(TypedDict):
        # 모델 입출력
        messages: Annotated[List[BaseMessage], operator.add]

        # 현재 그래프가 진행중인 단계
        status: Literal["acting", "done"]

    # 도구 세팅
    discord_toolkit = DiscordAlarmToolkit()
    discord_tools = discord_toolkit.get_tools()

    spread_sheets_toolkit = SpreadSheetsToolkit(creds=auth(CREDENTIALS_FILE_PATH))
    spread_sheets_tools = spread_sheets_toolkit.get_tools()

    tools = discord_tools + spread_sheets_tools
    # 모델 세팅

    llm_agent = ChatOpenAI(
    model='gpt-4o',
    temperature=0
    )

    agent_chatbot = llm_agent.bind_tools(tools=tools)

    # 메모리 생성
    memory = MemorySaver()

    ## 그래프에 필요한 노드 생성

    # 에이전트 노드
    agent_system = """
    당신은 사용자의 요청에 따라 Google Sheets 조회 후 데이터 포매팅 및 Discord 알림을 전송 하는 AI 어시스턴트입니다.

    당신의 임무는 사용자의 요구사항을 분석하고, 다음 두 단계에 따라 행동하는 것입니다.

    [1단계: 데이터 수집(필요한 경우만)]
    - 사용자가 "오늘 스케줄", "보고서 미제출" 등 데이터 조회가 필요한 요청을 하면,
    먼저 'get_formatted_daily_schedule' 또는 'get_unsubmit_report_targets' 도구를 호출해야 합니다.
    - 이 도구들은 Discord 알림에 필요한 JSON(데이터)를 반환합니다.

    [2단계: 알림 전송]
    - (만약 1단계에서 데이터를 받아 온 경우) 1단계 도구가 반환한 JSON 데이터를 
    'discord_channel_alarm' 또는 'discord_dm_alarm' 도구의 입력으로 사용하여 알림을 전송해야 합니다.
    ** 단순하게 데이터 조회가 필요 없는 알림 요청만을 한다면, 1단계를 건너뛰고 바로 'discord_channel_alarm'
    또는 'discord_dm_alarm' 도구를 호출합니다.

    모든 작업이 완료 되었다면 최종 결과를 보고합니다.
    """
    
    async def agent_node(state: State) -> State:
        # 에이전트에 전달할 시스템 메시지
        system_message = SystemMessage(content=agent_system)

        # 시스템 메시지와 지금까지의 message를 합친 인풋
        messages_with_system_prompt = [system_message] + state['messages']

        # agent의 답변
        answer = await agent_chatbot.ainvoke(messages_with_system_prompt)
        
        # 상태 업데이트
        return {**state, "messages": [answer], 'status': "acting"}
    
    # 도구 노드
    tool_node = ToolNode(tools=tools)

    # 그래프 빌더 생성
    graph_builder = StateGraph(State)

    # 그래프에 노드 주입
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", tool_node)

    # 고정 엣지 추가
    graph_builder.add_edge(START, "agent")
    graph_builder.add_edge("tools", "agent")

    # 조건 분기 함수와 조건부 엣지 추가
    def route_agent(state: State) -> str:
        """
        agent 노드 이후 실행
        tool_calls가 마지막 메시지에 있으면 'tools'로 없으면 'END'로 라우팅
        """

        if state['messages'][-1].tool_calls:
            return 'tools'
        else:
            return END
        
    graph_builder.add_conditional_edges(
        "agent", route_agent, {'tools': 'tools', END: END}
    )

    graph = graph_builder.compile(checkpointer=memory)
    return graph

# if __name__ == "__main__":
#     graph = get_discord_langgraph()
#     print(graph)


