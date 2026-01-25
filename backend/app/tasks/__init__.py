"""
TaskIQ Tasks Module
"""
from app.tasks.poster_tasks import (
    process_batch_job_task,
    process_single_poster_task,
    cleanup_old_jobs_task,
    process_ai_poster_generation_task,
    get_ai_poster_job,
    set_ai_poster_job,
    update_ai_poster_job
)

__all__ = [
    "process_batch_job_task",
    "process_single_poster_task",
    "cleanup_old_jobs_task",
    "process_ai_poster_generation_task",
    "get_ai_poster_job",
    "set_ai_poster_job",
    "update_ai_poster_job"
]
