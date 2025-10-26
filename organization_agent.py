import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from organization_tools import (
    get_chat_logs,
    analyze_log_trends,
    save_report_to_markdown,
)

# Preparing the environment and tools
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    print("[error] OPENAI_API_KEY is not in .env file.")
    exit()

# List of tools to be used by agents
tools = [get_chat_logs, analyze_log_trends, save_report_to_markdown]
# LangGraph's ToolNode receives a list of @tool functions.
tool_node = ToolNode(tools)


# Agent state definition
class AgentState(TypedDict):
    # 'messages' is the agent's conversation history (memory)
    messages: Annotated[list, add_messages]


# Agent Graph definition
def create_organization_agent():
    print("--- Initialize 'Organization ai agent' ---")

    # LLM definition
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    # Binding tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # Graph Node definition

    # [NODE 1. Call LLM]
    def agent_node(state: AgentState):
        """Call LLM to decide what to do next (call tool or respond to user)"""
        print("--- Node: agent_node (Call LLM) ---")

        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    # Graph assembly
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # Edges settings
    workflow.set_entry_point("agent")

    # [Conditional edge] Check if LLM's response (agent_node) contains 'tool call'
    workflow.add_conditional_edges("agent", tools_condition)

    # The 'tools' node always return to the 'agent' node after completing its work and reports the results.
    workflow.add_edge("tools", "agent")

    # Compiled
    organization_agent = workflow.compile()
    print("'Organization ai agent' Compilation complete.")
    return organization_agent


# Running the main agent
if __name__ == "__main__":

    agent = create_organization_agent()

    # 'Goals' (prompts) to be given to agents
    today = datetime.now().strftime("%Y-%m-%d")
    task = f"""
    Retrieve all logs from the last seven days from 'chat_logs.db', analyze trends, and save the results to a file named '{today}_weekly_report.md'.
    """

    print(f"\n--- [Goal delivery] ---\n{task}\n----------------------")

    # Run agent
    # SystemMassage defines the agent's identity/persona
    initial_messages = [
        SystemMessage(
            content="""#You must write the report in Korean.
         You are the 'Organization AI Agent' analyzing the logs of 'WanteDash'.
         To accomplish the Supervisor's objectives, you must perform the following steps in order, and only once each.
         **[Task Sequence]**
         1. Call the get_chat_logs tool to retrieve logs for the requested period.
         2. Call the analyze_log_trends tool to analyze the logs received in step 1.
         3. Call the save_report_to_markdown tool to save the analysis results received in step 2 to a file.
         **[Termination Condition]**
         If the save_report_to_markdown tool returns the message Report saved successfully...", your task is perfectly complete. After this, **never, under any circumstances, call any tool again.**
         Your sole and final task is to respond to the user with just one line: "All tasks completed."
        """
        ),
        HumanMessage(content=task),
    ]

    events = agent.stream(
        {"messages": initial_messages}, config={"recursion_limit": 10}
    )

    for event in events:
        if "messages" in event:
            event["messages"][-1].pretty_print()
