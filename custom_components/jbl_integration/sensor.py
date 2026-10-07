"""Sensor platform for JBL integration."""
import aiohttp
import async_timeout
import logging
from datetime import timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.const import PERCENTAGE
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from .const import DOMAIN
from .coordinator import Coordinator
from .entity import build_entity_id
from .equalizer import format_frequency

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the JBL sensor platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    entityArray = []
    entityArray.append(JBLSensor(coordinator,entry,"play_medium","Play Medium","mdi:soundbar"))
    entityArray.append(JBLSensor(coordinator,entry,"volume_level","Volume","mdi:volume-high"))
    entityArray.append(JBLSensor(coordinator,entry,"transport_state","Transport State","mdi:state-machine"))
    entityArray.append(JBLSensor(coordinator,entry,"transport_status","Transport Status","mdi:information"))
    entityArray.append(JBLSensor(coordinator,entry,"mute","mute","mdi:volume-mute"))
    entityArray.append(JBLSensor(coordinator,entry,"track_duration","Track Duration","mdi:information"))
    entityArray.append(JBLSensor(coordinator,entry,"track","Track","mdi:information"))
    entityArray.append(JBLSensor(coordinator,entry,"channel","Channel","mdi:information"))
    entityArray.append(JBLSensor(coordinator,entry,"audio_format","Audio Format","mdi:surround-sound"))
    entityArray.append(JBLEqualizerSensor(coordinator, entry))
    
    if "Rears" in coordinator.data:
        entityArray.append(JBLRearSensor(coordinator,entry,0))
        entityArray.append(JBLRearSensor(coordinator,entry,1))
        
    async_add_entities(entityArray)

    
class JBLSensor(Entity):
    """Representation of a sensor to get JBL PlayMedium."""

    def __init__(self, coordinator, entry, infoString, name, icon):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._entry = entry
        self.entityName = name
        self.entityicon = icon
        self.entity_id = build_entity_id(
            "sensor",
            self.coordinator.device_info.get("name", "jbl_integration"),
            self.entityName,
        )
        self.infoString = infoString

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.entityName

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return whether the entity should be enabled when first added to the entity registry."""
        return False  # Disable the sensor by default

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.infoString)

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self.entityicon

    @property
    def enabled(self):
        return False

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return f"jbl_800_{self.infoString.replace('_', '')}_{self._entry.entry_id}"

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_info(self):
        """Return device information about this entity."""
        return self.coordinator.device_info


    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()


class JBLEqualizerSensor(SensorEntity):
    """Unified equalizer entity used by the JBL EQ graph/editor card."""

    _attr_icon = "mdi:equalizer"

    def __init__(self, coordinator, entry):
        self.coordinator = coordinator
        self._entry = entry
        self._attr_name = "Equalizer"
        self._attr_unique_id = f"jbl_equalizer_{entry.entry_id}"
        self.entity_id = build_entity_id(
            "sensor",
            self.coordinator.device_info.get("name", "jbl_integration"),
            "equalizer",
        )

    @property
    def device_info(self):
        return self.coordinator.device_info

    @property
    def native_value(self):
        return self.coordinator.data.get("eq_active_preset") or "Custom"

    @property
    def extra_state_attributes(self):
        profile = self.coordinator.data.get("eq_profile") or {}
        frequencies = [float(value) for value in profile.get("frequencies", [])]
        gains = [float(value) for value in profile.get("gains", [])]
        count = min(len(frequencies), len(gains))
        frequencies = frequencies[:count]
        gains = gains[:count]

        minimums = profile.get("minimums")
        maximums = profile.get("maximums")
        if not minimums or len(minimums) != count:
            minimums = [-12.0] * count
        if not maximums or len(maximums) != count:
            maximums = [12.0] * count

        return {
            "jbl_eq_editor": True,
            "entry_id": self._entry.entry_id,
            "band_count": count,
            "frequencies": frequencies,
            "bands": [format_frequency(value) for value in frequencies],
            "gains": gains,
            "minimums": minimums,
            "maximums": maximums,
            "step": float(profile.get("step") or 0.5),
            "active_preset": self.coordinator.data.get("eq_active_preset"),
            "preset_map": self.coordinator.data.get("eq_preset_map", {}),
        }

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class JBLRearSensor(Entity):
    """Representation of a battery for the rear speakers of the  JBL."""

    def __init__(self, coordinator, entry, arrayNumber: int):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.number = arrayNumber
        self._entry = entry
        self.entityName = "Battery"
        self.entity_id = build_entity_id(
            "sensor",
            self.coordinator.device_info.get("name", "jbl_integration"),
            self.coordinator.data["Rears"][self.number]["channel"],
            self.entityName,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.entityName
    
    @property
    def device_class(self):
        return SensorDeviceClass.BATTERY

    @property
    def unit_of_measurement(self):
        return PERCENTAGE

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return whether the entity should be enabled when first added to the entity registry."""
        return True  # Disable the sensor by default

    @property
    def state(self):
        """Return the state of the sensor."""
        if "Rears" in self.coordinator.data:
            return self.coordinator.data["Rears"][self.number]["capicity"]
        else:
            _LOGGER.debug("Rear speaker unavailable for %s", self.entity_id )
            return None
            

    @property
    def enabled(self):
        return True

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return f"jbl_{self._entry.entry_id}_{self.coordinator.data["Rears"][self.number]["channel"].lower()}_{self.entityName.replace(' ', '_').lower()}"

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_info(self):
        """Return device information about this entity."""
        BaseDevice = self.coordinator.device_info.copy()
        BaseDevice["name"] = BaseDevice["name"] + " Rear Speaker " + self.coordinator.data["Rears"][self.number]["channel"].title()
        BaseDevice["identifiers"] = {(DOMAIN,f"{self.coordinator.device_info.get("name", "jbl_integration").replace(' ', '_').lower()}_{self.coordinator.data["Rears"][self.number]["channel"]}")}
        return BaseDevice

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()
