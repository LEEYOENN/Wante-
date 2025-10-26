import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt.chat_agent_executor import create_tool_calling_executor
from langchain_core.messages import SystemMessage
from langchain_tavily import TavilySearch


def format_docs(docs):
    """Converts the searched document into a prompt string."""
    context_str = ""
    for doc in docs:
        doc_type = doc.metadata.get("type", "text")
        context_str += f"--- [참고 자료 (Type: {doc_type}, Page: {doc.metadata.get('page')})] ---\n"
        context_str += doc.page_content + "\n\n"
    return context_str.strip()


# Tool 1. Router Chain
def create_router_chain(llm: ChatOpenAI):
    """Create a Router Tool that categorizes the question intent into three categories."""
    router_prompt = ChatPromptTemplate.from_template(
        """당신은 사용자의 질문 의도를 3가지 중 하나로 분류하는 '교통 경찰'입니다.
        오직 'rag', 'counseling', 'chit_chat' 중 하나만 반환해야 합니다.

        [분류 기준]
        1. rag: '국민내일배움카드', '운영규정', 'FAQ', '결석', '증빙 서류', '페널티', '환급' 등 구체적인 규정이나 사실에 대한 질문.
        2. counseling: '취업', '진로', '커리어', '업계 동향', '면접 준비', '이력서' 등 조언이나 상담이 필요한 '커리어 코칭' 질문.
        3. chit_chat: '안녕', 'ㅋㅋㅋㅋ', '고마워', '날씨 어때' 등 (1)과 (2)에 해당하지 않는 모든 '일상 대화' 및 잡담.

        [사용자 질문]
        {question}

        [분류] (rag, counseling, chit_chat 중 하나만 출력):"""
    )
    return router_prompt | llm | StrOutputParser()


# Tool 2. RAG Answer Chain
def create_rag_chain(llm: ChatOpenAI):
    """Create 'a RAG Tool' that takea 'context' and 'question' and generates 'a prescriptive answer'."""
    rag_prompt = ChatPromptTemplate.from_template(
        """당신은 '국민내일배움카드 운영규정' 및 '교육장 FAQ' 전문가인 친절한 상담 에이전트입니다.
        제공된 '참고 문서(context)'만을 사용하여 사용자 질문에 상세하고 정확하게 답변하세요.

        [참고 문서]
        {context}

        [사용자 질문]
        {question}

        [답변] (참고 문서에 답이 없으면 "참고 문서에 해당 정보가 없습니다. 운영진에게 문의하시기 바랍니다."라고 답변):"""
    )
    rag_answer_chain = (
        {
            "context": RunnableLambda(lambda x: format_docs(x["context"])),
            "question": RunnableLambda(lambda x: x["question"]),
        }
        | rag_prompt
        | llm
        | StrOutputParser()
    )
    return rag_answer_chain


# Tool 3. Career Counseling Chain
def create_counseling_chain(llm: ChatOpenAI):
    """Create 'a Consulting Tool' that receives 'a question' and generates 'a Career Coach Answer'.
    This tool is an agent (create_tool_calling_executor) that uses the Tavily search tool.
    """
    # Tool definition
    tavily_tool = TavilySearch(max_results=3)

    # List of tools for agents to use
    tools = [tavily_tool]

    # Persona definition
    system_prompt = """당신은 교육생들의 진로와 취업 고민을 들어주는 따뜻하고 전문적인 '커리어 코치'입니다.
- 사용자의 질문에 공감하며 전문적인 조언을 제공하세요.
- '취업 동향', '전망', '최신 기술' 등 실시간 정보가 필요한 경우, 반드시 'tavily_search' 도구를 사용하여 최신 정보를 검색하고 그 결과를 바탕으로 답변해야 합니다.
- 그 외의 대화나 간단한 조언은 당신의 지식으로 답하세요."""

    llm_with_tools = llm.bind_tools(tools)

    counseling_agent_executor = create_tool_calling_executor(llm_with_tools, tools)
    return counseling_agent_executor


# Tool 4. Chit-Chat Chain
def create_chit_chat_chain(llm: ChatOpenAI):
    """Create 'a Daily Conversation Tool' that takes 'a question' and generates 'a peer answer'"""
    chit_chat_prompt = ChatPromptTemplate.from_template(
        """당신은 교육생과 대화하는 친절하고 재치 있는 '동료'입니다.
        규정(RAG)이나 커리어 상담이 아닌, 가벼운 일상 대화나 감정 표현에 응답하세요.

        [사용자 질문]
        {question}

        [답변] (친절하고 재치있게 응답):"""
    )
    return chit_chat_prompt | llm | StrOutputParser()
