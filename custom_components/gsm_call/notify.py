# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import re

import homeassistant.helpers.config_validation as cv
import serial
import serial_asyncio_fast as serial_asyncio
import voluptuous as vol
from homeassistant.components.notify import \
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA
from homeassistant.components.notify.const import ATTR_TARGET
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from custom_components.gsm_call.sms.sms_sender import SmsSender

from .calls.at_dialer import ATDialer
from .calls.at_tone_dialer import ATToneDialer
from .calls.gtm382_dialer import GTM382Dialer
from .calls.zte_dialer import ZTEDialer
from .const import (_LOGGER, ATTR_PHONE_NUMBER, ATTR_REASON, CONF_AT_COMMAND,
                    CONF_CALL_DURATION_SEC, CONF_DIAL_TIMEOUT_SEC,
                    CONF_HARDWARE, CONF_TYPE, EVENT_GSM_CALL_ENDED,
                    GSM_7BIT_ALPHABET)
from .modem import READ_LIMIT, Modem

# Hardware support configuration
SUPPORTED_DIALERS = {
    "atd": ATDialer,
    "atdt": ATToneDialer,
    "zte": ZTEDialer,
    "gtm382": GTM382Dialer,
}

# Platform schema
PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE): cv.isdevice,
        vol.Optional(CONF_HARDWARE, default="atd"): vol.In(SUPPORTED_DIALERS.keys()),
        vol.Optional(CONF_DIAL_TIMEOUT_SEC, default=20): cv.positive_int,
        vol.Optional(CONF_CALL_DURATION_SEC, default=30): cv.positive_int,
        # CONF_AT_COMMAND is replaced by CONF_HARDWARE
        vol.Optional(CONF_AT_COMMAND, default="ATD"): cv.matches_regex("^(ATD|ATDT)$"),
    }
)


