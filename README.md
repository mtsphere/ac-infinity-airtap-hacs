# ac-infinity-airtap-hacs

Home Assistant custom integration for Bluetooth Low Energy (BLE) control of [AC Infinity Airtap](https://acinfinity.com/register-booster-fans/) series register fans.

Uses [ac-infinity-ble](https://github.com/hunterjm/ac-infinity-ble/) library.

## Troubleshooting

### Debug Logging

To enbale debug logging, configure the your [loggers](https://www.home-assistant.io/integrations/logger/) as follows:

```yaml
logger:
  default: info
  logs:
    ac_infinity_ble: debug
    custom_components.ac_infinity: debug
```

## Credit

This project builds on work by Jason Hunter: [hunterjm/ac-infinity-hacs](https://github.com/hunterjm/ac-infinity-hacs).
