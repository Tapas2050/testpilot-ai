"""Entry point for executing the arq background worker via `python -m app.worker`."""

from arq import run_worker

from app.worker.tasks import WorkerSettings

if __name__ == "__main__":
    run_worker(WorkerSettings)
