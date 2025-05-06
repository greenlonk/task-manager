import uuid
import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import desc, asc, select
from sqlalchemy.orm import joinedload, contains_eager
from models import Task, Category, TaskHistory, TaskStatus, TaskPriority, get_session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import json
from fastapi import HTTPException

class TaskService:
    def __init__(self, scheduler: AsyncIOScheduler):
        self.scheduler = scheduler
    
    def get_all_tasks(self, status: Optional[str] = None, category_id: Optional[int] = None, 
                       priority: Optional[str] = None, sort_by: str = "created_at", 
                       sort_desc: bool = True) -> List[Task]:
        """Get all tasks with optional filtering"""
        session = get_session()
        query = session.query(Task)
        
        # Apply filters
        if status:
            query = query.filter(Task.status == TaskStatus(status))
        
        if category_id:
            query = query.filter(Task.category_id == category_id)
        
        if priority:
            query = query.filter(Task.priority == TaskPriority(priority))
        
        # Apply sorting
        if hasattr(Task, sort_by):
            order_column = getattr(Task, sort_by)
            if sort_desc:
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))
        
        # Execute query
        # Eager load the category relationship to avoid DetachedInstanceError
        # This prevents DetachedInstanceError when accessing task.category after session close
        query = query.options(joinedload(Task.category))
        
        tasks = query.all() 
        session.close()
        return tasks
    
    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get a task by ID"""
        session = get_session()
        task = session.query(Task)\
            .options(joinedload(Task.category)).filter(Task.id == task_id).first()
        session.close()
        return task
    
    def create_task(self, title: str, topic: str, body: str, cron_expression: str, 
                    description: Optional[str] = None, priority: str = "MEDIUM", 
                    category_id: Optional[int] = None, notification_channels: Dict[str, bool] = None,
                    notification_sound: Optional[str] = None, timezone: str = "Europe/Berlin", attachments: Optional[List] = None,
                    tags: List[str] = None, notify_function=None) -> Task:
        """Create a new task and schedule it"""
        if notify_function is None:
            raise ValueError("Notify function must be provided")
        
        # Generate UUID for the task
        task_id = str(uuid.uuid4())
        
        # Create a new Task record
        session = get_session()
        
        task = Task(
            id=task_id,
            title=title,
            description=description or "",
            topic=topic,
            body=body,
            cron_expression=cron_expression,
            priority=TaskPriority(priority),
            status=TaskStatus.PENDING,
            category_id=category_id,
            timezone=timezone,
            notification_channels=notification_channels or {"ntfy": True},
            attachments=json.dumps(attachments) if attachments else None,
            notification_sound=notification_sound,
            tags=tags or []
        )
        
        # Add to database
        session.add(task)
        session.commit()
        
        # Schedule the task
        try:
            trigger = CronTrigger.from_crontab(cron_expression, timezone=timezone)
            
            self.scheduler.add_job(
                notify_function,
                trigger,
                id=task_id,
                name=title,
                args=(topic, title, body, task_id),  # Pass task_id to track execution
                misfire_grace_time=60,
                replace_existing=True
            )
        except Exception as e:
            # Rollback if scheduling fails
            session.delete(task)
            session.commit()
            session.close()
            raise HTTPException(status_code=400, detail=str(e))
        
        session.close()
        return task
    
    def update_task(self, task_id: str, update_data: Dict[str, Any], notify_function=None) -> Optional[Task]:
        """Update a task and reschedule if necessary"""
        session = get_session()
        task = session.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            session.close()
            return None
        
        # Update task fields
        for key, value in update_data.items():
            if hasattr(task, key):
                # Handle enum values
                if key == 'priority' and isinstance(value, str):
                    setattr(task, key, TaskPriority(value))
                elif key == 'status' and isinstance(value, str):
                    old_status = task.status
                    new_status = TaskStatus(value)
                    setattr(task, key, new_status)
                    
                    # Handle status transitions
                    if old_status != new_status:
                        if new_status == TaskStatus.COMPLETED:
                            task.completed_at = datetime.datetime.now()
                        elif new_status == TaskStatus.SNOOZED and 'snoozed_until' in update_data:
                            task.snoozed_until = update_data['snoozed_until']
                            
                        # Add to history
                        history_entry = TaskHistory(
                            task_id=task_id,
                            status=f"Status changed from {old_status.value} to {new_status.value}",
                            details={"old": old_status.value, "new": new_status.value}
                        )
                        session.add(history_entry)
                else:
                    setattr(task, key, value)
        
        # Update modified timestamp
        task.modified_at = datetime.datetime.now()
        
        # Reschedule if cron expression or other scheduling-related fields changed
        reschedule_keys = {'cron_expression', 'timezone', 'status', 'snoozed_until'}
        if any(key in update_data for key in reschedule_keys) and notify_function:
            # Get the existing job
            job = self.scheduler.get_job(task_id)
            
            # If job exists and task is active, update it
            if job:
                # Remove existing job
                self.scheduler.remove_job(task_id)
            
            # Only reschedule if the task is pending (not completed or paused)
            if task.status == TaskStatus.PENDING:
                try:
                    trigger = CronTrigger.from_crontab(task.cron_expression, timezone=task.timezone)
                    
                    self.scheduler.add_job(
                        notify_function,
                        trigger,
                        id=task_id,
                        name=task.title,
                        args=(task.topic, task.title, task.body, task_id),
                        misfire_grace_time=60,
                        replace_existing=True
                    )
                except Exception as e:
                    # Log error but don't fail the update
                    print(f"Error rescheduling task {task_id}: {str(e)}")
        
        session.commit()
        session.close()
        return task
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task and remove from scheduler"""
        session = get_session()
        task = session.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            session.close()
            return False
        
        # Delete from database
        session.delete(task)
        
        # Delete history entries
        session.query(TaskHistory).filter(TaskHistory.task_id == task_id).delete()
        
        session.commit()
        session.close()
        
        # Remove from scheduler
        job = self.scheduler.get_job(task_id)
        if job:
            self.scheduler.remove_job(task_id)
        
        return True
    
    def complete_task(self, task_id: str) -> Optional[Task]:
        """Mark a task as completed"""
        return self.update_task(task_id, {
            'status': 'COMPLETED',
            'completed_at': datetime.datetime.now()
        })
    
    def snooze_task(self, task_id: str, duration_hours: int = 24) -> Optional[Task]:
        """Snooze a task for the specified duration"""
        snooze_until = datetime.datetime.now() + datetime.timedelta(hours=duration_hours)
        return self.update_task(task_id, {
            'status': 'SNOOZED',
            'snoozed_until': snooze_until
        })
    
    def reactivate_task(self, task_id: str) -> Optional[Task]:
        """Reactivate a completed or snoozed task"""
        return self.update_task(task_id, {
            'status': 'PENDING',
            'snoozed_until': None
        })
    
    def record_execution(self, task_id: str) -> None:
        """Record that a task has executed"""
        session = get_session()
        task = session.query(Task).filter(Task.id == task_id).first()
        
        if task:
            # Update execution stats
            task.run_count += 1
            task.last_run = datetime.datetime.now()
            
            # Add to history
            history_entry = TaskHistory(
                task_id=task_id,
                status="executed",
                details={"run_count": task.run_count}
            )
            session.add(history_entry)
            
            session.commit()
        
        session.close()
    
    def get_task_history(self, task_id: str) -> List[TaskHistory]:
        """Get execution history for a task"""
        session = get_session()
        
        # Get the task history with proper eager loading to avoid DetachedInstanceError
        history = session.query(TaskHistory).filter(TaskHistory.task_id == task_id)\
                  .order_by(desc(TaskHistory.timestamp)).all()
        
        session.close()
        
        return history

