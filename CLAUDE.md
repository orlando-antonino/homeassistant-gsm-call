# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Home Assistant custom integration (distributed via HACS) that places voice calls and sends SMS through 3G/4G/LTE modems using AT commands over a serial port. It's a legacy YAML `notify` platform, configured under `notify:` in `configuration.yaml`. The README says a GUI config flow is planned to replace YAML in v1.0 stable.

## Commands

There's no build step, test suite, or local dev harness. You validate changes by installing the integration into a real Home Assistant instance with a modem attached.

- Lint/format (from `.vscode/settings.json`): `flake8 --max-line-length=120 --ignore=E203,W503 custom_components` and `autopep8 --max-line-length=120`.
- CI (`.github/workflows/validate.yaml`) runs three checks:
  - `hassfest`, which validates `manifest.json`
  - HACS validation
  - an MPL-2.0 license header check (`.licenserc.yaml`)
- Every `.py` file under `custom_components/` must start with the MPL-2.0 header comment, or CI fails.

## Releases

Pushing a `v*.*.*` tag triggers `.github/workflows/release.yaml`. The workflow:
- checks that the tag matches `version` in `custom_components/gsm_call/manifest.json`
- zips the `custom_components/gsm_call/` directory into `gsm_call.zip` (HACS uses `zip_release`, see `hacs.json`)
- creates a draft GitHub release

Version bumps are separate commits whose message is just the version, e.g. `1.0.0-alpha.0`.

## Architecture

All code is in `custom_components/gsm_call/`. `__init__.py` is empty and all wiring happens in `notify.py`.

- **`notify.py`**: holds `PLATFORM_SCHEMA` and `get_service()`.
  - `get_service()` returns `GsmSmsNotificationService` when `type: sms`, otherwise `GsmCallNotificationService`.
  - The call service gets a dialer instance chosen from `SUPPORTED_DIALERS` by the `hardware` key.
  - `at_command` is deprecated: `hardware: atd` combined with `at_command: ATDT` maps to the `atdt` dialer.
  - Each `async_send_message` call opens its own serial connection and closes it in `finally`.
  - The serial port settings (baud 75600, 8N1, `dsrdtr`/`rtscts`) are hardcoded in `connect()`.
  - The `modem` attribute is stored on the class, not the instance. It acts as a guard so a second call or SMS can't start while one is already in progress. `GsmCallNotificationService` uses `GsmBaseNotificationService.modem`, while `GsmSmsNotificationService` uses its own class attribute. Keep this in mind when changing concurrency behavior.
  - Phone numbers are validated as E.164, then stripped to digits. Dialers and the SMS sender add the `+` back themselves.
- **`modem.py`**: `Modem` is a thin wrapper around an asyncio `StreamReader`/`StreamWriter`.
  - `execute_at()` sends a command, then reads lines until one equals or starts with an end marker.
  - On timeout it returns the lines collected so far instead of raising. Callers must check the response contents.
- **`calls/`**: dialer strategies.
  - `ATDialer` is the base. It sends `ATD+<number>;` and then polls `AT+CLCC` once per second (faster polling causes `+CME ERROR: 100` on some modems). The CLCC state code tells it whether the call is ringing, answered, or declined.
  - Once ringing starts, the timeout is rescheduled from `dial_timeout_sec` to `call_duration_sec`. The call is then hung up with `AT+CHUP`.
  - The result is an `EndedReason`, which `notify.py` fires as the `gsm_call_ended` event.
  - Vendor-specific dialers subclass `ATDialer`. They either override `at_command` (`ATToneDialer`) or send setup commands before calling `super().dial()` (`ZTEDialer`, `GTM382Dialer`).
  - To add support for a new modem: add a subclass in `calls/`, register it in `SUPPORTED_DIALERS`, and document it in both READMEs.
- **`sms/sms_sender.py`**: sends SMS in text mode.
  - The sequence is `AT+CMGF=1`, then `AT+CMGS="+<number>"`, wait for the `>` prompt, then send the body terminated with `\r` plus Ctrl+Z (`Modem.SMS_TERMINATOR`).
  - Messages are limited to the GSM 7-bit alphabet, enforced by the `GSM_7BIT_ALPHABET` regex in `const.py`.

## Documentation

User docs exist in English (`README.md`) and Russian (`README.ru.md`), and `CONTRIBUTING.md` contains both languages. Keep all of them in sync when changing configuration options, supported hardware, or events.
