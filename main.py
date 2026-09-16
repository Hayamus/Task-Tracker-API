import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from app.core.database import init_db, close_db
from app.core.metrics import PrometheusMiddleware
from app.api.monitoring import router as monitoring_router
from app.background.cleanup import run_cleanup_loop

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.teams import router as teams_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.admin import router as admin_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.attachments import router as attachments_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    
    cleanup_task = asyncio.create_task(run_cleanup_loop())
    
    yield
    
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
        
    await close_db()


app = FastAPI(
    title="Task Tracker API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(PrometheusMiddleware)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(teams_router)
app.include_router(tasks_router)
app.include_router(admin_router)
app.include_router(analytics_router)
app.include_router(attachments_router)
app.include_router(monitoring_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)