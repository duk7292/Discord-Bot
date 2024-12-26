from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Date, Boolean, Text, Enum, JSON, TIMESTAMP, ARRAY, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import enum
import uuid
from datetime import datetime

import mysql.connector

#setup .env needed
config = {
    'user': 'root',        
    'password': '', 
    'host': 'localhost',    
}


conn = mysql.connector.connect(**config)
cursor = conn.cursor()


cursor.execute("CREATE DATABASE IF NOT EXISTS DiscordBotData")



cursor.close()
conn.close()


Base = declarative_base()


class TicketStatus(enum.Enum):
    open = "Open"
    closed = "Closed"
    pending = "Pending"

class Server(Base):
    __tablename__ = 'servers'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    server_name = Column(String(255), nullable=False)
    birthday_reminder_channel = Column(String(36), nullable=True) 



    members = relationship("Member", back_populates="server")
    

class Member(Base):
    __tablename__ = 'members'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    server_id = Column(String(36), ForeignKey('servers.id'), nullable=False)
    username = Column(String(255), nullable=False)
    messages_send = Column(Integer, default=0)
    level = Column(Integer, default=0)  
    birthday = Column(Date, nullable=True) 


    server = relationship("Server", back_populates="members")

class SupportTicket(Base):
    __tablename__ = 'support_tickets'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    server_id = Column(String(36), ForeignKey('servers.id'), nullable=False)
    user_id = Column(String(36), ForeignKey('members.id'), nullable=False)
    issue_description = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default='open')
    created_at = Column(DateTime, default=datetime.now)
    resolved_at = Column(DateTime, nullable=True)


    server = relationship("Server", back_populates="support_tickets")
    channels = relationship("SupportChannel", back_populates="support_ticket")
    user = relationship("Member")


class SupportChannel(Base):
    __tablename__ = 'support_channels'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    support_ticket_id = Column(String(36), ForeignKey('support_tickets.id'), nullable=False)
    channel_id = Column(String(36), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


    support_ticket = relationship("SupportTicket", back_populates="channels")


DATABASE_URL = ""#setup .env needed


engine = create_engine(DATABASE_URL)


Base.metadata.drop_all(engine)

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)


session = Session()

Base.metadata.create_all(engine)
