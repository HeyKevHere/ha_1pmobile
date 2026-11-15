"""HTML client for 1pMobile's personal usage pages.

Parser targets the structure in user-provided saved pages:
  /usage                 calls
  /usage?_action=T       texts
Summary header contains Mobile and Credit; event tables have Time, To,
Duration (calls only), Cost (£), with date group rows.
The live login form itself was not included, so authentication is generic and
may need adjustment if 1pMobile changes its form or requires an extra step.
"""
import re
from datetime import datetime
from homeassistant.util import dt as dt_util
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import aiohttp

BASE = "https://www.1pmobile.com"
LOGIN_URL = BASE + "/log-in"
CALLS_URL = BASE + "/usage"
TEXTS_URL = BASE + "/usage?_action=T"
MONTHLY_URL = BASE + "/usage?_action=M"


def _clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _number(value):
    return "".join(c for c in value if c.isdigit())


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.form = None
        self.inputs = []
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
        self.heading = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.form = {"action": a.get("action", ""), "method": a.get("method", "get").lower(), "inputs": []}
            self.forms.append(self.form)
        elif tag == "input" and self.form is not None:
            self.form["inputs"].append(a)
        elif tag == "table":
            self.table = []
            self.tables.append(self.table)
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = {"text": "", "tag": tag, "attrs": a}
        elif tag in ("h1", "h2"):
            self.heading = ""

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data
        if self.heading is not None:
            self.heading += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = _clean(self.cell["text"])
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table":
            self.table = None
        elif tag == "form":
            self.form = None
        elif tag in ("h1", "h2"):
            self.heading = None


