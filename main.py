import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from app.core.database import init_db, close_db
from app.background.cleanup import run_cleanup_loop

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.teams import router as teams_router
from app.api.v1.tasks import router as tasks_router


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

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(teams_router)
app.include_router(tasks_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)