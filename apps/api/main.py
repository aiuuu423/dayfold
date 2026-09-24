import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.auth.cloudbase import (
    AuthProviderUnavailable,
    CloudBaseAuthAdapter,
    InvalidToken,
    TokenExpired,
)
from apps.api.auth.user_status import (
    CloudBaseHttpUserStatusStore,
    PostgresUserStatusStore,
    UserStatusStore,
    UserStatusStoreUnavailable,
)
from apps.api.chat import (
    ArkChatProvider,
    ChatProvider,
    ProviderUnavailable,
    SqliteChatRepository,
)
from apps.api.demo import DemoSettings
from apps.api.entries import EntryVersionConflict, SqliteEntryRepository
from apps.api.growth import (
    ArkGrowthProvider,
    GrowthProvider,
    GrowthProviderUnavailable,
    InvalidGrowthOutput,
    SqliteGrowthRepository,
    has_enough_evidence,
)
from apps.api.memory import (
    ArkMemoryExtractionProvider,
    InvalidModelOutput,
    MemoryExtractionProvider,
    MemoryProviderUnavailable,
    SqliteMemoryRepository,
)
from apps.api.provider_resilience import ProviderRequestError
from apps.api.retrieval import (
    ArkEmbeddingProvider,
    EmbeddingProvider,
    EmbeddingProviderUnavailable,
    InvalidEmbedding,
    SqliteVectorRepository,
)


DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:8000",
    "http://127.0.0.1:8000",
)

HEALTH_RESPONSE = {
    "status": "ok",
    "service": "dayfold-api",
    "environment": "preview",
    "version": "p1-probe",
}


def parse_allowed_origins(raw_origins: str | None) -> tuple[str, ...]:
    if not raw_origins:
        return DEFAULT_ALLOWED_ORIGINS

    origins = tuple(
        dict.fromkeys(origin.strip() for origin in raw_origins.split(",") if origin.strip())
    )
    if "*" in origins:
        raise ValueError("Wildcard CORS origins are not allowed")

    return origins


app = FastAPI(
    title="Dayfold API Preview",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_allowed_origins(os.getenv("DAYFOLD_ALLOWED_ORIGINS")),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Accept", "Authorization", "Content-Type", "If-Match"],
)


def get_auth_adapter() -> CloudBaseAuthAdapter | None:
    environment_id = os.getenv("DAYFOLD_CLOUDBASE_ENV_ID")
    if not environment_id:
        return None
    return CloudBaseAuthAdapter(environment_id)


def get_user_status_store() -> UserStatusStore | None:
    backend = os.getenv("DAYFOLD_USER_STATUS_BACKEND")
    database_url = os.getenv("DATABASE_URL")
    environment_id = os.getenv("DAYFOLD_CLOUDBASE_ENV_ID")

    if backend == "cloudbase_http":
        if not environment_id:
            return None
        return CloudBaseHttpUserStatusStore(environment_id)
    if backend == "postgres":
        if not database_url:
            return None
        return PostgresUserStatusStore(database_url)
    if backend is None and database_url:
        return PostgresUserStatusStore(database_url)
    return None


def get_demo_settings() -> DemoSettings | None:
    if os.getenv("DAYFOLD_DEMO_MODE", "").strip().lower() != "true":
        return None
    return DemoSettings()


def get_entry_repository() -> SqliteEntryRepository:
    database_path = os.getenv(
        "DAYFOLD_DATABASE_PATH",
        str(Path("local") / "dayfold-demo.sqlite3"),
    )
    return SqliteEntryRepository(database_path)


def get_chat_repository() -> SqliteChatRepository:
    database_path = os.getenv(
        "DAYFOLD_DATABASE_PATH",
        str(Path("local") / "dayfold-demo.sqlite3"),
    )
    return SqliteChatRepository(database_path)


def get_chat_provider() -> ChatProvider | None:
    api_key = os.getenv("DAYFOLD_LLM_API_KEY") or os.getenv("DAYFOLD_ARK_API_KEY")
    if not api_key:
        return None
    endpoint = os.getenv("DAYFOLD_LLM_ENDPOINT")
    if not endpoint:
        base_url = os.getenv(
            "DAYFOLD_ARK_BASE_URL",
            "https://ark.cn-beijing.volces.com/api/plan",
        ).rstrip("/")
        endpoint = (
            f"{base_url}/messages"
            if base_url.endswith("/v1")
            else f"{base_url}/v1/messages"
        )
    return ArkChatProvider(
        endpoint=endpoint,
        api_key=api_key,
        model=os.getenv("DAYFOLD_LLM_MODEL")
        or os.getenv("DAYFOLD_ARK_MODEL")
        or "doubao-seed-2-1-turbo",
    )


