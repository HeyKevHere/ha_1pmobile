"""Sensors for 1pMobile."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTime
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        OnePMobileSensor(coordinator, entry, "balance", "Balance", "GBP", SensorDeviceClass.MONETARY),
        OnePMobileSensor(coordinator, entry, "calls_today", "Calls today"),
        OnePMobileSensor(coordinator, entry, "sms_today", "SMS today"),
        OnePMobileSensor(coordinator, entry, "monthly_calls_count", "Monthly calls"),
        OnePMobileSensor(coordinator, entry, "monthly_sms_count", "Monthly SMS"),
        OnePMobileSensor(coordinator, entry, "monthly_calls_cost_gbp", "Monthly call cost", "GBP", SensorDeviceClass.MONETARY),
        OnePMobileSensor(coordinator, entry, "monthly_sms_cost_gbp", "Monthly SMS cost", "GBP", SensorDeviceClass.MONETARY),
        OnePMobileSensor(coordinator, entry, "monthly_data_cost_gbp", "Monthly data cost", "GBP", SensorDeviceClass.MONETARY),
        OnePMobileSensor(coordinator, entry, "monthly_total_cost_gbp", "Monthly total cost", "GBP", SensorDeviceClass.MONETARY),
        OnePMobileSensor(coordinator, entry, "monthly_data_mb", "Monthly data usage", "MB"),
        OnePMobileSensor(coordinator, entry, "status", "Account status"),
    ])


class OnePMobileSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, key, label, unit=None, device_class=None):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"1pMobile {label}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_icon = {
            "balance": "mdi:wallet",
            "calls_today": "mdi:phone-outgoing",
            "sms_today": "mdi:message-text",
            "status": "mdi:cloud-check",
            "monthly_calls_count": "mdi:phone-outgoing",
            "monthly_sms_count": "mdi:message-text",
            "monthly_calls_cost_gbp": "mdi:cash",
            "monthly_sms_cost_gbp": "mdi:cash",
            "monthly_data_cost_gbp": "mdi:cash",
            "monthly_total_cost_gbp": "mdi:cash-multiple",
            "monthly_data_mb": "mdi:chart-donut",
        }.get(key)
        self._attr_extra_state_attributes = {}

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self._key == "status":
            return data.get("status", "unknown")
        return data.get(self._key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        contacts = data.get("contacts", {})
        recent = []
        for event in data.get("events", [])[:100]:
            item = dict(event)
            number = item.get("number", "")
            item["display_name"] = contacts.get(_normalise_number(number), number)
            recent.append(item)
        return {
            "message": data.get("message"),
            "last_checked": data.get("last_checked"),
            "new_activity": data.get("new_events", []),
            "recent_activity": recent,
            "monthly_label": data.get("monthly_label"),
            "monthly_usage": data.get("monthly_usage", []),
        }


def _normalise_number(number):
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    return "0" + digits[2:] if digits.startswith("44") else digits
