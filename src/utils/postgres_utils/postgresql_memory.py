import os
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.memory.chat_message_histories.sql import BaseMessageConverter
from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from langchain_community.chat_message_histories import SQLChatMessageHistory

# 1. SQLAlchemy 모델 정의
Base = declarative_base()

# class CustomMessageModel(Base):
#     __tablename__ = "wantedash_store"
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     session_id = Column(String)
#     conversation_id = Column(String)
#     type = Column(String)
#     content = Column(Text)

class CustomMessageModel(Base):
    __tablename__ = "wantedash_store"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)  # ✅ 추가됨
    type = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 2. 커스텀 컨버터 클래스 정의
class CustomMessageConverter(BaseMessageConverter):
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
    def get_sql_model_class(self):
        """최신버전에서는 필요없음"""
        return CustomMessageModel
    def to_sql_model(self, message: BaseMessage, session_id: str) -> CustomMessageModel:
        """LangChain 메시지를 SQL 모델로 변환"""
        # print(f'Custom Sql Message Converter : {session_id}, {self.conversation_id}')
        return CustomMessageModel(
            session_id=session_id,
            conversation_id=self.conversation_id,  # 여기에 conversation_id를 할당
            type=message.type,
            content=message.content
        )
    def from_sql_model(self, sql_model: CustomMessageModel) -> BaseMessage:
        """SQL 모델을 LangChain 메시지로 변환"""
        message_type = sql_model.type
        content = sql_model.content
        conversation_id=sql_model.conversation_id
        created_at=sql_model.created_at
        # print(f'Custom Sql Message Converter : {sql_model.session_id}:{sql_model.conversation_id}-{message_type}:{content}')
        # 메시지 타입에 따라 적절한 BaseMessage 서브클래스로 변환
        if message_type == "human":
            return HumanMessage(content=content,conversation_id=conversation_id,created_at=created_at)
        elif message_type == "ai":
            return AIMessage(content=content,conversation_id=conversation_id,created_at=created_at)
        # 기타 필요한 메시지 타입 추가
        else:
            return BaseMessage(content=content,conversation_id=conversation_id,created_at=created_at)

class CustomSQLChatMessageHistory(SQLChatMessageHistory):
    def __init__(self, session_id: str, conversation_id: str, **kwargs):
        super().__init__(session_id=session_id, **kwargs)
        self.conversation_id = conversation_id

    @property
    def messages(self):
        with self._make_sync_session() as session:
            records = (
                session.query(self.sql_model_class)
                .filter_by(session_id=self.session_id, conversation_id=self.conversation_id)
                .order_by(self.sql_model_class.id.asc())
                .all()
            )
            return [self.converter.from_sql_model(r) for r in records]
    def allmessages(self):
        with self._make_sync_session() as session:
            records = (
                session.query(self.sql_model_class)
                .filter_by(session_id=self.session_id)
                .order_by(self.sql_model_class.id.asc())
                .all()
            )
            return [self.converter.from_sql_model(r) for r in records]

def get_chat_history(session_id:str, conversation_id:str):
    return CustomSQLChatMessageHistory(
        session_id=session_id,
        conversation_id=conversation_id,
        ## .env DB_URL 반드시 필요
        connection=os.getenv('DB_URL'),
        custom_message_converter=CustomMessageConverter(conversation_id=conversation_id),
    )
def get_session_history(session_id:str):
    return CustomSQLChatMessageHistory(
        session_id=session_id,
        conversation_id='',
        ## .env DB_URL 반드시 필요
        connection=os.getenv('DB_URL'),
        custom_message_converter=CustomMessageConverter(conversation_id=''),
    ).allmessages()
    