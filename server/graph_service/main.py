from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from graph_service.config import get_settings
from graph_service.routers import ingest, retrieve
from graph_service.routers.ingest import async_worker  # FIX: Import async_worker
from graph_service.zep_graphiti import initialize_graphiti


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    await initialize_graphiti(settings)

    # FIX: Start async worker here instead of router lifespan (which never executes)
    print("Starting async worker from main app lifespan...")
    await async_worker.start()
    print("Async worker started successfully!")

    yield

    # FIX: Stop async worker on shutdown
    print("Stopping async worker...")
    await async_worker.stop()
    print("Async worker stopped.")


app = FastAPI(lifespan=lifespan)


app.include_router(retrieve.router)
app.include_router(ingest.router)


@app.get('/healthcheck')
async def healthcheck():
    return JSONResponse(content={'status': 'healthy'}, status_code=200)
