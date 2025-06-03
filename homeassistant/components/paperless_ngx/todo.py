"""Definition of Picnic shopping cart."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PaperlessConfigEntry, PaperlessInboxCoordinator
from .entity import PaperlessEntity

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=20)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Paperless-ngx inbox documents todo platform config entry."""
    coordinator = config_entry.runtime_data.inbox

    description = EntityDescription(
        key="documents_inbox_todo",
        translation_key="documents_inbox_todo",
    )

    async_add_entities([InboxDocuments(coordinator, description)])


class InboxDocuments(TodoListEntity, PaperlessEntity[PaperlessInboxCoordinator]):
    """Paperless-ngx inbox documents todo entity."""

    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Get the current inbox documents."""
        if self.coordinator.data is None:
            return None

        return [
            TodoItem(
                summary=item.title,
                uid=str(item.id),
                status=TodoItemStatus.NEEDS_ACTION,
            )
            for item in self.coordinator.data.documents
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item in the To-do list."""
        if not self.coordinator.data or not item.uid:
            raise ServiceValidationError(
                "No inbox data available or item ID not given."
            )

        document = await self.coordinator.api.documents(int(item.uid))
        document.title = item.summary

        # remove the inbox tags from the document if it is completed
        if item.status == TodoItemStatus.COMPLETED and document.tags:
            for tag_id in self.coordinator.data.inbox_tag_ids:
                if tag_id in document.tags:
                    document.tags.remove(tag_id)

        # save changed in paperless
        await document.update()

        await self.coordinator.async_refresh()
