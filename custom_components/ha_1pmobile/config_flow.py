"""Config and options flows for 1pMobile."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_CONTACTS, CONF_NOTIFY_SERVICE, CONF_POLL_HOUR, DEFAULT_CONTACTS, DEFAULT_POLL_HOUR


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].strip().lower())
            self._abort_if_unique_id_configured()
            # The login is tested during first coordinator refresh. Do not make
            # assumptions about hidden fields / CAPTCHA in the public login form.
            return self.async_create_entry(
                title=f"1pMobile ({user_input[CONF_USERNAME]})", data=user_input
            )
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        # Home Assistant injects the active entry into OptionsFlow.config_entry.
        # Do not assign it manually: that setter was removed in HA 2025.12.
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Store contact mapping in persistent integration storage, applied on
            # next update. Syntax: one mapping per line, number = display name.
            from homeassistant.helpers.storage import Store
            store = Store(self.hass, 1, f"{DOMAIN}_{self.config_entry.entry_id}_history")
            stored = await store.async_load() or {"events": [], "contacts": {}, "last_daily_summary": None}
            contacts = {}
            for line in user_input[CONF_CONTACTS].splitlines():
                if "=" not in line:
                    continue
                number, name = line.split("=", 1)
                number = "".join(ch for ch in number.strip() if ch.isdigit())
                if number.startswith("44"):
                    number = "0" + number[2:]
                if number and name.strip():
                    contacts[number] = name.strip()
            stored["contacts"] = contacts
            await store.async_save(stored)
            entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if entry_data:
                entry_data["stored"]["contacts"] = contacts
                if entry_data["coordinator"].data:
                    entry_data["coordinator"].data["contacts"] = contacts
                    entry_data["coordinator"].async_set_updated_data(entry_data["coordinator"].data)
            return self.async_create_entry(title="", data={
                CONF_CONTACTS: user_input[CONF_CONTACTS],
                CONF_NOTIFY_SERVICE: user_input[CONF_NOTIFY_SERVICE].strip(),
                CONF_POLL_HOUR: user_input[CONF_POLL_HOUR],
            })
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Optional(
                CONF_CONTACTS,
                default=self.config_entry.options.get(CONF_CONTACTS, DEFAULT_CONTACTS),
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Optional(CONF_NOTIFY_SERVICE, default=self.config_entry.options.get(CONF_NOTIFY_SERVICE, "")): str,
            vol.Optional(CONF_POLL_HOUR, default=self.config_entry.options.get(CONF_POLL_HOUR, DEFAULT_POLL_HOUR)): vol.All(int, vol.Range(min=0, max=23)),
        }))
