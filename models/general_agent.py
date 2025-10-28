import os, sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.agents.output_parsers.tools import ToolAgentAction
from typing import List, Dict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from src.utils.google_utils.google_util import auth
from src.lib.google.google_drive_toolkit.google_toolkit import GoogleToolkit


current_path = Path(__file__).resolve()
PROJECT_ROOT = current_path.parent.parent
CREDENTIALS_FILE_PATH = PROJECT_ROOT / 'credentials.json'
print(CREDENTIALS_FILE_PATH)

class GeneralAgent:
    def __init__(self, creds, system_prompt) -> None:
        self.creds = creds
        self.stores : Dict[str, InMemoryChatMessageHistory] = {}
        print('****** make agent ******')
        self.agent_history = self.make_agent(system_prompt)
        print(self.agent_history)

    def make_agent(self,system_prompt):
        print('**** system prompt ****')
        print(system_prompt)
        ## 1. agent 만들기
        llm = ChatOpenAI(model='gpt-4.1-mini', temperature=0)
        prompt = ChatPromptTemplate.from_messages([
            ("system",system_prompt),
            ("placeholder", "{chat_history}"),
            ("human","{question}"),
            ("placeholder","{agent_scratchpad}")  ## Agent 사용 결과 처리용?
        ])
        # tool
        toolkit = GoogleToolkit(creds = auth(CREDENTIALS_FILE_PATH))
        google_tools = toolkit.get_tools()
        # agent
        agent = create_openai_tools_agent(
            llm = llm,
            tools = google_tools,
            prompt = prompt
        )
        ## executor
        executor = AgentExecutor(
            agent = agent,
            tools = google_tools,
            return_intermediate_steps=True,
            verbose = True
        )
        def get_store(session_id : str):
            if session_id not in self.stores:
                self.stores[session_id] = InMemoryChatMessageHistory()
            return self.stores[session_id]
        ## 3. 히스토리 매핑
        return RunnableWithMessageHistory(
            executor,
            lambda session_id: get_store(session_id),
            input_messages_key="question",
            history_messages_key="chat_history"
        )

    def reset_agent(self,system_prompt):
        print('****** reset agent ******')
        self.agent_history = self.make_agent(system_prompt)        
        print(self.agent_history)
    
    def chat(self, answer, config):
        print("*** agent chat ***")
        msg = {"question" : answer}
        print('** msg : ',msg)
        print('** config : ',config)
        print(self.agent_history)
        result = self.agent_history.invoke(
            input = msg,
            config= config,
        )
        print(result)
        print("*** agent chat ***")
        print('*** intermediate check', len(result['intermediate_steps']))
        if result['intermediate_steps'] and result['intermediate_steps'][0] \
            and isinstance(result['intermediate_steps'][0][0],ToolAgentAction):
            print('*** clean stores ')
            self.stores[config['configurable']['session_id']].messages = self.stores[config['configurable']['session_id']].messages[-3:]
        return result