class CategoryService:
    def get_all_categories(self) -> List[Category]:
        """Get all categories"""
        session = get_session()
        # All relationships in models.py have been set to lazy="joined", so no need for additional joinedload here
        categories = session.query(Category).all()
        session.close()
        return categories
    
    def get_category(self, category_id: int) -> Optional[Category]:
        """Get a category by ID"""
        session = get_session()
        category = session.query(Category).filter(Category.id == category_id).first()
        session.close()
        return category
    
    def create_category(self, name: str, color: str, icon: Optional[str] = None) -> Category:
        """Create a new category"""
        session = get_session()
        
        # Check if category with this name already exists
        existing = session.query(Category).filter(Category.name == name).first()
        if existing:
            session.close()
            raise ValueError(f"Category '{name}' already exists")
        
        category = Category(name=name, color=color, icon=icon)
        session.add(category)
        session.commit()
        
        # Refresh to get the ID
        session.refresh(category)
        result = Category(id=category.id, name=category.name, color=category.color, icon=category.icon)
        
        session.close()
        return result
    
    def update_category(self, category_id: int, update_data: Dict[str, Any]) -> Optional[Category]:
        """Update a category"""
        session = get_session()
        category = session.query(Category).filter(Category.id == category_id).first()
        
        if not category:
            session.close()
            return None
        
        # Update category fields
        for key, value in update_data.items():
            if hasattr(category, key):
                setattr(category, key, value)
        
        session.commit()
        
        # Return a copy of the updated category
        result = Category(
            id=category.id, 
            name=category.name, 
            color=category.color, 
            icon=category.icon
        )
        
        session.close()
        return result
    
    def delete_category(self, category_id: int, reassign_to_id: Optional[int] = None) -> bool:
        """Delete a category and optionally reassign its tasks"""
        session = get_session()
        category = session.query(Category).filter(Category.id == category_id).first()
        
        if not category:
            session.close()
            return False
        
        # If reassign_to_id is provided, reassign tasks
        if reassign_to_id:
            session.query(Task).filter(Task.category_id == category_id).\
                update({Task.category_id: reassign_to_id})
        else:
            # Otherwise, set category to null for all tasks
            session.query(Task).filter(Task.category_id == category_id).\
                update({Task.category_id: None})
        
        # Delete the category
        session.delete(category)
        session.commit()
        session.close()
        
        return True

