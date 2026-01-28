"""Background job system for long-running tasks.

Uses threading with a job queue for multi-user support.
Jobs are tracked in the database so users can see progress.
"""
import threading
import uuid
import traceback
from datetime import datetime
from queue import Queue
from typing import Callable, Any
from dataclasses import dataclass, field
from enum import Enum


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    name: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    total: int = 0
    message: str = ""
    result: Any = None
    error: str = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime = None
    completed_at: datetime = None


# In-memory job storage (for simplicity - could use Redis for production)
_jobs: dict[str, Job] = {}
_job_queue: Queue = Queue()
_workers_started = False
_num_workers = 2


def _worker():
    """Background worker that processes jobs from the queue."""
    while True:
        job_id, func, args, kwargs = _job_queue.get()
        job = _jobs.get(job_id)
        if not job:
            continue
        
        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            
            # Run the job function, passing the job for progress updates
            result = func(job, *args, **kwargs)
            
            job.result = result
            job.status = JobStatus.COMPLETED
            job.progress = job.total
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        finally:
            job.completed_at = datetime.now()
            _job_queue.task_done()


def start_workers():
    """Start background worker threads."""
    global _workers_started
    if _workers_started:
        return
    
    for i in range(_num_workers):
        t = threading.Thread(target=_worker, daemon=True, name=f"job-worker-{i}")
        t.start()
    
    _workers_started = True


def submit_job(name: str, func: Callable, *args, **kwargs) -> str:
    """
    Submit a job to be processed in the background.
    
    Args:
        name: Human-readable job name
        func: Function to call. First argument will be the Job object for progress updates.
        *args, **kwargs: Additional arguments to pass to func
    
    Returns:
        Job ID for tracking
    """
    start_workers()
    
    job_id = str(uuid.uuid4())[:8]
    job = Job(id=job_id, name=name)
    _jobs[job_id] = job
    
    _job_queue.put((job_id, func, args, kwargs))
    
    return job_id


def get_job(job_id: str) -> Job | None:
    """Get job by ID."""
    return _jobs.get(job_id)


def get_all_jobs() -> list[Job]:
    """Get all jobs, most recent first."""
    return sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)


def clear_completed_jobs():
    """Remove completed/failed jobs older than 1 hour."""
    now = datetime.now()
    to_remove = []
    for job_id, job in _jobs.items():
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            if job.completed_at and (now - job.completed_at).seconds > 3600:
                to_remove.append(job_id)
    for job_id in to_remove:
        del _jobs[job_id]


def job_to_dict(job: Job) -> dict:
    """Convert job to JSON-serializable dict."""
    return {
        "id": job.id,
        "name": job.name,
        "status": job.status.value,
        "progress": job.progress,
        "total": job.total,
        "message": job.message,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
