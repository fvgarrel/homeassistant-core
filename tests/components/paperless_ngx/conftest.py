"""Common fixtures for the Paperless-ngx tests."""

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from pypaperless.models import Document, RemoteVersion, Statistic, Status
import pytest

from homeassistant.components.paperless_ngx.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import ENTITY_ID_TODO, USER_INPUT_ONE

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)
from tests.conftest import WebSocketGenerator


@pytest.fixture
def mock_status_data() -> Generator[MagicMock]:
    """Return test status data."""
    return load_json_object_fixture("test_data_status.json", DOMAIN)


@pytest.fixture
def mock_remote_version_data() -> Generator[MagicMock]:
    """Return test remote version data."""
    return load_json_object_fixture("test_data_remote_version.json", DOMAIN)


@pytest.fixture
def mock_remote_version_data_unavailable() -> Generator[MagicMock]:
    """Return test remote version data."""
    return load_json_object_fixture("test_data_remote_version_unavailable.json", DOMAIN)


@pytest.fixture
def mock_statistic_data() -> Generator[MagicMock]:
    """Return test statistic data."""
    return load_json_object_fixture("test_data_statistic.json", DOMAIN)


@pytest.fixture
def mock_statistic_data_update() -> Generator[MagicMock]:
    """Return updated test statistic data."""
    return load_json_object_fixture("test_data_statistic_update.json", DOMAIN)


@pytest.fixture
def mock_inbox_documents() -> Generator[MagicMock]:
    """Return inbox documents data."""
    return load_json_array_fixture("test_data_inbox_documents.json", DOMAIN)


@asynccontextmanager
async def mock_reduce_context_manager(
    documents: list[Document],
) -> AsyncGenerator[MagicMock]:
    """Mock an async context manager that yields an async iterable."""

    class AsyncIterator:
        def __init__(self, items) -> None:
            self._items = items
            self._iter = iter(self._items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    yield AsyncIterator(documents)


def create_mock_reduce(
    paperless: AsyncMock,
    documents_data: list[dict],
) -> MagicMock:
    """Create a mock for the reduce method of the Paperless client."""
    documents = [
        Document.create_with_data(paperless, data=doc_data, fetched=True)
        for doc_data in documents_data
    ]
    return MagicMock(
        side_effect=lambda **kwargs: mock_reduce_context_manager(documents)
    )


@pytest.fixture
def mock_document(mock_inbox_documents: list[dict[str, str]]) -> Document:
    """Create a mock Document instance with the given data."""
    document = Document.create_with_data(
        MagicMock(),
        data=mock_inbox_documents[0],
        fetched=True,
    )
    document.update = AsyncMock()
    return document


@pytest.fixture
async def get_todo_items(
    hass_ws_client: WebSocketGenerator,
) -> Callable[[], Awaitable[dict[str, str]]]:
    """Fixture to fetch items from the todo websocket."""

    async def get() -> list[dict[str, str]]:
        # Fetch items using To-do platform
        client = await hass_ws_client()
        await client.send_json_auto_id(
            {
                "id": id,
                "type": "todo/item/list",
                "entity_id": ENTITY_ID_TODO,
            }
        )
        resp = await client.receive_json()
        assert resp.get("success")
        return resp.get("result", {}).get("items", [])

    return get


@pytest.fixture(autouse=True)
def mock_paperless(
    mock_statistic_data: MagicMock,
    mock_status_data: MagicMock,
    mock_remote_version_data: MagicMock,
    mock_document: Document,
    mock_inbox_documents: MagicMock,
) -> Generator[AsyncMock]:
    """Mock the pypaperless.Paperless client."""
    with (
        patch(
            "homeassistant.components.paperless_ngx.coordinator.Paperless",
            autospec=True,
        ) as paperless_mock,
        patch(
            "homeassistant.components.paperless_ngx.config_flow.Paperless",
            new=paperless_mock,
        ),
        patch(
            "homeassistant.components.paperless_ngx.Paperless",
            new=paperless_mock,
        ),
    ):
        paperless = paperless_mock.return_value

        paperless.base_url = "http://paperless.example.com/"
        paperless.host_version = "2.3.0"
        paperless.initialize.return_value = None
        paperless.statistics = AsyncMock(
            return_value=Statistic.create_with_data(
                paperless, data=mock_statistic_data, fetched=True
            )
        )
        paperless.status = AsyncMock(
            return_value=Status.create_with_data(
                paperless, data=mock_status_data, fetched=True
            )
        )
        paperless.remote_version = AsyncMock(
            return_value=RemoteVersion.create_with_data(
                paperless, data=mock_remote_version_data, fetched=True
            )
        )

        paperless.documents = AsyncMock(return_value=mock_document)
        paperless.documents.reduce = create_mock_reduce(paperless, mock_inbox_documents)

        yield paperless


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="0KLG00V55WEVTJ0CJHM0GADNGH",
        title="Paperless-ngx",
        domain=DOMAIN,
        data=USER_INPUT_ONE,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_paperless: MagicMock
) -> MockConfigEntry:
    """Set up the Paperless-ngx integration for testing."""
    await setup_integration(hass, mock_config_entry)

    return mock_config_entry
