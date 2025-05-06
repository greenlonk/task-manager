from filters import register_filters
from fastapi import FastAPI, Form, Request, HTTPException, Depends, Query, File, UploadFile, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from cron_descriptor import get_description
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
import httpx, uuid, pathlib, json, os, shutil
import asyncio
from datetime import datetime, timedelta

# Import our models and services
from models import create_tables, TaskStatus, TaskPriority
from services import TaskService, CategoryService, AnalyticsService, CalendarService

# Environment variables
NTFY = os.environ.get("NTFY_URL", "https://ntfy.sh")
TZ = os.environ.get("TZ", "Europe/Berlin")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── APScheduler setup ----------------------------------------------------------
scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url="sqlite:///tasks.db")},
    timezone=TZ,
)

async def notify(topic: str, title: str, body: str, task_id: str = None):
    """Send notification and record execution"""
    # Send the notification
    httpx.post(
        f"{NTFY}/{topic}",
        headers={"Title": title},
        content=body
    ).raise_for_status()
    
    # Record the execution in history if task_id is provided
    if task_id:
        task_service.record_execution(task_id)

# Create our service instances
task_service = TaskService(scheduler)
category_service = CategoryService()
analytics_service = AnalyticsService()
calendar_service = CalendarService()

# ── FastAPI lifespan ----------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create or update tables
    create_tables()
    
    # Start the scheduler
    if not scheduler.running:
        scheduler.start()
    
    try:
        yield
    finally:
        # Shutdown the scheduler
        await asyncio.get_running_loop().run_in_executor(None, scheduler.shutdown)

# ── FastAPI setup -------------------------------------------------------------
app = FastAPI(lifespan=lifespan, title="Task Manager API")

# ── Static files and templates ------------------------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / "templates")

# Register custom Jinja2 filters
register_filters(templates)

# ── Helper functions ----------------------------------------------------------
def trigger_to_crontab(trigger) -> str:
    """Convert scheduler trigger to crontab format"""
    return " ".join(str(f) for f in trigger.fields[1:6])

def format_datetime(dt):
    """Format datetime for display"""
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")

# ── Web routes ----------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main application page"""
    # Get all tasks and categories
    tasks = task_service.get_all_tasks()
    categories = category_service.get_all_categories()
    stats = analytics_service.get_task_stats()
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request, 
            "tasks": tasks,
            "categories": categories,
            "stats": stats,
            "TaskStatus": TaskStatus,
            "TaskPriority": TaskPriority,
            "format_datetime": format_datetime
        }
    )