def get_memory_repository() -> SqliteMemoryRepository:
    database_path = os.getenv(
        "DAYFOLD_DATABASE_PATH",
        str(Path("local") / "dayfold-demo.sqlite3"),
    )
    return SqliteMemoryRepository(database_path)


def get_memory_provider() -> MemoryExtractionProvider | None:
    api_key = os.getenv("DAYFOLD_STANDARD_ARK_API_KEY")
    model = os.getenv("DAYFOLD_STANDARD_ARK_MODEL")
    if not api_key or not model:
        return None
    prompt_path = Path(__file__).parent / "prompts" / "memory_extraction_v0_4.md"
    return ArkMemoryExtractionProvider(
        endpoint=os.getenv(
            "DAYFOLD_STANDARD_ARK_ENDPOINT",
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        ),
        api_key=api_key,
        model=model,
        system_prompt=prompt_path.read_text(encoding="utf-8"),
    )


def get_vector_repository() -> SqliteVectorRepository:
    database_path = os.getenv(
        "DAYFOLD_DATABASE_PATH",
        str(Path("local") / "dayfold-demo.sqlite3"),
    )
    return SqliteVectorRepository(database_path)


def get_embedding_provider() -> EmbeddingProvider | None:
    api_key = os.getenv("DAYFOLD_EMBEDDING_API_KEY") or os.getenv(
        "DAYFOLD_STANDARD_ARK_API_KEY"
    )
    if not api_key:
        return None
    return ArkEmbeddingProvider(
        endpoint=os.getenv(
            "DAYFOLD_EMBEDDING_ENDPOINT",
            "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal",
        ),
        api_key=api_key,
        model=os.getenv(
            "DAYFOLD_EMBEDDING_MODEL",
            "doubao-embedding-vision-251215",
        ),
        dimensions=int(os.getenv("DAYFOLD_EMBEDDING_DIMENSIONS", "1024")),
    )


def get_growth_repository() -> SqliteGrowthRepository:
    database_path = os.getenv(
        "DAYFOLD_DATABASE_PATH",
        str(Path("local") / "dayfold-demo.sqlite3"),
    )
    return SqliteGrowthRepository(database_path)


def get_growth_provider() -> GrowthProvider | None:
    api_key = os.getenv("DAYFOLD_STANDARD_ARK_API_KEY")
    model = os.getenv("DAYFOLD_STANDARD_ARK_MODEL")
    if not api_key or not model:
        return None
    return ArkGrowthProvider(
        endpoint=os.getenv(
            "DAYFOLD_STANDARD_ARK_ENDPOINT",
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        ),
        api_key=api_key,
        model=model,
    )


class EntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=10_000)
    occurred_at: datetime

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Content must not be blank.")
        return value.strip()

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone.")
        return value


class EntryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Content must not be blank.")
        return value.strip()


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="新对话", min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must not be blank.")
        return value.strip()


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Content must not be blank.")
        return value.strip()


class MemoryExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["entry", "message"]
    source_id: str = Field(min_length=1, max_length=100)


class MemoryRetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must not be blank.")
        return value.strip()


class MemoryStatusPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["disabled"]


def auth_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def resource_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def provider_error_details(
    error: ProviderRequestError,
) -> tuple[int, str, str]:
    errors = {
        "authentication": (
            503,
            "LLM_AUTHENTICATION_FAILED",
            "The AI service authentication failed.",
        ),
        "rate_limited": (
            503,
            "LLM_RATE_LIMITED",
            "The AI service is temporarily rate limited.",
        ),
        "request_rejected": (
            502,
            "LLM_REQUEST_REJECTED",
            "The AI service rejected the request.",
        ),
        "timeout": (
            504,
            "LLM_TIMEOUT",
            "The AI service timed out.",
        ),
        "upstream": (
            502,
            "LLM_UPSTREAM_ERROR",
            "The AI service returned an upstream error.",
        ),
    }
    return errors.get(
        error.kind,
        (503, "LLM_UNAVAILABLE", "The AI service is unavailable."),
    )


def provider_error_response(error: ProviderRequestError) -> JSONResponse:
    status_code, code, message = provider_error_details(error)
    return resource_error(status_code, code, message)


def require_demo(settings: DemoSettings | None) -> JSONResponse | None:
    if settings is None:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return None


