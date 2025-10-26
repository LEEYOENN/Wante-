from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import Annotated, TypedDict, Literal, List
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt.tool_node import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage
import operator
from langgraph.checkpoint.memory import MemorySaver
from src.agent_tool.discord.discord_alarm_toolkit.discord_toolkit import DiscordAlarmToolkit
import sys
import os
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableConfig

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "./")))


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

    # 모델 세팅

    llm_agent = ChatOpenAI(
    model='gpt-4o',
    temperature=0
    )

    agent_chatbot = llm_agent.bind_tools(tools=discord_tools)

    # 메모리 생성
    memory = MemorySaver()

    ## 그래프에 필요한 노드 생성

    # 에이전트 노드
    agent_system = """
    당신은 사용자의 요청에 따라 Discord 알림을 전송하는 AI 어시스턴트입니다.
    당신의 임무는 사용자의 요구사항을 분석하여 '개인 DM 알림' 또는 '채널 전체 공지' 중 적절한 도구를 선택하고,
    도구 사용 시 필요한 모든 정보를 수집하여 도구를 호출하는 것입니다.
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
    tool_node = ToolNode(tools=discord_tools)

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

    graph = graph_builder.compile()
    return graph