@app.get("/tasks", response_class=HTMLResponse)
async def get_tasks_fragment(
    request: Request,
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    priority: Optional[str] = None,
    sort_by: str = "created_at",
    sort_desc: bool = True
):
    """Get filtered tasks fragment for HTMX updates"""
    # Get filtered tasks
    tasks = task_service.get_all_tasks(
        status=status,
        category_id=category_id,
        priority=priority,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    categories = category_service.get_all_categories()
    
    return templates.TemplateResponse(
        "tasks_fragment.html",
        {
            "request": request, 
            "tasks": tasks,
            "categories": categories,
            "TaskStatus": TaskStatus,
            "TaskPriority": TaskPriority,
            "format_datetime": format_datetime,
            "current_filters": {
                "status": status,
                "category_id": category_id,
                "priority": priority,
                "sort_by": sort_by,
                "sort_desc": sort_desc
            }
        }
    )

@app.get("/task/{task_id}", response_class=HTMLResponse)
async def get_task_detail(
    request: Request,
    task_id: str
):
    """Get task detail fragment for modals"""
    task = task_service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    categories = category_service.get_all_categories()
    history = task_service.get_task_history(task_id)
    
    return templates.TemplateResponse(
        "task_detail.html",
        {
            "request": request, 
            "task": task,
            "categories": categories,
            "history": history,
            "TaskStatus": TaskStatus,
            "TaskPriority": TaskPriority,
            "format_datetime": format_datetime
        }
    )

@app.post("/add", response_class=HTMLResponse)
async def add_task(
    request: Request,
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    topic: str = Form(...),
    body: str = Form(...),
    cron: str = Form(...),
    description: Optional[str] = Form(None),
    priority: str = Form("MEDIUM"),
    category_id: Optional[int] = Form(None),
    notification_sound: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None),
    tags: Optional[str] = Form(None)
):
    """Add a new task"""
    # Handle file upload if present
    attachments = None
    if attachment and attachment.filename:
        file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{attachment.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(attachment.file, buffer)
        attachments = [{"name": attachment.filename, "path": file_path}]
    
    # Process tags
    tag_list = []
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    
    # Create the task
    try:
        task = task_service.create_task(
            title=title,
            topic=topic,
            body=body,
            cron_expression=cron,
            description=description,
            priority=priority,
            category_id=category_id if category_id else None,
            notification_sound=notification_sound,
            tags=tag_list,
            attachments=attachments,
            notify_function=notify
        )
        
        # Return the updated tasks list
        return await get_tasks_fragment(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/tasks/{task_id}", response_class=HTMLResponse)
async def update_task(
    request: Request,
    task_id: str,
    title: str = Form(...),
    topic: str = Form(...),
    body: str = Form(...),
    cron: str = Form(...),
    description: Optional[str] = Form(None),
    priority: str = Form("MEDIUM"),
    category_id: Optional[int] = Form(None),
    status: str = Form("PENDING"),
    notification_sound: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None),
    tags: Optional[str] = Form(None)
):
    """Update an existing task"""
    # Get the existing task
    task = task_service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Process file upload if present
    attachments = json.loads(task.attachments) if task.attachments else []
    if attachment and attachment.filename:
        file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{attachment.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(attachment.file, buffer)
        attachments.append({"name": attachment.filename, "path": file_path})
    
    # Process tags
    tag_list = []
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    
    # Update the task
    update_data = {
        "title": title,
        "topic": topic,
        "body": body,
        "cron_expression": cron,
        "description": description,
        "priority": priority,
        "category_id": category_id if category_id else None,
        "status": status,
        "notification_sound": notification_sound,
        "attachments": attachments,
        "tags": tag_list
    }
    
    try:
        task_service.update_task(task_id, update_data, notify_function=notify)
        
        # Return the updated task detail
        return await get_task_detail(request, task_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/tasks/{task_id}", response_class=HTMLResponse)
async def delete_task(request: Request, task_id: str):
    """Delete a task"""
    success = task_service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Return the updated tasks list
    return await get_tasks_fragment(request)

@app.post("/tasks/{task_id}/complete", response_class=HTMLResponse)
async def complete_task(request: Request, task_id: str):
    """Mark a task as completed"""
    task = task_service.complete_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Return the updated tasks list
    return await get_tasks_fragment(request)

@app.post("/tasks/{task_id}/snooze", response_class=HTMLResponse)
async def snooze_task(
    request: Request, 
    task_id: str,
    hours: int = Form(24)
):
    """Snooze a task for the specified duration"""
    task = task_service.snooze_task(task_id, duration_hours=hours)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Return the updated tasks list
    return await get_tasks_fragment(request)

@app.post("/tasks/{task_id}/reactivate", response_class=HTMLResponse)
async def reactivate_task(request: Request, task_id: str):
    """Reactivate a completed or snoozed task"""
    task = task_service.reactivate_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Return the updated tasks list
    return await get_tasks_fragment(request)

@app.post("/tasks/{task_id}/attachment", response_class=HTMLResponse)
async def add_attachment(
    request: Request,
    task_id: str,
    attachment: UploadFile = File(...)
):
    """Add an attachment to a task"""
    # Get the existing task
    task = task_service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Process file upload
    attachments = json.loads(task.attachments) if task.attachments else []
    if attachment and attachment.filename:
        file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{attachment.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(attachment.file, buffer)
        attachments.append({"name": attachment.filename, "path": file_path})
    else:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    # Update the task
    task_service.update_task(task_id, {"attachments": attachments})
    
    # Return the updated task detail
    return await get_task_detail(request, task_id)

@app.delete("/tasks/{task_id}/attachment/{attachment_index}", response_class=HTMLResponse)
async def delete_attachment(
    request: Request,
    task_id: str,
    attachment_index: int
):
    """Delete an attachment from a task"""
    # Get the existing task
    task = task_service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Process attachments
    attachments = json.loads(task.attachments) if task.attachments else []
    if 0 <= attachment_index < len(attachments):
        # Delete the file if it exists
        attachment = attachments[attachment_index]
        file_path = attachment.get("path")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        
        # Remove from the list
        attachments.pop(attachment_index)
    else:
        raise HTTPException(status_code=400, detail="Invalid attachment index")
    
    # Update the task
    task_service.update_task(task_id, {"attachments": attachments})
    
    # Return the updated task detail
    return await get_task_detail(request, task_id)

# ── Category management ------------------------------------------------------
@app.get("/categories", response_class=HTMLResponse)
async def get_categories_fragment(request: Request):
    """Get categories fragment for HTMX updates"""
    categories = category_service.get_all_categories()
    
    return templates.TemplateResponse(
        "categories_fragment.html",
        {"request": request, "categories": categories}
    )

@app.post("/categories", response_class=HTMLResponse)
async def add_category(
    request: Request,
    name: str = Form(...),
    color: str = Form("#4facfe"),
    icon: Optional[str] = Form(None)
):
    """Add a new category"""
    try:
        category_service.create_category(name=name, color=color, icon=icon)
        return await get_categories_fragment(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/categories/{category_id}", response_class=HTMLResponse)
async def update_category(
    request: Request,
    category_id: int,
    name: str = Form(...),
    color: str = Form("#4facfe"),
    icon: Optional[str] = Form(None)
):
    """Update a category"""
    update_data = {"name": name, "color": color}
    if icon:
        update_data["icon"] = icon
    
    category = category_service.update_category(category_id, update_data)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return await get_categories_fragment(request)

@app.delete("/categories/{category_id}", response_class=HTMLResponse)
async def delete_category(
    request: Request,
    category_id: int,
    reassign_to_id: Optional[int] = Query(None)
):
    """Delete a category"""
    success = category_service.delete_category(category_id, reassign_to_id)
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return await get_categories_fragment(request)

# ── Analytics and stats ------------------------------------------------------
@app.get("/analytics", response_class=HTMLResponse)
async def get_analytics(request: Request):
    """Get analytics page"""
    stats = analytics_service.get_task_stats()
    completion_rate = analytics_service.get_task_completion_rate()
    
    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request, 
            "stats": stats,
            "completion_rate": completion_rate
        }
    )

@app.get("/analytics/stats.json")
async def get_analytics_data():
    """Get analytics data as JSON for charts"""
    stats = analytics_service.get_task_stats()
    completion_rate = analytics_service.get_task_completion_rate()
    
    return JSONResponse(content={
        "stats": jsonable_encoder(stats),
        "completion_rate": jsonable_encoder(completion_rate)
    })

# ── Calendar integration -----------------------------------------------------
@app.get("/tasks.ics")
async def export_calendar(task_id: Optional[str] = None):
    """Export tasks as iCalendar"""
    ical_data = calendar_service.export_ical(task_id)
    if not ical_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return Response(
        content=ical_data,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f"attachment; filename=tasks.ics"
        }
    )

# ── dev entry point -----------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    # Use a different approach that might avoid the permission issue
    config = uvicorn.Config(app, host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    server.run()
