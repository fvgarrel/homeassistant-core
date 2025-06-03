"""Paperless-ngx Status coordinator."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from typing import TypeVar

from pypaperless import Paperless
from pypaperless.exceptions import (
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
from pypaperless.models import Document, Statistic, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type PaperlessConfigEntry = ConfigEntry[PaperlessData]

TData = TypeVar("TData")

UPDATE_INTERVAL_INBOX = timedelta(seconds=120)
UPDATE_INTERVAL_STATISTICS = timedelta(seconds=120)
UPDATE_INTERVAL_STATUS = timedelta(seconds=300)


@dataclass
class PaperlessData:
    """Data for the Paperless-ngx integration."""

    statistics: PaperlessStatisticCoordinator
    status: PaperlessStatusCoordinator
    inbox: PaperlessInboxCoordinator


@dataclass
class InboxData:
    """Data for the Paperless-ngx inbox platform."""

    inbox_tag_ids: list[int]
    documents: list[Document]


class PaperlessCoordinator(DataUpdateCoordinator[TData]):
    """Coordinator to manage fetching Paperless-ngx API."""

    config_entry: PaperlessConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaperlessConfigEntry,
        api: Paperless,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize Paperless-ngx statistics coordinator."""
        self.api = api

        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=name,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> TData:
        """Update data via internal method."""
        try:
            return await self._async_update_data_internal()
        except PaperlessConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except PaperlessInvalidTokenError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from err
        except PaperlessInactiveOrDeletedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="user_inactive_or_deleted",
            ) from err
        except PaperlessForbiddenError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="forbidden",
            ) from err

    @abstractmethod
    async def _async_update_data_internal(self) -> TData:
        """Update data via paperless-ngx API."""


class PaperlessStatisticCoordinator(PaperlessCoordinator[Statistic]):
    """Coordinator to manage Paperless-ngx statistic updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaperlessConfigEntry,
        api: Paperless,
    ) -> None:
        """Initialize Paperless-ngx status coordinator."""
        super().__init__(
            hass,
            entry,
            api,
            name="Statistics Coordinator",
            update_interval=UPDATE_INTERVAL_STATISTICS,
        )

    async def _async_update_data_internal(self) -> Statistic:
        """Fetch statistics data from API endpoint."""
        return await self.api.statistics()


class PaperlessStatusCoordinator(PaperlessCoordinator[Status]):
    """Coordinator to manage Paperless-ngx status updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaperlessConfigEntry,
        api: Paperless,
    ) -> None:
        """Initialize Paperless-ngx status coordinator."""
        super().__init__(
            hass,
            entry,
            api,
            name="Status Coordinator",
            update_interval=UPDATE_INTERVAL_STATUS,
        )

    async def _async_update_data_internal(self) -> Status:
        """Fetch status data from API endpoint."""
        return await self.api.status()


class PaperlessInboxCoordinator(PaperlessCoordinator[InboxData | None]):
    """Coordinator to manage Paperless-ngx inbox updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaperlessConfigEntry,
        api: Paperless,
    ) -> None:
        """Initialize Paperless-ngx inbox coordinator."""
        super().__init__(
            hass,
            entry,
            api,
            name="Inbox Coordinator",
            update_interval=UPDATE_INTERVAL_INBOX,
        )

    async def _async_update_data_internal(self) -> InboxData | None:
        """Fetch inbox data from API endpoint."""

        inbox_tags = (await self.api.statistics()).inbox_tags

        if not inbox_tags:
            return None

        inbox_data = InboxData(
            inbox_tag_ids=inbox_tags,
            documents=[],
        )

        filters = {
            "tags__id__in": ",".join(
                str(tag_id) for tag_id in inbox_data.inbox_tag_ids
            ),
            "ordering": "added",
        }

        async with self.api.documents.reduce(**filters) as filtered:
            inbox_data.documents.extend([item async for item in filtered])

        return inbox_data