def sse_event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def build_memory_context(matches, minimum_score: float) -> tuple[str | None, list[dict]]:
    relevant = [match for match in matches if match.score >= minimum_score]
    if not relevant:
        return None, []
    context = "\n".join(
        (
            f"- memory_id={match.memory.id}; "
            f"type={match.memory.type}; "
            f"content={match.memory.content}"
        )
        for match in relevant
    )
    references = [
        {
            "id": match.memory.id,
            "type": match.memory.type,
            "score": round(match.score, 6),
        }
        for match in relevant
    ]
    return context, references


@app.get("/health")
def get_health() -> dict[str, str]:
    return HEALTH_RESPONSE


@app.get("/v1/demo")
def get_demo_info(
    settings: DemoSettings | None = Depends(get_demo_settings),
):
    if settings is None:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return settings.public_contract()


@app.post("/v1/entries", status_code=201)
async def create_entry(
    payload: EntryCreate,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteEntryRepository = Depends(get_entry_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    entry = await repository.create(
        settings.user_id,
        payload.content,
        payload.occurred_at.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    )
    return entry.public_view()


@app.get("/v1/entries")
async def list_entries(
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteEntryRepository = Depends(get_entry_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    entries = await repository.list(settings.user_id)
    return {"items": [entry.public_view() for entry in entries]}


@app.get("/v1/entries/{entry_id}")
async def get_entry(
    entry_id: str,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteEntryRepository = Depends(get_entry_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    entry = await repository.get(settings.user_id, entry_id)
    if entry is None:
        return resource_error(404, "RESOURCE_NOT_FOUND", "Resource was not found.")
    return entry.public_view()


@app.patch("/v1/entries/{entry_id}")
async def update_entry(
    entry_id: str,
    payload: EntryPatch,
    if_match: int = Header(alias="If-Match"),
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteEntryRepository = Depends(get_entry_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    try:
        entry = await repository.update(
            settings.user_id,
            entry_id,
            payload.content,
            expected_version=if_match,
        )
    except EntryVersionConflict:
        return resource_error(
            409,
            "VERSION_CONFLICT",
            "The entry has changed. Reload it and try again.",
        )
    if entry is None:
        return resource_error(404, "RESOURCE_NOT_FOUND", "Resource was not found.")
    return entry.public_view()


@app.delete("/v1/entries/{entry_id}", status_code=202)
async def delete_entry(
    entry_id: str,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteEntryRepository = Depends(get_entry_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    if not await repository.delete(settings.user_id, entry_id):
        return resource_error(404, "RESOURCE_NOT_FOUND", "Resource was not found.")
    return {"id": entry_id, "status": "deleted"}


@app.post("/v1/conversations", status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteChatRepository = Depends(get_chat_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    conversation = await repository.create_conversation(
        settings.user_id,
        payload.title,
    )
    return conversation.public_view()


@app.get("/v1/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteChatRepository = Depends(get_chat_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    if await repository.get_conversation(settings.user_id, conversation_id) is None:
        return resource_error(404, "RESOURCE_NOT_FOUND", "Resource was not found.")
    messages = await repository.list_messages(settings.user_id, conversation_id)
    return {"items": [message.public_view() for message in messages]}


@app.post("/v1/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: str,
    payload: MessageCreate,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteChatRepository = Depends(get_chat_repository),
    provider: ChatProvider | None = Depends(get_chat_provider),
    vector_repository: SqliteVectorRepository = Depends(get_vector_repository),
    embedding_provider: EmbeddingProvider | None = Depends(get_embedding_provider),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    if provider is None:
        return resource_error(
            503,
            "LLM_UNAVAILABLE",
            "The AI service is unavailable.",
        )
    if await repository.get_conversation(settings.user_id, conversation_id) is None:
        return resource_error(404, "RESOURCE_NOT_FOUND", "Resource was not found.")

    memory_context = None
    recalled_memories: list[dict] = []
    if embedding_provider is not None:
        try:
            unembedded = await vector_repository.list_unembedded(
                settings.user_id,
                embedding_provider.model,
                embedding_provider.dimensions,
            )
            if unembedded:
                memory_vectors = await embedding_provider.embed(
                    [memory.content for memory in unembedded]
                )
                await vector_repository.store_many(
                    settings.user_id,
                    unembedded,
                    memory_vectors,
                    embedding_provider.model,
                    embedding_provider.dimensions,
                )
            query_vectors = await embedding_provider.embed([payload.content])
            matches = await vector_repository.search(
                settings.user_id,
                query_vectors[0],
                embedding_provider.model,
                embedding_provider.dimensions,
                limit=3,
            )
            minimum_score = float(os.getenv("DAYFOLD_RECALL_MIN_SCORE", "0.30"))
            memory_context, recalled_memories = build_memory_context(
                matches,
                minimum_score,
            )
        except EmbeddingProviderUnavailable:
            return resource_error(
                503,
                "EMBEDDING_UNAVAILABLE",
                "Memory recall is unavailable.",
            )
        except (InvalidEmbedding, IndexError, ValueError):
            return resource_error(
                502,
                "INVALID_EMBEDDING",
                "Memory recall returned an invalid vector.",
            )

    user_message = await repository.add_message(
        settings.user_id,
        conversation_id,
        "user",
        payload.content,
    )
    if user_message is None:
        return resource_error(404, "RESOURCE_NOT_FOUND", "Resource was not found.")
    history = await repository.list_messages(settings.user_id, conversation_id)
    provider_messages = [
        {"role": message.role, "content": message.content}
        for message in history
    ]

    async def generate():
        yield sse_event(
            "message.start",
            {
                "conversation_id": conversation_id,
                "user_message_id": user_message.id,
                "recalled_memories": recalled_memories,
            },
        )
        chunks: list[str] = []
        try:
            async for chunk in provider.stream(provider_messages, memory_context):
                chunks.append(chunk)
                yield sse_event("message.delta", {"text": chunk})
        except ProviderUnavailable as error:
            _, code, message = provider_error_details(error)
            yield sse_event(
                "message.error",
                {
                    "code": code,
                    "message": message,
                },
            )
            return

        assistant_message = await repository.add_message(
            settings.user_id,
            conversation_id,
            "assistant",
            "".join(chunks),
        )
        if assistant_message is None:
            yield sse_event(
                "message.error",
                {
                    "code": "PERSISTENCE_ERROR",
                    "message": "The response could not be saved.",
                },
            )
            return
        yield sse_event("message.done", assistant_message.public_view())

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/v1/memory-extractions", status_code=201)
async def extract_memories(
    payload: MemoryExtractionRequest,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteMemoryRepository = Depends(get_memory_repository),
    provider: MemoryExtractionProvider | None = Depends(get_memory_provider),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    if provider is None:
        return resource_error(
            503,
            "LLM_UNAVAILABLE",
            "The AI service is unavailable.",
        )
    source_content = await repository.get_source_content(
        settings.user_id,
        payload.source_type,
        payload.source_id,
    )
    if source_content is None:
        return resource_error(404, "RESOURCE_NOT_FOUND", "Resource was not found.")
    try:
        operations = await provider.extract(source_content)
        memories = await repository.store_extraction(
            settings.user_id,
            payload.source_type,
            payload.source_id,
            operations,
        )
    except MemoryProviderUnavailable as error:
        return provider_error_response(error)
    except InvalidModelOutput:
        return resource_error(
            502,
            "INVALID_MODEL_OUTPUT",
            "The AI service returned an invalid result.",
        )
    return {
        "source": {"type": payload.source_type, "id": payload.source_id},
        "memories": [memory.public_view() for memory in memories],
    }


@app.get("/v1/memories")
async def list_memories(
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteMemoryRepository = Depends(get_memory_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    memories = await repository.list(settings.user_id)
    return {"items": [memory.public_view() for memory in memories]}


@app.get("/v1/memories/{memory_id}")
async def get_memory(
    memory_id: str,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteMemoryRepository = Depends(get_memory_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    memory = await repository.get(settings.user_id, memory_id)
    if memory is None:
        return resource_error(404, "RESOURCE_NOT_FOUND", "Resource was not found.")
    view = memory.public_view()
    view["sources"] = await repository.list_sources(settings.user_id, memory_id)
    return view


@app.patch("/v1/memories/{memory_id}")
async def disable_memory(
    memory_id: str,
    payload: MemoryStatusPatch,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteMemoryRepository = Depends(get_memory_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    memory = await repository.disable(settings.user_id, memory_id)
    if memory is None:
        return resource_error(404, "RESOURCE_NOT_FOUND", "Resource was not found.")
    view = memory.public_view()
    view["sources"] = await repository.list_sources(settings.user_id, memory_id)
    return view


@app.delete("/v1/memories/{memory_id}", status_code=202)
async def delete_memory(
    memory_id: str,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteMemoryRepository = Depends(get_memory_repository),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    if not await repository.delete(settings.user_id, memory_id):
        return resource_error(404, "RESOURCE_NOT_FOUND", "Resource was not found.")
    return {"id": memory_id, "status": "deleted"}


@app.post("/v1/memory-embeddings/sync")
async def sync_memory_embeddings(
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteVectorRepository = Depends(get_vector_repository),
    provider: EmbeddingProvider | None = Depends(get_embedding_provider),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    if provider is None:
        return resource_error(
            503,
            "EMBEDDING_UNAVAILABLE",
            "The embedding service is unavailable.",
        )
    memories = await repository.list_unembedded(
        settings.user_id,
        provider.model,
        provider.dimensions,
    )
    if not memories:
        return {"embedded": 0}
    try:
        vectors = await provider.embed([memory.content for memory in memories])
        await repository.store_many(
            settings.user_id,
            memories,
            vectors,
            provider.model,
            provider.dimensions,
        )
    except EmbeddingProviderUnavailable:
        return resource_error(
            503,
            "EMBEDDING_UNAVAILABLE",
            "The embedding service is unavailable.",
        )
    except InvalidEmbedding:
        return resource_error(
            502,
            "INVALID_EMBEDDING",
            "The embedding service returned an invalid vector.",
        )
    return {"embedded": len(memories)}


@app.post("/v1/memory-retrievals")
async def retrieve_memories(
    payload: MemoryRetrievalRequest,
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteVectorRepository = Depends(get_vector_repository),
    provider: EmbeddingProvider | None = Depends(get_embedding_provider),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    if provider is None:
        return resource_error(
            503,
            "EMBEDDING_UNAVAILABLE",
            "The embedding service is unavailable.",
        )
    try:
        query_vectors = await provider.embed([payload.query])
        query_vector = query_vectors[0]
        matches = await repository.search(
            settings.user_id,
            query_vector,
            provider.model,
            provider.dimensions,
            payload.limit,
        )
    except EmbeddingProviderUnavailable:
        return resource_error(
            503,
            "EMBEDDING_UNAVAILABLE",
            "The embedding service is unavailable.",
        )
    except (InvalidEmbedding, IndexError):
        return resource_error(
            502,
            "INVALID_EMBEDDING",
            "The embedding service returned an invalid vector.",
        )
    return {"items": [match.public_view() for match in matches]}


@app.get("/v1/growth/current")
async def get_current_growth(
    settings: DemoSettings | None = Depends(get_demo_settings),
    repository: SqliteGrowthRepository = Depends(get_growth_repository),
    provider: GrowthProvider | None = Depends(get_growth_provider),
):
    unavailable = require_demo(settings)
    if unavailable:
        return unavailable
    evidence = await repository.collect_evidence(settings.user_id)
    if not has_enough_evidence(evidence):
        return {
            "status": "collecting",
            "content": "正在积累你的记录。",
            "evidence": [],
        }
    if provider is None:
        return resource_error(
            503,
            "LLM_UNAVAILABLE",
            "Growth insight is unavailable.",
        )
    try:
        content = await provider.generate(evidence)
        summary = await repository.store(
            settings.user_id,
            content,
            evidence,
        )
    except GrowthProviderUnavailable as error:
        return provider_error_response(error)
    except InvalidGrowthOutput:
        return resource_error(
            502,
            "INVALID_GROWTH_OUTPUT",
            "The AI service returned an invalid growth insight.",
        )
    return summary.public_view()


@app.get("/v1/auth/probe")
async def get_auth_probe(
    authorization: str | None = Header(default=None),
    adapter: CloudBaseAuthAdapter | None = Depends(get_auth_adapter),
    user_status_store: UserStatusStore | None = Depends(get_user_status_store),
):
    if not authorization:
        return auth_error(401, "INVALID_TOKEN", "Authentication is required.")

    scheme, separator, token = authorization.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not token
        or token != token.strip()
        or " " in token
    ):
        return auth_error(401, "INVALID_TOKEN", "Authentication is required.")
    if adapter is None:
        return auth_error(
            503,
            "AUTH_PROVIDER_UNAVAILABLE",
            "Authentication provider is unavailable.",
        )

    try:
        identity = await adapter.verify_access_token(token)
    except (InvalidToken, TokenExpired):
        return auth_error(401, "INVALID_TOKEN", "Authentication is required.")
    except AuthProviderUnavailable:
        return auth_error(
            503,
            "AUTH_PROVIDER_UNAVAILABLE",
            "Authentication provider is unavailable.",
        )

    if user_status_store is None:
        return auth_error(
            503,
            "USER_STATUS_UNAVAILABLE",
            "User status is unavailable.",
        )
    try:
        user_status = await user_status_store.get_status(
            identity.auth_subject,
            token,
        )
    except UserStatusStoreUnavailable:
        return auth_error(
            503,
            "USER_STATUS_UNAVAILABLE",
            "User status is unavailable.",
        )
    if user_status != "active":
        return auth_error(401, "INVALID_TOKEN", "Authentication is required.")

    return {"status": "authenticated"}
