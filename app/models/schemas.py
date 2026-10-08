
from pydantic import BaseModel, Field


class MemorySearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(10, ge=1, le=100, description="Maximum results")
    search_type: str = Field("hybrid", description="keyword, vector, or hybrid")


class MemorySearchResult(BaseModel):
    file_path: str
    content: str
    score: float
    metadata: dict = {}


class MemorySearchResponse(BaseModel):
    results: list[MemorySearchResult]
    total: int
    query: str


class MemoryGetRequest(BaseModel):
    file_path: str


class MemoryGetResponse(BaseModel):
    file_path: str
    content: str
    metadata: dict = {}


class MemoryRecordRequest(BaseModel):
    file_path: str
    content: str
    commit_message: str | None = None


class MemoryRecordResponse(BaseModel):
    file_path: str
    commit_hash: str
    message: str


class MemoryUpdateRequest(BaseModel):
    file_path: str
    content: str
    commit_message: str | None = None


class MemoryUpdateResponse(BaseModel):
    file_path: str
    commit_hash: str
    message: str


class MemoryCorrectRequest(BaseModel):
    file_path: str
    old_content: str = Field(..., min_length=3, description="Text to replace (must not be empty)")
    new_content: str
    commit_message: str | None = None


class MemoryCorrectResponse(BaseModel):
    file_path: str
    commit_hash: str
    message: str


class MemoryArchiveRequest(BaseModel):
    file_path: str
    commit_message: str | None = None


class MemoryArchiveResponse(BaseModel):
    file_path: str
    commit_hash: str
    message: str


class MemoryListRelatedRequest(BaseModel):
    file_path: str
    limit: int = Field(5, ge=1, le=20)


class MemoryListRelatedResponse(BaseModel):
    related: list[MemorySearchResult]


class IndexRebuildRequest(BaseModel):
    force: bool = False


class IndexRebuildResponse(BaseModel):
    status: str
    files_indexed: int
    message: str


class HealthResponse(BaseModel):
    status: str
    service: str
    git_repo: str
    chroma_connected: bool
