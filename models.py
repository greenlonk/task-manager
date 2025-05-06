from sqlalchemy import Boolean, Column, Integer, String, Text, Float, DateTime, Enum, JSON, create_engine, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import enum
import os
import datetime

Base = declarative_base()

# Enum definitions
class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class TaskStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SNOOZED = "snoozed"

# Task Category model
class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    color = Column(String(20), nullable=False, default="#4facfe")
    icon = Column(String(50), nullable=True)
    
    # Relationships
    tasks = relationship("Task", back_populates="category", lazy="joined")
    
    def __repr__(self):
        return f"<Category {self.name}>"

# Extended Task model
class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String(50), primary_key=True) # UUID from APScheduler
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    topic = Column(String(100), nullable=False) # ntfy topic
    body = Column(Text, nullable=False) # ntfy message
    cron_expression = Column(String(100), nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    snoozed_until = Column(DateTime, nullable=True)
    timezone = Column(String(50), default="Europe/Berlin")
    
    # Additional metadata fields
    tags = Column(JSON, nullable=True)
    attachments = Column(JSON, nullable=True) # Store paths to attached files
    notes = Column(Text, nullable=True) # For additional notes or comments
    
    # Notification settings
    notification_channels = Column(JSON, default={"ntfy": True})
    notification_sound = Column(String(50), nullable=True)
    
    # Stats and metadata
    run_count = Column(Integer, default=0) # Number of times executed
    last_run = Column(DateTime, nullable=True)
    
    # Relationships
    category = relationship("Category", back_populates="tasks", lazy="joined")
    
    def __repr__(self):
        return f"<Task {self.title}>"

# Task History model to track completions and runs
class TaskHistory(Base):
    __tablename__ = "task_history"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String(50), ForeignKey("tasks.id"), nullable=False)
    status = Column(String(50), nullable=False) # Status change or "executed"
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    details = Column(JSON, nullable=True) # Any additional details about the run
    
    def __repr__(self):
        return f"<TaskHistory {self.task_id} {self.status} at {self.timestamp}>"

# Connection setup
def get_engine(db_url="sqlite:///tasks.db"):
    return create_engine(db_url)

def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def create_tables():
    engine = get_engine()
    Base.metadata.create_all(engine)
    
    # Create default categories if they don't exist
    session = get_session()
    default_categories = [
        {"name": "Work", "color": "#4facfe", "icon": "briefcase"},
        {"name": "Personal", "color": "#43e97b", "icon": "user"},
        {"name": "Health", "color": "#f78ca0", "icon": "heart"},
        {"name": "Finance", "color": "#38b2ac", "icon": "dollar-sign"},
        {"name": "Home", "color": "#a78bfa", "icon": "home"},
        {"name": "Other", "color": "#9ca3af", "icon": "tag"}
    ]
    
    for cat_data in default_categories:
        if not session.query(Category).filter_by(name=cat_data["name"]).first():
            session.add(Category(**cat_data))
    
    session.commit()
    session.close()

if __name__ == "__main__":
    create_tables()
