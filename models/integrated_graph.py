from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import Annotated, TypedDict, Literal, List
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt.tool_node import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
import sys, os
from pathlib import Path
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableConfig
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from src.lib.discord.discord_toolkit import DiscordAlarmToolkit
from src.lib.spread_sheets.spread_sheets_toolkit import SpreadSheetsToolkit
from src.utils.google_utils.google_util import auth
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "./")))
from prompts.alarm_system_prompt import ALARM_SYSTEM_PROMPT

class State(TypedDict):
    massages: Annotated[List[BaseMessage], add_messages]
    next: str

# 멤버 Agent 목록 정의
members = ["Alarm", "Submit", "RAG"]

# 다음 작업자 선택 옵션 목록 정의
options_for_next = ["FINISH"] + members

MODEL_NAME = "gpt-4.1-mini"

# 시스템 프롬프트 정의: 작업자 간의 대화를 관리하는 감독자 역할
system_prompt = (
    "You are a supervisor tasked with managing a conversation between the"
    " following workers:  {members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH."
)

# ChatPromptTemplate 생성
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        (
            "system",
            "Given the conversation above, who should act next? "
            "Or should we FINISH? Select one of: {options}",
        ),
    ]
).partial(options=str(options_for_next), members=", ".join(members))


# LLM 초기화
llm = ChatOpenAI(model=MODEL_NAME, temperature=0)


# Supervisor Agent 생성
def supervisor_agent(state):
    # 프롬프트와 LLM을 결합하여 체인 구성
    supervisor_chain = prompt | llm.with_structured_output(RouteResponse)
    # Agent 호출
    return supervisor_chain.invoke(state)


current_path = Path(__file__).resolve()
PROJECT_ROOT = current_path.parent.parent
CREDENTIALS_FILE_PATH = PROJECT_ROOT / 'credentials.json'
print(CREDENTIALS_FILE_PATH)

def get_discord_langgraph() -> CompiledStateGraph:

    # 노드가 주고받을 상태(State) 정의
    class State(TypedDict):
        # 모델 입출력
        messages: Annotated[List[BaseMessage], add_messages]

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
    async def agent_node(state: State) -> State:
        # 에이전트에 전달할 시스템 메시지
        system_message = SystemMessage(content=ALARM_SYSTEM_PROMPT)

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


