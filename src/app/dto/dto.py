# 모듈 불러오기
from typing import Annotated, TypedDict, Literal, List
from langchain.schema import BaseMessage
import operator

class State(TypedDict):
    # 모델 입출력
    messages: Annotated[List[BaseMessage], operator.add]

    # 현재 그래프가 진행중인 단계
    status: Literal["acting", "done"]