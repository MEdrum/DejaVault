from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.api.routes import router as api_router
from app.services.memory_service import MemoryService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Agent Memory Service...")
    memory_service = MemoryService(
        repo_path=settings.MEMORY_REPO_PATH,
        chroma_path=settings.CHROMA_DB_PATH
    )
    await memory_service.initialize()
    app.state.memory_service = memory_service
    logger.info("Agent Memory Service started")
    yield
    logger.info("Shutting down Agent Memory Service...")

app = FastAPI(
    title="Agent Memory Service",
    description="Memory service with Markdown Git repository and vector search",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agent-memory"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
