
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.schemas import (
    HealthResponse,
    IndexRebuildRequest,
    IndexRebuildResponse,
    MemoryArchiveRequest,
    MemoryArchiveResponse,
    MemoryCorrectRequest,
    MemoryCorrectResponse,
    MemoryGetRequest,
    MemoryGetResponse,
    MemoryListRelatedRequest,
    MemoryListRelatedResponse,
    MemoryRecordRequest,
    MemoryRecordResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryUpdateRequest,
    MemoryUpdateResponse,
)
from app.services.memory_service import MemoryService

router = APIRouter()


def get_memory_service(request: Request) -> MemoryService:
    if not hasattr(request.app.state, "memory_service") or request.app.state.memory_service is None:
        raise HTTPException(status_code=503, detail="Memory service not initialized")
    return request.app.state.memory_service


ServiceDep = Annotated[MemoryService, Depends(get_memory_service)]


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    svc = get_memory_service(request)
    return svc.health_check()


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(request: MemorySearchRequest, svc: ServiceDep):
    results = svc.search(request.query, request.limit, request.search_type)
    return MemorySearchResponse(results=results, total=len(results), query=request.query)


@router.post("/get", response_model=MemoryGetResponse)
async def get_memory(request: MemoryGetRequest, svc: ServiceDep):
    result = svc.get(request.file_path)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Memory file not found: {request.file_path}")
    return MemoryGetResponse(**result)


@router.post("/record", response_model=MemoryRecordResponse)
async def record_memory(request: MemoryRecordRequest, svc: ServiceDep):
    try:
        result = svc.record(request.file_path, request.content, request.commit_message)
        return MemoryRecordResponse(**result)
    except Exception as e:  # noqa: BLE001 - API error boundary
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update", response_model=MemoryUpdateResponse)
async def update_memory(request: MemoryUpdateRequest, svc: ServiceDep):
    try:
        result = svc.update(request.file_path, request.content, request.commit_message)
        return MemoryUpdateResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001 - API error boundary
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correct", response_model=MemoryCorrectResponse)
async def correct_memory(request: MemoryCorrectRequest, svc: ServiceDep):
    try:
        result = svc.correct(request.file_path, request.old_content, request.new_content, request.commit_message)
        return MemoryCorrectResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001 - API error boundary
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archive", response_model=MemoryArchiveResponse)
async def archive_memory(request: MemoryArchiveRequest, svc: ServiceDep):
    try:
        result = svc.archive(request.file_path, request.commit_message)
        return MemoryArchiveResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001 - API error boundary
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/related", response_model=MemoryListRelatedResponse)
async def list_related(request: MemoryListRelatedRequest, svc: ServiceDep):
    related = svc.list_related(request.file_path, request.limit)
    return MemoryListRelatedResponse(related=related)


@router.post("/rebuild-index", response_model=IndexRebuildResponse)
async def rebuild_index(request: IndexRebuildRequest, svc: ServiceDep):
    try:
        result = await svc.rebuild_index(request.force)
        return IndexRebuildResponse(**result, message=f"Indexed {result['files_indexed']} files")
    except Exception as e:  # noqa: BLE001 - API error boundary
        raise HTTPException(status_code=500, detail=str(e))