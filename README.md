Описание на русском [доступно тут](./README.ru.md).
<br>
<br>

# Home Assistant GSM Call

[![Add a custom repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=black-roland&repository=homeassistant-gsm-call&category=integration)

Home Assistant integration which allows you to call a phone number using 3G/4G, LTE modems.

The main idea is to use a modem for emergency notifications about important events in your smart home. However, emergency alerts are just one example, and the integration can be used in other scenarios as well.

## Installation

This integration can be installed using HACS. To add GSM Call to your Home Assistant, click the blue button above or add the repository manually:

1. Go to *HACS* → *Integrations*.
2. In the top right corner, select the three-dots menu and choose _Custom repositories_.
3. Paste `black-roland/homeassistant-gsm-call`.
4. Select _Integration_ in the _Category_ field.
5. Click the _Save_ icon.
6. Install "GSM Call".

## Configuration and usage

To use this integration, add the following to your `configuration.yaml`:

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/serial/by-id/usb-HUAWEI_Technology_HUAWEI_Mobile-if01-port0 # modem device path
```

The modem path can be obtained by [by clicking on the «All hardware» button](https://my.home-assistant.io/redirect/hardware/).

Make sure to restart Home Assistant after updating `configuration.yaml`. Use the `notify.call` action to make a phone call. The phone number to dial is specified as `target`:

```yaml
action:
  service: notify.call
  data:
    target: "+12345678901"
    message: "Required by HASS but not used by the integration — enter any text here"
```

### Ringing duration

By default, the called phone will ring for approximately 30 seconds. This duration can be adjusted by specifying `call_duration_sec`:

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/serial/by-id/usb-HUAWEI_Technology_HUAWEI_Mobile-if01-port0
    call_duration_sec: 40
```

Note:
- The duration is counted from the moment the called phone starts ringing.
- Your carrier might interrupt outgoing call before reaching the desired time if the duration is too high.

### Dialing timeout

Before the called phone starts ringing, there's typically a 5-10 second delay while the call connects. The integration will wait up to 20 seconds (default) for this connection to establish. This timeout can be adjusted by specifying `dial_timeout_sec`.

### Keepalive

Some modems stop responding to AT commands after a few days of inactivity. The integration can ping the modem with `AT` periodically, so a stuck modem is detected before you need it. Set the interval in minutes with `keepalive_interval_min` (disabled by default):

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/serial/by-id/usb-HUAWEI_Technology_HUAWEI_Mobile-if01-port0
    keepalive_interval_min: 30
```

Note:
- A ping is skipped while a call or an SMS is in progress; calls and SMS started during a ping wait for it to finish.
- With debug logs enabled, each ping logs the network registration (`AT+CREG?`), signal quality (`AT+CSQ`) and, on Huawei modems, `AT^SYSINFO`.
- If the modem doesn't answer, the `gsm_call_modem_unresponsive` event is fired (see [Events](#events)).

## Events

The integration fires the `gsm_call_ended` event indicating whether the call was declined or answered. For example, you can turn off the alarm if the callee declined a call:

```yaml
automation:
  - alias: "Disarm the security alarm when a call is declined"
    triggers:
      - trigger: event
        event_type: gsm_call_ended
        event_data:
          reason: "declined"
    actions:
      - action: alarm_control_panel.alarm_disarm
        target:
          entity_id: alarm_control_panel.security
```

`reason` can contain the following values: `not_answered`, `declined`, `answered`.

In addition to the `reason`, you can filter by the `phone_number`. All possible data properties can be found in [developer tools](https://my.home-assistant.io/create-link/?redirect=developer_events).

When [keepalive](#keepalive) is enabled and the modem doesn't answer a ping, the integration fires the `gsm_call_modem_unresponsive` event with the modem path in `device`. You can use it to get notified or to power-cycle the modem:

```yaml
automation:
  - alias: "Notify when the GSM modem is stuck"
    triggers:
      - trigger: event
        event_type: gsm_call_modem_unresponsive
    actions:
      - action: persistent_notification.create
        data:
          message: "GSM modem {{ trigger.event.data.device }} is not responding"
```

## SMS support

This integration experimentally supports sending SMS messages in addition to making voice calls. To configure SMS notifications, add a separate entry in your `configuration.yaml`:

```yaml
notify:
  - name: sms
    platform: gsm_call
    type: sms
    device: /dev/serial/by-id/usb-HUAWEI_Technology_HUAWEI_Mobile-if01-port0 # the same path as for calls
```

To send an SMS message, use the `notify.sms` service:

```yaml
action:
  service: notify.sms
  data:
    target: "+12345678901"
    message: "This is an SMS message"
```

Note:
- SMS support is experimental: you can track down the implementation progress in [#17](https://github.com/black-roland/homeassistant-gsm-call/issues/17)
- SMS messages are limited to the GSM 7-bit alphabet (basic Latin letters, digits, and common symbols)
- The `type: sms` parameter is required to distinguish SMS notifications from voice calls
- SMS and voice call configurations can coexist in the same `configuration.yaml` file
- GUI will replace legacy `congiguration.yaml` in v1.0 (stable)

## Troubleshooting

For troubleshooting, first enable debug logs in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.gsm_call: debug
```

After restarting, check the logs in *Settings* → *System* → *Logs* (or use [this link to open the logs](https://my.home-assistant.io/redirect/logs/)).

### ZTE modems

On some ZTE modems, dialing only works after sending an obscure command: `AT%icscall=1,0`. Try specifying `hardware: zte` in the configuration if dialing doesn't work with the default configuration:

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/serial/by-id/usb-ZTE_MF192_D536C4624C61DC91XXXXXXXXXXXXXXXXXXXXXXXX-if00
    hardware: zte
```

### GTM382-based modems

For Globetrotter HSUPA and other GTM382-based modems, add `hardware: gtm382` to your configuration:

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/ttyHS6
    hardware: gtm382
```

### ATD/ATDT (dialing commands)

Most modems work perfectly with default settings, but if you're experiencing issues, your modem might require a specific dialing command. As a troubleshooting step, try specifying `hardware: atdt`:

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/serial/by-id/usb-Obscure_Hardware-if01-port0
    hardware: atdt
```

## Supported hardware

In general, this integration [should be compatible with modems specified here](https://wammu.eu/phones/).

Tested on:
- Huawei E1550 (identifies as Huawei E161/E169/E620/E800).
- Huawei E171.
- Huawei E3531 (needs to be unlocked using [this guide](http://blog.asiantuntijakaveri.fi/2015/07/convert-huawei-e3372h-153-from.html)).
- ZTE MF192 (`hardware: zte` must be specified in the configuration).
- Globetrotter HSUPA (`hardware: gtm382`).

**Want to add support for your modem?** Check out [contributing guidelines](./CONTRIBUTING.md#adding-support-for-new-modems) to learn how you can help!
