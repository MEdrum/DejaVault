import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import settings
from app.services.memory_service import MemoryService

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DejaVault...")
    memory_service = MemoryService(
        repo_path=settings.MEMORY_REPO_PATH,
        chroma_path=settings.CHROMA_DB_PATH
    )
    await memory_service.initialize()
    app.state.memory_service = memory_service
    logger.info("DejaVault started")
    yield
    logger.info("Shutting down DejaVault...")

app = FastAPI(
    title="DejaVault",
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
    return {"status": "healthy", "service": "dejavault"}

# Serve the browser UI at the root (must be last so it doesn't shadow API routes)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
