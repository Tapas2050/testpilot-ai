"""Entry point for executing the arq background worker via `python -m app.worker`."""

from arq import run_worker

from app.core.logging import setup_structured_logging
from app.worker.tasks import WorkerSettings

if __name__ == "__main__":
    setup_structured_logging()
    run_worker(WorkerSettings)
