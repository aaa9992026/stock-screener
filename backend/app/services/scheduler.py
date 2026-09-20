from apscheduler.schedulers.background import BackgroundScheduler
from app.services.company_auto_sync import sync_all_companies


scheduler = BackgroundScheduler()


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            sync_all_companies,
            "interval",
            hours=24,
            id="company_sync",
            replace_existing=True
        )

        scheduler.start()