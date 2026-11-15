"""1pMobile personal account integration."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN, CONF_POLL_HOUR, DEFAULT_POLL_HOUR
from .client import OnePMobileClient
from .const import CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_history")
    stored = await store.async_load() or {"events": [], "contacts": {}, "last_daily_summary": None}
    client = OnePMobileClient(hass, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])

    async def async_update_data():
        try:
            fetched = await client.async_fetch()
            if fetched.get("status") != "ok":
                raise UpdateFailed(fetched.get("message", "1pMobile data retrieval failed"))
            old_events = stored.get("events", [])
            known = {event["id"] for event in old_events}
            first_sync = not stored.get("initialized", False)
            new_events = [] if first_sync else [e for e in fetched["events"] if e["id"] not in known]
            # Keep a rolling 2-year local history; newest first.
            merged = {e["id"]: e for e in old_events}
            merged.update({e["id"]: e for e in fetched["events"]})
            events = sorted(merged.values(), key=lambda e: e["timestamp"], reverse=True)
            cutoff = (dt_util.now() - timedelta(days=730)).isoformat()
            events = [e for e in events if e.get("timestamp", "") >= cutoff]
            stored["events"] = events
            stored["initialized"] = True
            await store.async_save(stored)
            result = {
                **fetched,
                "events": events,
                "new_events": new_events,
                "last_checked": dt_util.now().isoformat(),
                "contacts": stored.get("contacts", {}),
            }
            await _async_daily_notification(hass, entry, result, stored, store)
            return result
        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.exception("Unable to update 1pMobile account")
            raise UpdateFailed(f"Unable to retrieve 1pMobile account data: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass, _LOGGER, name="1pMobile", update_method=async_update_data,
        update_interval=None,
    )
    # Do not let initial setup fail permanently if the site changes; entities can
    # show an unavailable state and Home Assistant can retry the next interval.
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Initial 1pMobile update failed: %s", err)
        coordinator.data = {
            "status": "error", "message": str(err), "balance": None, "events": [],
            "new_events": [], "last_checked": None, "contacts": stored.get("contacts", {})
        }
    async def _scheduled_refresh(now=None):
        await coordinator.async_request_refresh()

    poll_hour = entry.options.get(CONF_POLL_HOUR, DEFAULT_POLL_HOUR)
    cancel = async_track_time_change(
        hass, _scheduled_refresh, hour=poll_hour, minute=0, second=0
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator, "client": client, "store": store,
        "stored": stored, "cancel_schedule": cancel
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_daily_notification(hass, entry, result, stored, store):
    """Send one daily summary when a notify service has been configured."""
    from .const import CONF_NOTIFY_SERVICE
    service = entry.options.get(CONF_NOTIFY_SERVICE, "")
    if not service or result.get("status") != "ok":
        return
    today = dt_util.now().date().isoformat()
    if stored.get("last_daily_summary") == today:
        return
    events = result.get("new_events", [])
    contacts = result.get("contacts", {})
    lines = [f"1pMobile daily summary", f"Remaining credit: £{result['balance']:.2f}",
             f"New outgoing calls: {sum(e['type'] == 'call' for e in events)}",
             f"New SMS messages: {sum(e['type'] == 'sms' for e in events)}"]
    for e in events[:20]:
        number = e.get("number", "Unknown")
        display = contacts.get(_normalise_number(number), number)
        kind = "Call" if e["type"] == "call" else "SMS"
        details = f", duration {e['duration']}" if e.get("duration") else ""
        lines.append(f"{e['date']} {e['time']} — {kind} to {display}{details}")
    if len(events) > 20:
        lines.append(f"...and {len(events)-20} more new events.")
    if not events:
        lines.append("No new outgoing calls or SMS messages found.")
    try:
        domain, _, service_name = service.partition(".")
        if domain != "notify" or not service_name:
            _LOGGER.warning("Notify service must be in the form notify.mobile_app_phone")
            return
        await hass.services.async_call(domain, service_name, {
            "title": "1pMobile daily summary", "message": "\n".join(lines)
        }, blocking=True)
        stored["last_daily_summary"] = today
        await store.async_save(stored)
    except Exception:
        _LOGGER.exception("Failed to send 1pMobile daily summary")


def _normalise_number(number):
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    if digits.startswith("44"):
        digits = "0" + digits[2:]
    return digits


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        item = hass.data[DOMAIN].pop(entry.entry_id)
        item["cancel_schedule"]()
        await item["client"].async_close()
    return ok
