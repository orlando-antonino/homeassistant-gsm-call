# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
from enum import Enum

_LOGGER = logging.getLogger(__name__)

DOMAIN = "gsm_call"

CONF_TYPE = "type"
CONF_AT_COMMAND = "at_command"
CONF_DIAL_TIMEOUT_SEC = "dial_timeout_sec"
CONF_CALL_DURATION_SEC = "call_duration_sec"
CONF_HARDWARE = "hardware"
CONF_KEEPALIVE_INTERVAL_MIN = "keepalive_interval_min"

EVENT_GSM_CALL_ENDED = f"{DOMAIN}_ended"
EVENT_GSM_MODEM_UNRESPONSIVE = f"{DOMAIN}_modem_unresponsive"
ATTR_DEVICE = "device"
ATTR_PHONE_NUMBER = "phone_number"
ATTR_REASON = "reason"

# GSM 7-bit alphabet (basic chars, digits, common symbols)
GSM_7BIT_ALPHABET = r'^[A-Za-z0-9 \t\n.,!?()"\'@#$%^&*-_=+;:<>\£\€\¥\§\¿\¡]+$'


class EndedReason(str, Enum):
    NOT_ANSWERED = "not_answered"
    DECLINED = "declined"
    ANSWERED = "answered"
