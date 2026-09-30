"""PostgreSQL-backed acceptance coverage for Markdown source ingestion."""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, inspect, text

from probeinterview.entrypoints.api import create_app
from probeinterview.entrypoints.profile_seed import DEMO_USER_ID, seed_demo_profile
from probeinterview.identity.access.domain.context import ActorContext
from probeinterview.knowledge.source.application.errors import (
    DailyUploadLimitReached,
    EffectiveSourceLimitReached,
)
from probeinterview.knowledge.source.application.service import KnowledgeSourceService
from probeinterview.knowledge.source.infrastructure.repository import (
    SqlAlchemyKnowledgeSourceRepository,
)
from probeinterview.knowledge.source.infrastructure.storage import FakeObjectStorage
from probeinterview.platform.foundation.infrastructure.persistence import (
    create_engine,
    create_session_factory,
)
from probeinterview.platform.foundation.infrastructure.settings import Settings

pytestmark = pytest.mark.asyncio

BACKEND_ROOT = Path(__file__).resolve().parents[3]
SECOND_ACTOR_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e3001")


def isolated_database_url() -> str:
    database_url = os.getenv("PROBEINTERVIEW_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("run through scripts/test-knowledge-source-postgres")
    if os.getenv("PROBEINTERVIEW_DESTRUCTIVE_DATABASE_TEST") != "1":
        raise RuntimeError("destructive database test sentinel is required")
    if "/probeinterview_knowledge_source_test_" not in database_url:
        raise RuntimeError("refusing to migrate a non-isolated database")
    return database_url


@pytest.fixture(scope="module")
def knowledge_database() -> Iterator[tuple[str, Engine]]:
    database_url = isolated_database_url()
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "20260929_0001")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into users (id, nickname, avatar_url)
                values
                    (:demo_id, 'Preexisting Demo', 'https://example.invalid/demo.png'),
                    (:second_id, 'Second Actor', 'https://example.invalid/second.png')
                """
            ),
            {"demo_id": DEMO_USER_ID, "second_id": SECOND_ACTOR_ID},
        )
    command.upgrade(config, "head")
    seed_demo_profile(engine)
    try:
        yield database_url, engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")
        verification_engine = create_engine(database_url)
        try:
            assert "knowledge_sources" not in inspect(verification_engine).get_table_names()
            assert "users" not in inspect(verification_engine).get_table_names()
        finally:
            verification_engine.dispose()


@pytest.fixture(autouse=True)
def clean_sources(knowledge_database: tuple[str, Engine]) -> Iterator[None]:
    engine = knowledge_database[1]
    with engine.begin() as connection:
        connection.execute(text("delete from knowledge_sources"))
        connection.execute(
            text(
                """
                update knowledge_upload_policies
                set daily_success_limit = 2,
                    effective_source_limit = 100,
                    quota_timezone = 'Asia/Shanghai'
                """
            )
        )
    yield


async def test_migration_seed_and_private_upload_contract(
    knowledge_database: tuple[str, Engine],
) -> None:
    database_url, engine = knowledge_database
    tables = set(inspect(engine).get_table_names())
    assert {
        "user_capabilities",
        "knowledge_upload_policies",
        "knowledge_sources",
        "knowledge_source_versions",
    } <= tables
    seed_demo_profile(engine)
    seed_demo_profile(engine)
    with engine.connect() as connection:
        policy = connection.execute(
            text(
                """
                select daily_success_limit, effective_source_limit, quota_timezone
                from knowledge_upload_policies
                where user_id = :actor_id
                """
            ),
            {"actor_id": DEMO_USER_ID},
        ).one()
        capability_count = connection.scalar(
            text(
                """
                select count(*)
                from user_capabilities
                where user_id = :actor_id
                  and capability = 'knowledge.submit_public'
                """
            ),
            {"actor_id": DEMO_USER_ID},
        )
    assert tuple(policy) == (2, 100, "Asia/Shanghai")
    assert capability_count == 1

    async with api_client(database_url, DEMO_USER_ID) as (client, storage):
        accepted = await client.post(
            "/api/v1/me/knowledge-sources",
            headers={"Idempotency-Key": "private-upload-1"},
            data={"original_filename": "用户选择的笔记.md"},
            files={"file": ("wx-temp-hash.md", b"# Notes", "text/plain")},
        )
        replay = await client.post(
            "/api/v1/me/knowledge-sources",
            headers={"Idempotency-Key": "private-upload-1"},
            data={"original_filename": "用户选择的笔记.md"},
            files={
                "file": (
                    "another-wx-temp-hash.md",
                    b"# Notes",
                    "application/octet-stream",
                )
            },
        )
        duplicate = await client.post(
            "/api/v1/me/knowledge-sources",
            headers={"Idempotency-Key": "private-upload-2"},
            data={"original_filename": "用户选择的笔记.md"},
            files={"file": ("third-wx-temp-hash.md", b"# Notes", "text/markdown")},
        )
        conflict = await client.post(
            "/api/v1/me/knowledge-sources",
            headers={"Idempotency-Key": "private-upload-1"},
            data={"original_filename": "用户选择的笔记.md"},
            files={"file": ("wx-temp-hash.md", b"# Different", "text/markdown")},
        )
        collection = await client.get("/api/v1/me/knowledge-sources")

    assert accepted.status_code == 202
    assert accepted.headers["location"] == "/api/v1/me/knowledge-sources"
    body = accepted.json()
    assert body["source"]["original_filename"] == "用户选择的笔记.md"
    assert body["source"]["scope"] == "PRIVATE"
    assert body["source"]["processing_status"] == "PENDING_EXTRACTION"
    assert body["quota"] == {
        "timezone": "Asia/Shanghai",
        "daily_limit": 2,
        "daily_used": 1,
        "effective_source_limit": 100,
        "effective_source_count": 1,
    }
    assert replay.json() == body
    assert duplicate.json() == body
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
    assert [call.operation for call in storage.calls] == ["put"]
    assert collection.status_code == 200
    assert collection.json() == {"quota": body["quota"], "items": [body["source"]]}
    forbidden = {
        "object_key",
        "content_sha256",
        "url",
        "provider",
        "access_key",
        "credentials",
    }
    assert forbidden.isdisjoint(body["source"])
    assert forbidden.isdisjoint(collection.json()["items"][0])


async def test_validation_storage_failure_and_exact_size_do_not_consume_quota(
    knowledge_database: tuple[str, Engine],
) -> None:
    database_url, engine = knowledge_database
    async with api_client(database_url, DEMO_USER_ID) as (client, storage):
        invalid_requests = [
            {"files": {"file": ("notes.txt", b"text", "text/plain")}},
            {"files": {"file": ("notes.md", b"", "text/markdown")}},
            {"files": {"file": ("notes.md", b"\xff", "text/markdown")}},
            {"files": {"file": ("notes.md", b"a\x00b", "text/markdown")}},
            {"files": {"file": ("notes.md", b"a" * (500 * 1024), "text/markdown")}},
            {
                "files": {"file": ("notes.md", b"valid", "text/markdown")},
                "data": {"scope": "FRIENDS"},
            },
            {
                "files": {"file": ("wx-temp-hash.md", b"valid", "text/markdown")},
                "data": {"original_filename": "../not-markdown.txt"},
            },
        ]
        for index, kwargs in enumerate(invalid_requests):
            response = await client.post(
                "/api/v1/me/knowledge-sources",
                headers={"Idempotency-Key": f"invalid-{index}"},
                **kwargs,
            )
            assert response.status_code in {400, 413}
            assert response.headers["content-type"] == "application/problem+json"
            if index == len(invalid_requests) - 1:
                assert response.json()["errors"][0]["field"] == "original_filename"
        storage.fail_put = True
        storage_failure = await client.post(
            "/api/v1/me/knowledge-sources",
            headers={"Idempotency-Key": "storage-failure"},
            files={"file": ("valid.md", b"# valid", "text/markdown")},
        )
        collection = await client.get("/api/v1/me/knowledge-sources")

    assert storage_failure.status_code == 503
    assert storage_failure.json()["code"] == "object_storage_unavailable"
    assert collection.json()["quota"]["daily_used"] == 0
    assert collection.json()["quota"]["effective_source_count"] == 0
    assert collection.json()["items"] == []
    assert storage.objects == {}
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    """
                select count(*) from knowledge_sources
                where ingestion_status = 'FAILED'
                """
                )
            )
            == 1
        )


async def test_public_capability_owner_isolation_ordering_and_quota_problem(
    knowledge_database: tuple[str, Engine],
) -> None:
    database_url, engine = knowledge_database
    async with (
        api_client(database_url, DEMO_USER_ID) as (owner_client, _owner_storage),
        api_client(database_url, SECOND_ACTOR_ID) as (other_client, other_storage),
    ):
        public_response = await owner_client.post(
            "/api/v1/me/knowledge-sources",
            headers={"Idempotency-Key": "public-1"},
            data={"scope": "PUBLIC"},
            files={"file": ("same.md", b"# Same", "text/markdown")},
        )
        private_response = await owner_client.post(
            "/api/v1/me/knowledge-sources",
            headers={"Idempotency-Key": "private-1"},
            data={"scope": "PRIVATE"},
            files={"file": ("same.md", b"# Same", "text/markdown")},
        )
        forbidden = await other_client.post(
            "/api/v1/me/knowledge-sources",
            headers={"Idempotency-Key": "forbidden-public"},
            data={"scope": "PUBLIC"},
            files={"file": ("other.md", b"# Other", "text/markdown")},
        )
        other_collection = await other_client.get("/api/v1/me/knowledge-sources")

        with engine.begin() as connection:
            common_time = datetime(2026, 9, 30, 6, 0, tzinfo=UTC)
            connection.execute(
                text(
                    """
                    update knowledge_sources
                    set stored_at = :stored_at
                    where owner_user_id = :actor_id
                    """
                ),
                {"stored_at": common_time, "actor_id": DEMO_USER_ID},
            )
        owner_collection = await owner_client.get("/api/v1/me/knowledge-sources")
        exhausted = await owner_client.post(
            "/api/v1/me/knowledge-sources",
            headers={"Idempotency-Key": "third-unique"},
            files={"file": ("third.md", b"# Third", "text/markdown")},
        )

    assert public_response.status_code == 202
    assert private_response.status_code == 202
    assert public_response.json()["source"]["id"] != private_response.json()["source"]["id"]
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "public_knowledge_source_forbidden"
    assert other_storage.calls == []
    assert other_collection.json()["items"] == []
    assert other_collection.json()["quota"]["daily_used"] == 0
    items = owner_collection.json()["items"]
    assert {item["scope"] for item in items} == {"PRIVATE", "PUBLIC"}
    assert [item["id"] for item in items] == sorted(
        (item["id"] for item in items),
        reverse=True,
    )
    assert exhausted.status_code == 429
    assert exhausted.json()["code"] == "daily_upload_limit_reached"
    assert exhausted.json()["quota"]["daily_used"] == 2


@pytest.mark.parametrize(
    ("daily_limit", "effective_limit", "expected_error"),
    [
        (1, 10, DailyUploadLimitReached),
        (10, 1, EffectiveSourceLimitReached),
    ],
)
async def test_concurrent_uploads_cannot_exceed_last_database_slot(
    knowledge_database: tuple[str, Engine],
    daily_limit: int,
    effective_limit: int,
    expected_error: type[Exception],
) -> None:
    database_url, engine = knowledge_database
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                update knowledge_upload_policies
                set daily_success_limit = :daily_limit,
                    effective_source_limit = :effective_limit
                where user_id = :actor_id
                """
            ),
            {
                "daily_limit": daily_limit,
                "effective_limit": effective_limit,
                "actor_id": SECOND_ACTOR_ID,
            },
        )
    session_factory = create_session_factory(engine)
    storage = FakeObjectStorage()
    service = KnowledgeSourceService(
        repository=SqlAlchemyKnowledgeSourceRepository(session_factory),
        storage=storage,
        clock=lambda: datetime(2026, 9, 30, 6, 0, tzinfo=UTC),
    )
    actor = ActorContext(actor_id=SECOND_ACTOR_ID, capabilities=frozenset())

    def upload(index: int) -> str:
        try:
            service.upload(
                actor=actor,
                filename=f"source-{index}.md",
                content=f"# source {index}".encode(),
                scope_value="PRIVATE",
                idempotency_key=f"concurrent-{daily_limit}-{effective_limit}-{index}",
            )
        except Exception as error:
            assert isinstance(error, expected_error)
            return "rejected"
        return "stored"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(upload, (1, 2)))

    assert sorted(outcomes) == ["rejected", "stored"]
    with engine.connect() as connection:
        counts = connection.execute(
            text(
                """
                select
                    count(*) filter (where ingestion_status = 'STORED'),
                    count(*) filter (where ingestion_status = 'UPLOADING')
                from knowledge_sources
                where owner_user_id = :actor_id
                """
            ),
            {"actor_id": SECOND_ACTOR_ID},
        ).one()
    assert tuple(counts) == (1, 0)
    assert len(storage.objects) == 1


@pytest.fixture
async def unused_fixture() -> None:
    """Keep pytest-asyncio in strict mode from treating helpers as fixtures."""


class ClientContext:
    def __init__(self, database_url: str, actor_id: UUID) -> None:
        self.settings = Settings(
            environment="test",
            database_url=database_url,
            celery_broker_url="redis://127.0.0.1:1/0",
            local_actor_enabled=True,
            local_actor_id=actor_id,
            object_storage_adapter="fake",
            _env_file=None,
        )
        self.app = create_app(self.settings, readiness_checks={})
        self.transport = ASGITransport(app=self.app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")

    async def __aenter__(self) -> tuple[AsyncClient, FakeObjectStorage]:
        await self.client.__aenter__()
        storage = self.app.state.object_storage
        assert isinstance(storage, FakeObjectStorage)
        return self.client, storage

    async def __aexit__(self, *args: object) -> None:
        await self.client.__aexit__(*args)
        self.app.state.persistence_engine.dispose()


def api_client(database_url: str, actor_id: UUID) -> ClientContext:
    return ClientContext(database_url, actor_id)
