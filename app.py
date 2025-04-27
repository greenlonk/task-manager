from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from cron_descriptor import get_description
from contextlib import asynccontextmanager
import httpx, uuid, pathlib
import asyncio
import os



NTFY = os.environ.get("NTFY_URL", "https://ntfy.sh")
TZ = os.environ.get("TZ", "Europe/Berlin")

# ── APScheduler ---------------------------------------------------------------
scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url="sqlite:///tasks.db")},
    timezone=TZ,
)

def notify(topic: str, title: str, body: str):
    httpx.post(
        f"{NTFY}/{topic}",
        headers={"Title": title},
        content=body
    ).raise_for_status()

# ── FastAPI lifespan ----------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not scheduler.running:
        scheduler.start()
    try:
        yield
    finally:
        await asyncio.get_running_loop().run_in_executor(None, scheduler.shutdown)

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / "templates")

# ── helpers -------------------------------------------------------------------
def trigger_to_crontab(trigger) -> str:
    # drop seconds & year → five-field crontab
    return " ".join(str(f) for f in trigger.fields[1:6])

def _jobs():
    return [
        {
            "id": j.id,
            "name": j.name,
            "pretty": get_description(trigger_to_crontab(j.trigger)),
        }
        for j in scheduler.get_jobs()
    ]

def _render_full(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "jobs": _jobs()},
    )

def _render_fragment(request: Request):
    # tasks_fragment.html contains ONLY the <div id="tasks">…</div>
    return templates.TemplateResponse(
        "tasks_fragment.html",
        {"request": request, "jobs": _jobs()},
    )

# ── routes --------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _render_full(request)

@app.post("/add", response_class=HTMLResponse)
async def add_task(
    request: Request,
    topic: str = Form(...),
    title: str = Form(...),
    body: str = Form(...),
    cron: str = Form(...),
):
    try:
        trigger = CronTrigger.from_crontab(cron, timezone="Europe/Berlin")
    except ValueError as exc:                # ← exc, not exec
        raise HTTPException(status_code=400, detail=str(exc))

    scheduler.add_job(
        notify,
        trigger,
        id=str(uuid.uuid4()),
        name=title,
        args=(topic, title, body),
        misfire_grace_time=60,
    )
    return _render_fragment(request)         # HTMX swaps "#tasks"

@app.delete("/jobs/{job_id}", response_class=HTMLResponse)
async def delete_job(request: Request, job_id: str):
    if job := scheduler.get_job(job_id):
        job.modify(next_run_time=None)       # cancel any queued run
        scheduler.remove_job(job_id)
    return _render_fragment(request)         # HTMX swaps "#tasks"

# ── dev entry point -----------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

