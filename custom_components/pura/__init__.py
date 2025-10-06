"""The Pura integration."""

from __future__ import annotations

from pypura import Pura, PuraAuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ID_TOKEN, CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import PuraDataUpdateCoordinator
from .helpers import get_device_id
from .services import async_setup_services

type PuraConfigEntry = ConfigEntry[PuraDataUpdateCoordinator]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Pura integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PuraConfigEntry) -> bool:
    """Set up Pura from a config entry."""
    _unlisten = entry.add_update_listener(update_listener)

    client = Pura(
        username=entry.data.get(CONF_USERNAME),
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
        id_token=entry.data.get(CONF_ID_TOKEN),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
    )

    try:
        await hass.async_add_executor_job(client.get_auth)
    except PuraAuthenticationError as err:
        raise ConfigEntryAuthFailed(err) from err
    except Exception as ex:
        raise ConfigEntryNotReady(ex) from ex

    coordinator = PuraDataUpdateCoordinator(hass, client=client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _async_save_tokens(ev: Event) -> None:
        """Save tokens to the config entry data."""
        _unlisten()
        hass.config_entries.async_update_entry(
            entry, data=entry.data | client.get_tokens()
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_save_tokens)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PuraConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: PuraConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: PuraConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        for devices in entry.runtime_data.devices.values()
        for device in devices
        if identifier[1] == get_device_id(device)
    )
