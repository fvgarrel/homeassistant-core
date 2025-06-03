"""Test paperless_ngx todo platform."""

from collections.abc import Awaitable, Callable

from freezegun.api import FrozenDateTimeFactory
from pypaperless.models import Document, Statistic
import pytest

from homeassistant.components.paperless_ngx.coordinator import UPDATE_INTERVAL_INBOX
from homeassistant.components.todo import TodoServices
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.llm import TODO_DOMAIN

from . import setup_integration
from .const import ENTITY_ID_TODO

from tests.common import (
    AsyncMock,
    MockConfigEntry,
    SnapshotAssertion,
    async_fire_time_changed,
    patch,
)
from tests.typing import MagicMock


async def test_todo_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    get_todo_items: Callable[[], Awaitable[dict[str, str]]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test paperless_ngx todo entity."""
    with patch("homeassistant.components.paperless_ngx.PLATFORMS", [Platform.TODO]):
        await setup_integration(hass, mock_config_entry)

    assert snapshot == await get_todo_items()


@pytest.mark.usefixtures("init_integration")
async def test_paperless_inbox_tags(
    hass: HomeAssistant,
    mock_paperless: AsyncMock,
    freezer: FrozenDateTimeFactory,
    mock_statistic_data_update: MagicMock,
) -> None:
    """Test the state of the todo entity for inbox documents."""
    # initialize with 3 inbox documents
    state = hass.states.get(ENTITY_ID_TODO)
    assert state.state == "3"

    # update to none inbox tags
    mock_statistic_data_update["inbox_tags"] = None
    mock_paperless.statistics = AsyncMock(
        return_value=Statistic.create_with_data(
            mock_paperless, data=mock_statistic_data_update, fetched=True
        )
    )

    freezer.tick(UPDATE_INTERVAL_INBOX)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID_TODO)
    assert state.state == STATE_UNKNOWN

    # update to empty inbox tags
    mock_statistic_data_update["inbox_tags"] = []
    mock_paperless.statistics = AsyncMock(
        return_value=Statistic.create_with_data(
            mock_paperless, data=mock_statistic_data_update, fetched=True
        )
    )

    freezer.tick(UPDATE_INTERVAL_INBOX)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID_TODO)
    assert state.state == STATE_UNKNOWN

    # update available inbox tags
    mock_statistic_data_update["inbox_tags"] = [1, 2]
    mock_paperless.statistics = AsyncMock(
        return_value=Statistic.create_with_data(
            mock_paperless, data=mock_statistic_data_update, fetched=True
        )
    )

    freezer.tick(UPDATE_INTERVAL_INBOX)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID_TODO)
    assert state.state == "3"


@pytest.mark.usefixtures("init_integration")
async def test_paperless_inbox_update(
    hass: HomeAssistant,
    mock_document: Document,
) -> None:
    """Test the state of the todo entity for inbox documents."""

    # document has 3 tags including 1 inbox tag (9)
    assert mock_document.title == "Electricity Bill"
    assert mock_document.tags == [1, 2, 9]

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            "item": "1",
            "rename": "Updated Document Title",
        },
        target={ATTR_ENTITY_ID: ENTITY_ID_TODO},
        blocking=True,
    )

    # titled changed but inbox tag should not be removed
    assert mock_document.title == "Updated Document Title"
    assert mock_document.tags == [1, 2, 9]

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            "item": "1",
            "status": "completed",
        },
        target={ATTR_ENTITY_ID: ENTITY_ID_TODO},
        blocking=True,
    )

    # inbox tag should be removed
    assert mock_document.tags == [1, 2]
