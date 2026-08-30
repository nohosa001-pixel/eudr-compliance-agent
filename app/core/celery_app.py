import os
try:
    from celery import Celery
    CELERY_INSTALLED = True
except ImportError:
    Celery = None
    CELERY_INSTALLED = False

from app.core.config import settings

broker_url = os.getenv("CELERY_BROKER_URL", settings.CELERY_BROKER_URL)
result_backend = os.getenv("CELERY_RESULT_BACKEND", settings.CELERY_RESULT_BACKEND)

if CELERY_INSTALLED and Celery is not None:
    celery_app = Celery(
        "eudr_compliance_worker",
        broker=broker_url,
        backend=result_backend,
        include=["app.tasks.eudr_tasks"]
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,  # 1 hour hard limit for ultra-large batch workloads
        task_soft_time_limit=3300,  # 55 minutes soft limit
        worker_prefetch_multiplier=1,  # Fair distribution among workers
        task_acks_late=True,  # Guarantee execution even if worker crashes
        task_reject_on_worker_lost=True,
    )
else:
    celery_app = None
