import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

# --- CONFIGURATION ---
# In production (Railway), this will be: os.getenv("DATABASE_URL")
# For now, it creates a robust local file 'auditflow.db'
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./auditflow.db")

Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- MODELS (TABLES) ---

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    role = Column(String, default="Viewer") # Administrator, Analyst, Viewer
    title = Column(String)
    phone = Column(String)

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True)
    description = Column(String)
    upload_date = Column(String)
    review_date = Column(String)
    uploaded_by = Column(String)

class AnswerBank(Base):
    __tablename__ = "answer_bank"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, index=True)
    answer = Column(Text)
    product = Column(String)
    subsidiary = Column(String)
    verified_by = Column(String)
    date_added = Column(String)

# --- INITIALIZATION ---
def init_db():
    """Creates tables if they don't exist."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Helper to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