def get_service(
    _hass: HomeAssistant,
    config: ConfigType,
    _discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService:
    """Get the appropriate GSM notification service."""
    if config.get(CONF_TYPE, "call") == "sms":
        sender = SmsSender()
        return GsmSmsNotificationService(config[CONF_DEVICE], sender)
    else:  # call
        dialer_name = config[CONF_HARDWARE]

        if config[CONF_HARDWARE] == "atd" and config[CONF_AT_COMMAND] == "ATDT":
            dialer_name = "atdt"

        dialer = SUPPORTED_DIALERS[dialer_name](
            dial_timeout_sec=config[CONF_DIAL_TIMEOUT_SEC],
            call_duration_sec=config[CONF_CALL_DURATION_SEC],
        )

        return GsmCallNotificationService(config[CONF_DEVICE], dialer)


class GsmBaseNotificationService(BaseNotificationService):
    """Base class for GSM notification services."""

    # Class-level modem instance
    modem: Modem | None = None

    def __init__(self, device_path: str):
        """Initialize the base service."""
        self.device_path = device_path
        self.modem: Modem | None = None

    async def connect(self) -> None:
        """Connect to the modem."""
        _LOGGER.debug(f"Connecting to {self.device_path}...")
        self.modem = Modem(
            *await serial_asyncio.open_serial_connection(
                url=self.device_path,
                baudrate=75600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                dsrdtr=True,
                rtscts=True,
                limit=READ_LIMIT,
            )
        )

    async def terminate(self) -> None:
        """Terminate the modem connection."""
        if self.modem is None:
            return

        _LOGGER.debug("Closing connection to the modem...")
        self.modem.writer.close()
        await self.modem.writer.wait_closed()
        self.modem = None

    def _validate_phone_number(self, phone_number: str) -> str:
        """Validate and normalize phone number."""
        phone_number_re = re.compile(r"^\+?[1-9]\d{1,14}$")
        if not phone_number_re.match(phone_number):
            raise ValueError("Invalid phone number")

        return re.sub(r"\D", "", phone_number)


class GsmCallNotificationService(GsmBaseNotificationService):
    """Service for making GSM voice calls."""

    def __init__(self, device_path: str, dialer):
        """Initialize the call service."""
        super().__init__(device_path)
        self.dialer = dialer

    async def async_send_message(self, _message="", **kwargs):
        """Make a voice call to the specified targets."""
        if not (targets := kwargs.get(ATTR_TARGET)):
            _LOGGER.info("At least 1 target is required")
            return

        # Check if already making a call
        if GsmBaseNotificationService.modem:
            _LOGGER.info("Already making a voice call")
            return

        try:
            await self.connect()

            for target in targets:
                try:
                    phone_number = self._validate_phone_number(target)
                except ValueError as e:
                    _LOGGER.error(f"Invalid phone number {target}: {e}")
                    continue

                call_state = await self.dialer.dial(GsmBaseNotificationService.modem, phone_number)
                self.hass.bus.async_fire(
                    EVENT_GSM_CALL_ENDED,
                    {ATTR_PHONE_NUMBER: phone_number, ATTR_REASON: call_state},
                )
        finally:
            await self.terminate()

    async def connect(self):
        """Connect to the modem for calls."""
        _LOGGER.debug(f"Connecting to {self.device_path} for voice call...")
        GsmBaseNotificationService.modem = Modem(
            *await serial_asyncio.open_serial_connection(
                url=self.device_path,
                baudrate=75600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                dsrdtr=True,
                rtscts=True,
                limit=READ_LIMIT,
            )
        )
        if not await GsmBaseNotificationService.modem.wake_up():
            raise HomeAssistantError(f"Modem on {self.device_path} is not responding to AT commands")

    async def terminate(self):
        """Terminate the modem connection for calls."""
        if GsmBaseNotificationService.modem is None:
            return

        _LOGGER.debug("Closing connection to the modem after voice call...")
        GsmBaseNotificationService.modem.writer.close()
        await GsmBaseNotificationService.modem.writer.wait_closed()
        GsmBaseNotificationService.modem = None


class GsmSmsNotificationService(GsmBaseNotificationService):
    """Service for sending GSM SMS messages."""

    def __init__(self, device_path: str, sender):
        """Initialize the SMS service."""
        super().__init__(device_path)
        self.sender = sender

    async def async_send_message(self, message="", **kwargs):
        """Send an SMS message to the specified targets."""
        if not (targets := kwargs.get(ATTR_TARGET)):
            _LOGGER.info("At least 1 target is required")
            return

        if not message:
            _LOGGER.error("SMS requires a non-empty message")
            return

        # Validate message for GSM 7-bit alphabet
        if not re.match(GSM_7BIT_ALPHABET, message):
            _LOGGER.error("SMS message contains invalid characters")
            raise HomeAssistantError("Only basic Latin letters, digits, and common symbols are supported")

        # Check if already connected for SMS
        if GsmSmsNotificationService.modem:
            _LOGGER.info("Already connected to the modem for SMS")
            return

        try:
            await self.connect()

            for target in targets:
                try:
                    phone_number = self._validate_phone_number(target)
                except ValueError as e:
                    _LOGGER.error(f"Invalid phone number {target}: {e}")
                    continue

                await self.sender.send(GsmSmsNotificationService.modem, phone_number, message)
        finally:
            await self.terminate()

    async def connect(self):
        """Connect to the modem for SMS."""
        _LOGGER.debug(f"Connecting to {self.device_path} for SMS...")
        GsmSmsNotificationService.modem = Modem(
            *await serial_asyncio.open_serial_connection(
                url=self.device_path,
                baudrate=75600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                dsrdtr=True,
                rtscts=True,
                limit=READ_LIMIT,
            )
        )
        if not await GsmSmsNotificationService.modem.wake_up():
            raise HomeAssistantError(f"Modem on {self.device_path} is not responding to AT commands")

    async def terminate(self):
        """Terminate the modem connection for SMS."""
        if GsmSmsNotificationService.modem is None:
            return

        _LOGGER.debug("Closing connection to the modem after SMS...")
        GsmSmsNotificationService.modem.writer.close()
        await GsmSmsNotificationService.modem.writer.wait_closed()
        GsmSmsNotificationService.modem = None
