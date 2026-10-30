from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import ViewpieCoordinator
from .entity import ViewpieEntity

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: ViewpieCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities([ViewpiePausedBinarySensor(coordinator), ViewpieScreenOffBinarySensor(coordinator), ViewpieFullscreenBinarySensor(coordinator)])
    known: set[str] = set()
    @callback
    def add_camera_entities() -> None:
        details = coordinator.data.get("camera_details", []) if coordinator.data else []
        new = []
        for item in details:
            name = str(item.get("name", ""))
            if name and name not in known:
                known.add(name)
                new.extend([ViewpieCameraRunningBinarySensor(coordinator, name), ViewpieCameraInUseBinarySensor(coordinator, name)])
        if new: async_add_entities(new)
    add_camera_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_camera_entities))

class ViewpieBinarySensorBase(ViewpieEntity, BinarySensorEntity):
    _key: str
    _default = False
    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        super().__init__(coordinator); self._attr_unique_id = f"{coordinator.entry.entry_id}_{self._key}"
    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success: return None
        return bool(self.status.get(self._key, self._default))

class ViewpiePausedBinarySensor(ViewpieBinarySensorBase):
    _attr_name = "Paused"; _attr_device_class = BinarySensorDeviceClass.RUNNING; _key = "paused"
class ViewpieScreenOffBinarySensor(ViewpieBinarySensorBase):
    _attr_name = "Screen off"; _attr_device_class = BinarySensorDeviceClass.POWER; _key = "screen_off"
class ViewpieFullscreenBinarySensor(ViewpieEntity, BinarySensorEntity):
    _attr_name = "Fullscreen mode"; _attr_icon = "mdi:fullscreen"
    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        super().__init__(coordinator); self._attr_unique_id = f"{coordinator.entry.entry_id}_fullscreen_active"
    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success: return None
        return self.status.get("fullscreen_camera") is not None

class ViewpieCameraBinarySensor(ViewpieEntity, BinarySensorEntity):
    _camera_key: str
    def __init__(self, coordinator: ViewpieCoordinator, camera_name: str) -> None:
        super().__init__(coordinator); self.camera_name = camera_name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_camera_{camera_name}_{self._camera_key}"
        self._attr_name = f"{camera_name} {self._camera_key.replace('_', ' ')}"
    @property
    def _camera(self) -> dict:
        return next((c for c in self.status.get("camera_details", []) if c.get("name") == self.camera_name), {})
    @property
    def extra_state_attributes(self) -> dict:
        return {"references": int(self._camera.get("ref_count", 0))} if self._camera else {}
class ViewpieCameraRunningBinarySensor(ViewpieCameraBinarySensor):
    _camera_key = "running"; _attr_device_class = BinarySensorDeviceClass.RUNNING; _attr_icon = "mdi:cctv"
    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success: return None
        return bool(self._camera.get("running", False))
class ViewpieCameraInUseBinarySensor(ViewpieCameraBinarySensor):
    _camera_key = "in_use"; _attr_icon = "mdi:camera-lock"
    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success: return None
        return int(self._camera.get("ref_count", 0)) > 0
