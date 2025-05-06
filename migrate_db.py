import sqlite3
import json
import uuid
import datetime
from models import create_tables, get_session, Task, Category, TaskStatus, TaskPriority
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import pickle
import zlib
import base64

def migrate_from_apscheduler():
    print("Starting database migration...")
    
    # Create new tables
    create_tables()
    
    # Connect to the SQLite database
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # Query all jobs from the APScheduler table
    cursor.execute("SELECT id, job_state FROM apscheduler_jobs")
    jobs = cursor.fetchall()
    
    print(f"Found {len(jobs)} tasks to migrate")
    
    # Get a database session for our new models
    session = get_session()
    
    # Get the "Other" category as default
    default_category = session.query(Category).filter_by(name="Other").first()
    
    # Process each job
    for job_id, job_state_blob in jobs:
        try:
            # Deserialize the job state
            job_state = pickle.loads(zlib.decompress(base64.b64decode(job_state_blob)))
            
            # Extract the task data
            func_args = job_state.get('args', [])
            if len(func_args) >= 3:
                topic, title, body = func_args[:3]
                
                # Get the cron expression if available
                cron_expression = ""
                trigger = job_state.get('trigger', None)
                if trigger and hasattr(trigger, 'fields'):
                    # Convert trigger fields to cron format
                    fields = [str(f) for f in trigger.fields[1:6]]  # Skip seconds, year
                    cron_expression = " ".join(fields)
                
                # Create a new Task record
                task = Task(
                    id=job_id,
                    title=title,
                    description="",
                    topic=topic,
                    body=body,
                    cron_expression=cron_expression,
                    priority=TaskPriority.MEDIUM,
                    status=TaskStatus.PENDING,
                    category_id=default_category.id if default_category else None,
                    created_at=datetime.datetime.now(),
                    modified_at=datetime.datetime.now()
                )
                
                session.add(task)
                print(f"Migrated task: {title}")
            else:
                print(f"Skipped job {job_id} - insufficient arguments")
        except Exception as e:
            print(f"Error migrating job {job_id}: {str(e)}")
    
    # Commit the changes
    session.commit()
    session.close()
    conn.close()
    
    print("Migration completed successfully")

if __name__ == "__main__":
    migrate_from_apscheduler()
