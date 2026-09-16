import asyncio
import re
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncpg

from app.core.celery_app import celery_app
from app.core.config import settings
from app.repositories.analytics_repo import AnalyticsRepository

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

async def _process_analytics(job_id: int):
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
    repo = AnalyticsRepository(conn)

    try:
        job = await repo.get_job_by_id(job_id)
        if not job:
            return

        await repo.set_job_running(job_id)
        
        user_id = job["user_id"]
        params = job["params"] or {}
        if isinstance(params, str):
            import json
            params = json.loads(params)

        tz_str = params.get("timezone", "UTC")
        target_tz = ZoneInfo(tz_str)

        tasks_query = """
            SELECT title, completed, created_at, completed_at
            FROM tasks
            WHERE owner_id = $1;
        """
        tasks = await conn.fetch(tasks_query, user_id)

        total_tasks = len(tasks)
        completed_true = 0
        completed_false = 0
        total_duration_hours = 0.0
        completed_durations_count = 0
        weekday_distribution = {day: 0 for day in DAYS_OF_WEEK}
        all_words = []

        for t in tasks:
            is_completed = bool(t["completed"])
            
            if is_completed:
                completed_true += 1
                if t["completed_at"] and t["created_at"]:
                    duration_hours = (t["completed_at"] - t["created_at"]).total_seconds() / 3600.0
                    if duration_hours >= 0:
                        total_duration_hours += duration_hours
                        completed_durations_count += 1
            else:
                completed_false += 1

            if t["created_at"]:
                task_local_time = t["created_at"].astimezone(target_tz)
                day_name = DAYS_OF_WEEK[task_local_time.weekday()]
                weekday_distribution[day_name] += 1

            if t["title"]:
                words = re.findall(r'\b[a-zA-Zа-яА-ЯёЁ0-9]+\b', t["title"].lower())
                all_words.extend(words)

        avg_completion_time = (
            round(total_duration_hours / completed_durations_count, 2)
            if completed_durations_count > 0 else 0.0
        )

        word_counts = Counter(all_words).most_common(10)
        top_10_words = [{"word": word, "count": count} for word, count in word_counts]

        # 7. Формируем финальный словарь результата
        result_data = {
            "total_tasks": total_tasks,
            "status_distribution": {
                "completed": completed_true,
                "not_completed": completed_false
            },
            "average_completion_time_hours": avg_completion_time,
            "weekday_distribution": weekday_distribution,
            "top_10_words": top_10_words
        }

        await repo.set_job_done(job_id, result_data)

    except Exception as e:
        await repo.set_job_failed(job_id, str(e))
        raise e
    finally:
        await conn.close()


@celery_app.task(name="compute_analytics")
def compute_analytics_job(job_id: int):
    asyncio.run(_process_analytics(job_id))