# 1pMobile Home Assistant Integration

A custom integration for [Home Assistant](https://www.home-assistant.io/) that connects to your 1pMobile UK account and brings your mobile usage and account information into Home Assistant.

## Features

- **Account balance** – Monitor your current 1pMobile account balance.
- **Call history** – Retrieve details of outgoing calls, including destination number, date, time, duration and cost.
- **SMS history** – Retrieve details of outgoing text messages, including destination number, date, time and cost.
- **Contact mapping** – Assign friendly names to telephone numbers to make activity history easier to understand.
- **Recent activity** – Maintain a history of recent calls and text messages.
- **Daily summaries** – Provide information about new activity and your remaining account balance.
- **Monthly usage** – Monitor monthly calls, SMS messages, costs and data usage.

## Installation

This integration is installed manually and does not require HACS.

1. Download or clone this repository.
2. Locate the `custom_components` directory.
3. Copy the `ha_1pmobile` folder into your Home Assistant configuration directory:

   ```text
   /config/custom_components/ha_1pmobile/
   ```

4. Restart Home Assistant.
5. Navigate to **Settings → Devices & Services**.
6. Select **Add Integration**.
7. Search for **1pMobile** and follow the configuration steps.

## Repository structure

The GitHub repository is named `ha_1pmobile`.

```text
ha_1pmobile/
├── README.md
├── LICENSE
└── custom_components/
    └── ha_1pmobile/
        ├── __init__.py
        ├── config_flow.py
        ├── const.py
        ├── manifest.json
        ├── sensor.py
        └── ...
```

The integration directory and the `domain` specified in `manifest.json` must both be `ha_1pmobile`.

## Configuration

The integration uses Home Assistant's configuration flow.

1. Go to **Settings → Devices & Services**.
2. Select **Add Integration**.
3. Search for **1pMobile**.
4. Enter your 1pMobile account credentials when prompted.

## Contact name mapping

Telephone numbers can be associated with friendly contact names to make call and SMS history easier to read.

The mapping uses the following format:

| Telephone number = Contact name |
| --- |
| `07987654321 = Contact Name` |

For example:

| Mapping |
| --- |
| `07987654321 = John` |
| `07712345678 = Sarah` |
| `07898765432 = Work` |

Add one entry per telephone number. Use the full telephone number, followed by an equals sign (`=`), followed by the contact's preferred name.

The integration can then display the contact name instead of the telephone number wherever contact mapping is supported.

## Entities

The integration uses the `1pmobile` entity ID prefix.

Examples include:

| Entity | Description |
| --- | --- |
| `sensor.1pmobile_account_status` | Account status and recent activity |
| `sensor.1pmobile_balance` | Current account balance |
| `sensor.1pmobile_monthly_calls` | Monthly outgoing call count |
| `sensor.1pmobile_monthly_sms` | Monthly outgoing SMS count |
| `sensor.1pmobile_monthly_call_cost` | Monthly call cost |
| `sensor.1pmobile_monthly_sms_cost` | Monthly SMS cost |
| `sensor.1pmobile_monthly_data_cost` | Monthly data cost |
| `sensor.1pmobile_monthly_total_cost` | Total monthly cost |
| `sensor.1pmobile_monthly_data_usage` | Monthly data usage |

The exact entities available depend on the integration version and the information returned by 1pMobile.

## Dashboard examples

The integration's sensors and activity attributes can be used to create Home Assistant dashboard cards displaying:

- Current account balance.
- Recent outgoing calls and text messages.
- Daily call and SMS expenditure.
- Monthly usage and costs.
- Contact names instead of telephone numbers.

## Troubleshooting

If the integration does not appear after installation:

1. Check that the integration folder is located at `/config/custom_components/ha_1pmobile/`.
2. Confirm that `manifest.json` is present inside that folder.
3. Check that the `domain` value in `manifest.json` is `ha_1pmobile`.
4. Restart Home Assistant.
5. Check **Settings → System → Logs** for integration errors.

If sensors report `unknown` or `unavailable`, check that your 1pMobile account credentials are correct and that the 1pMobile service is accessible.

## Disclaimer

This is an unofficial community integration and is not affiliated with, endorsed by or supported by 1pMobile.

Use at your own risk. Changes to the 1pMobile website or its underlying services may affect the integration.

## Contributions

Suggestions, bug reports and contributions are welcome. Please use the GitHub Issues section to report problems or request improvements.

## Licence

See the accompanying `LICENSE` file for licence details.