class AnalyticsService:
    def get_task_stats(self):
        """Get statistics about tasks"""
        session = get_session()
        
        # Total count
        total_count = session.query(Task).count()
        
        # Status counts
        status_counts = {}
        for status in TaskStatus:
            count = session.query(Task).filter(Task.status == status).count()
            status_counts[status.value] = count
        
        # Priority counts
        priority_counts = {}
        for priority in TaskPriority:
            count = session.query(Task).filter(Task.priority == priority).count()
            priority_counts[priority.value] = count
        
        # Category distribution
        category_distribution = {}
        categories = session.query(Category).all()
        for category in categories:
            count = session.query(Task).filter(Task.category_id == category.id).count()
            category_distribution[category.name] = {
                "count": count,
                "color": category.color,
                "icon": category.icon
            }
        
        # Add uncategorized count
        uncategorized_count = session.query(Task).filter(Task.category_id == None).count()
        category_distribution["Uncategorized"] = {
            "count": uncategorized_count,
            "color": "#9ca3af",
            "icon": "question"
        }
        
        # Get execution history stats
        executions_today = session.query(TaskHistory).filter(
            TaskHistory.status == "executed",
            TaskHistory.timestamp >= datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
        
        # Get day of week distribution
        day_of_week = {}
        for i in range(7):
            day = session.query(TaskHistory).filter(
                TaskHistory.status == "executed",
                TaskHistory.timestamp >= datetime.datetime.now() - datetime.timedelta(days=30)
            ).count()
            day_of_week[i] = day
        
        session.close()
        
        return {
            "total_count": total_count,
            "status_counts": status_counts,
            "priority_counts": priority_counts,
            "category_distribution": category_distribution,
            "executions_today": executions_today,
            "day_of_week": day_of_week
        }
    
    def get_task_completion_rate(self, days: int = 30):
        """Get task completion rate for the specified number of days"""
        session = get_session()
        
        # Get completed tasks in the period
        start_date = datetime.datetime.now() - datetime.timedelta(days=days)
        completed = session.query(Task).filter(
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at >= start_date
        ).count()
        
        # Get total tasks created in the period
        created = session.query(Task).filter(
            Task.created_at >= start_date
        ).count()
        
        session.close()
        
        return {
            "completed": completed,
            "created": created,
            "rate": completed / created if created > 0 else 0
        }

# Calendar integration services
class CalendarService:
    def export_ical(self, task_id: Optional[str] = None):
        """Export tasks as iCalendar format"""
        from icalendar import Calendar, Event
        import pytz
        
        session = get_session()
        
        # Create calendar
        cal = Calendar()
        cal.add('prodid', '-//Task Manager//taskmanager.app//')
        cal.add('version', '2.0')
        
        # Get tasks to export
        if task_id:
            tasks = [session.query(Task).filter(Task.id == task_id).first()]
            if not tasks[0]:
                session.close()
                return None
        else:
            tasks = session.query(Task).filter(
                Task.status != TaskStatus.COMPLETED
            ).all()
        
        # Add each task as an event
        for task in tasks:
            event = Event()
            event.add('summary', task.title)
            event.add('description', task.body)
            event.add('uid', task.id)
            
            # Add category if available
            if task.category_id:
                category = session.query(Category).filter(Category.id == task.category_id).first()
                if category:
                    event.add('categories', category.name)
            
            # Add a sample schedule (since cron doesn't translate directly to iCal)
            # This is a simplification - real implementation would need to interpret cron
            # and create proper RRULE recurrence patterns
            tz = pytz.timezone(task.timezone)
            now = datetime.datetime.now(tz)
            event.add('dtstart', now)
            event.add('dtend', now + datetime.timedelta(minutes=30))
            
            cal.add_component(event)
        
        session.close()
        return cal.to_ical()
