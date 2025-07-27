from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    TIMESTAMP,
    ForeignKey,
    JSON,
    Enum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class ChatThread(Base):
    __tablename__ = 'chat_threads'

    thread_id = Column(Integer, primary_key=True, autoincrement=True)
    session_uuid = Column(String(55), nullable=False, index=True)
    title = Column(String(255), nullable=True, default=None)
    dataset_id = Column(Integer, nullable=True, default=None)
    thread_metadata = Column(JSON, default=None)
    created_on = Column(TIMESTAMP, server_default=func.current_timestamp())
    modified_on = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    is_active = Column(Boolean, default=True)

    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatThread(thread_id={self.thread_id}, session_uuid='{self.session_uuid}', title='{self.title}')>"


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(Integer, ForeignKey('chat_threads.thread_id', ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    role = Column(Enum('user', 'bot', 'system', name="role_enum"), nullable=False)
    llm_context = Column(JSON, default=None)
    is_active = Column(Boolean, default=True)
    created_on = Column(TIMESTAMP, server_default=func.current_timestamp())
    modified_on = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    thread = relationship("ChatThread", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage(message_id={self.message_id}, role='{self.role}', thread_id={self.thread_id})>"


class Dataset(Base):
    __tablename__ = 'datasets'

    dataset_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default=None)
    dataset_metadata = Column(JSON, default=None)
    created_by = Column(String(100), nullable=False)
    created_on = Column(TIMESTAMP, server_default=func.current_timestamp())
    modified_on = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Dataset(dataset_id={self.dataset_id}, name='{self.name}')>"