class OnePMobileClient:
    def __init__(self, hass, username, password):
        self.hass = hass
        self.username = username
        self.password = password
        self.session = aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(unsafe=True),
            timeout=aiohttp.ClientTimeout(total=35),
            headers={"User-Agent": "HomeAssistant-1pMobile/0.2"},
        )

    async def async_close(self):
        await self.session.close()

    async def _get(self, url):
        async with self.session.get(url, allow_redirects=True) as response:
            response.raise_for_status()
            return str(response.url), await response.text(errors="replace")

    async def _login(self):
        final_url, html = await self._get(LOGIN_URL)
        parser = PageParser()
        parser.feed(html)
        # Select a form that contains a password input. Keep hidden/CSRF inputs.
        candidates = [f for f in parser.forms if any(i.get("type", "").lower() == "password" for i in f["inputs"])]
        if not candidates:
            # Already authenticated or changed login page; test a protected page.
            _, page = await self._get(CALLS_URL)
            if "Your call usage" in page and "Log out" in page:
                return
            raise RuntimeError("Could not find the 1pMobile login form (possible page redesign, JavaScript challenge or MFA).")
        form = candidates[0]
        payload = {}
        username_field = None
        password_field = None
        for inp in form["inputs"]:
            name = inp.get("name")
            if not name:
                continue
            typ = inp.get("type", "text").lower()
            if typ == "hidden":
                payload[name] = inp.get("value", "")
            elif typ == "password":
                password_field = name
            elif typ in ("text", "email", "tel") and username_field is None:
                username_field = name
        if not username_field or not password_field:
            raise RuntimeError("The 1pMobile login form's username/password fields could not be identified.")
        payload[username_field] = self.username
        payload[password_field] = self.password
        action = urljoin(final_url, form["action"] or final_url)
        method = form["method"]
        if method == "post":
            async with self.session.post(action, data=payload, allow_redirects=True) as response:
                response.raise_for_status()
                page = await response.text(errors="replace")
                landed = str(response.url)
        else:
            async with self.session.get(action, params=payload, allow_redirects=True) as response:
                response.raise_for_status()
                page = await response.text(errors="replace")
                landed = str(response.url)
        # Validate session using protected page, not just HTTP 200.
        _, usage = await self._get(CALLS_URL)
        if "Your call usage" not in usage or "Log out" not in usage:
            raise RuntimeError("1pMobile login did not reach the authenticated usage page. Check credentials or whether the site requires JavaScript/MFA.")

    async def async_validate_login(self):
        await self._login()

    async def async_fetch(self):
        await self._login()
        calls_url, calls_html = await self._get(CALLS_URL)
        texts_url, texts_html = await self._get(TEXTS_URL)
        monthly_url, monthly_html = await self._get(MONTHLY_URL)
        balance = self._parse_balance(calls_html)
        if balance is None:
            balance = self._parse_balance(texts_html)
        if balance is None:
            raise RuntimeError("Could not parse the Credit value from the account usage page.")
        calls = self._parse_events(calls_html, "call")
        texts = self._parse_events(texts_html, "sms")
        events = calls + texts
        events.sort(key=lambda e: e["timestamp"], reverse=True)
        monthly_usage = self._parse_monthly_usage(monthly_html)
        current_month = dt_util.now().strftime("%Y-%m")
        monthly = next((row for row in monthly_usage if row["month"] == current_month), None)
        if monthly is None and monthly_usage:
            # Keep historic figures visible, but don't label an older month as current.
            monthly = None
        monthly = monthly or {}
        return {
            "status": "ok", "balance": balance, "events": events,
            "calls_today": sum(e["type"] == "call" and e["date"] == dt_util.now().date().isoformat() for e in events),
            "sms_today": sum(e["type"] == "sms" and e["date"] == dt_util.now().date().isoformat() for e in events),
            "monthly_label": monthly.get("month_label"),
            "monthly_calls_count": monthly.get("calls_count"),
            "monthly_sms_count": monthly.get("sms_count"),
            "monthly_calls_cost_gbp": monthly.get("calls_cost_gbp"),
            "monthly_sms_cost_gbp": monthly.get("sms_cost_gbp"),
            "monthly_data_mb": monthly.get("data_mb"),
            "monthly_data_cost_gbp": monthly.get("data_cost_gbp"),
            "monthly_total_cost_gbp": monthly.get("total_cost_gbp"),
            "monthly_usage": monthly_usage,
            "message": "Updated from 1pMobile calls, texts and monthly usage pages",
        }

    def _parse_balance(self, html):
        parser = PageParser()
        parser.feed(html)
        for table in parser.tables:
            for row in table:
                texts = [c["text"] for c in row]
                if texts and texts[0].strip().lower() == "credit" and len(texts) > 1:
                    match = re.search(r"(?:£|\xa3)\s*([0-9]+(?:\.[0-9]{1,2})?)", texts[1])
                    if match:
                        return float(match.group(1))
        # The supplied HTML may have been saved with a legacy encoding; fallback.
        match = re.search(r"<strong>Credit</strong>\s*</td>\s*<td[^>]*>\s*(?:£|&#163;|\xa3)\s*([0-9]+(?:\.[0-9]{1,2})?)", html, re.I)
        return float(match.group(1)) if match else None


    def _parse_monthly_usage(self, html):
        """Parse provider-reported monthly totals from /usage?_action=M."""
        parser = PageParser()
        parser.feed(html)
        for table in parser.tables:
            header_row = next((row for row in table if row and all(c["tag"] == "th" for c in row)), None)
            if not header_row:
                continue
            headers = [c["text"].lower() for c in header_row]
            if not all(any(h.startswith(required) for h in headers) for required in ("month", "calls", "texts", "data", "total")):
                continue
            indices = {}
            for key in ("month", "calls", "texts", "data", "total"):
                indices[key] = next(i for i, h in enumerate(headers) if h.startswith(key))
            output = []
            for row in table:
                if not row or len(row) <= max(indices.values()):
                    continue
                cells = [c["text"] for c in row]
                month_label = _clean(cells[indices["month"]])
                try:
                    month_dt = datetime.strptime(month_label, "%b %Y")
                except ValueError:
                    try:
                        month_dt = datetime.strptime(month_label, "%B %Y")
                    except ValueError:
                        continue

                def count_and_cost(value, word):
                    count_match = re.search(r"(\d+)\s*" + word + r"\b", value, re.I)
                    amounts = re.findall(r"\d+(?:\.\d{1,3})?", value)
                    count = int(count_match.group(1)) if count_match else None
                    # The last number in these cells is the provider-displayed cost.
                    cost = float(amounts[-1]) if amounts else None
                    return count, cost

                calls_count, calls_cost = count_and_cost(cells[indices["calls"]], "calls?")
                sms_count, sms_cost = count_and_cost(cells[indices["texts"]], "texts?")
                data_text = cells[indices["data"]]
                data_match = re.search(r"([\d]+(?:\.[\d]+)?)\s*MB\b", data_text, re.I)
                data_amounts = re.findall(r"\d+(?:\.\d{1,3})?", data_text)
                data_mb = float(data_match.group(1)) if data_match else None
                data_cost = float(data_amounts[-1]) if data_amounts else None
                total_amounts = re.findall(r"\d+(?:\.\d{1,3})?", cells[indices["total"]])
                total_cost = float(total_amounts[-1]) if total_amounts else None
                output.append({
                    "month": month_dt.strftime("%Y-%m"),
                    "month_label": month_label,
                    "calls_count": calls_count,
                    "calls_cost_gbp": calls_cost,
                    "sms_count": sms_count,
                    "sms_cost_gbp": sms_cost,
                    "data_mb": data_mb,
                    "data_cost_gbp": data_cost,
                    "total_cost_gbp": total_cost,
                })
            return sorted(output, key=lambda item: item["month"], reverse=True)
        raise RuntimeError("Could not find the monthly usage table (expected Month, Calls, Texts, Data and Total columns).")

    def _parse_events(self, html, kind):
        parser = PageParser()
        parser.feed(html)
        events = []
        for table in parser.tables:
            header = []
            for row in table:
                if row and all(c["tag"] == "th" for c in row):
                    header = [c["text"].lower() for c in row]
                    if "time" in header and "to" in header:
                        break
            if not header or "time" not in header or "to" not in header:
                continue
            idx_time = header.index("time")
            idx_to = header.index("to")
            idx_duration = header.index("duration (h:m:s)") if "duration (h:m:s)" in header else None
            idx_cost = next((i for i, h in enumerate(header) if h.startswith("cost")), None)
            current_date = None
            for row in table:
                if not row:
                    continue
                # Group header rows contain one cell spanning multiple columns.
                if len(row) == 1 or (len(row) > 0 and row[0]["attrs"].get("colspan")):
                    date_text = row[0]["text"]
                    parsed = self._parse_date(date_text)
                    if parsed:
                        current_date = parsed
                    continue
                cells = [c["text"] for c in row]
                if max(idx_time, idx_to) >= len(cells) or not current_date:
                    continue
                time_text = cells[idx_time].split("(")[0].strip()
                number = re.sub(r"\s+", "", cells[idx_to].split(" ")[0])
                if not number or not re.search(r"\d{6,}", number) or not re.match(r"^\d{1,2}:\d{2}:\d{2}$", time_text):
                    continue
                duration = cells[idx_duration] if idx_duration is not None and idx_duration < len(cells) else None
                cost = None
                if idx_cost is not None and idx_cost < len(cells):
                    try:
                        cost = float(cells[idx_cost].replace("£", "").replace(",", "").strip())
                    except ValueError:
                        pass
                stamp = f"{current_date}T{time_text}"
                # Stable identity for deduplication. Include type and all available row values.
                identity = "|".join([kind, stamp, number, duration or "", str(cost)])
                import hashlib
                event_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
                events.append({
                    "id": event_id, "type": kind, "date": current_date,
                    "time": time_text, "timestamp": stamp, "number": number,
                    "duration": duration if duration and duration != "-" else None,
                    "cost_gbp": cost,
                })
        return events

    def _parse_date(self, text):
        text = _clean(text)
        # Examples in the supplied pages: "Thursday 17 September 2026"
        for fmt in ("%A %d %B %Y", "%d %B %Y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                pass
        return None
