# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import asyncio

from homeassistant.exceptions import HomeAssistantError

from ..const import _LOGGER, EndedReason
from ..modem import Modem


class ATDialer:
    at_command = "ATD"

    def __init__(self, dial_timeout_sec: int, call_duration_sec: int):
        self._dial_sec = dial_timeout_sec
        self._call_sec = call_duration_sec

    async def dial(self, modem: Modem, phone_number: str) -> EndedReason:
        _LOGGER.debug(f"Dialing +{phone_number}...")
        try:
            lines = await modem.execute_at(
                f"{self.at_command}+{phone_number};",
                timeout=10,
                end_markers=["OK", "ERROR", "BUSY", "NO CARRIER", "+CME ERROR"]
            )
            reply = " ".join(lines)
            _LOGGER.debug(f"Modem replied with {reply}")

            if not lines:
                raise HomeAssistantError(f"No response from the modem while dialing +{phone_number}")

            if "BUSY" in reply:
                raise HomeAssistantError("Busy")

            if "ERROR" in reply or "NO CARRIER" in reply:
                raise HomeAssistantError(f"Modem replied with an error: {reply}")

            ended_reason = await self._wait_for_answer(modem)
            _LOGGER.info(f"Call ended: {ended_reason}")
            return ended_reason
        finally:
            # Also sent on errors: the call may have been placed even if the reply got lost
            _LOGGER.debug("Hanging up...")
            modem.send_command("AT+CHUP")

    async def _wait_for_answer(self, modem: Modem) -> EndedReason:
        _LOGGER.debug(f"Waiting up to {self._dial_sec} seconds for answer...")

        is_ringing = False
        modem_responding = False
        try:
            async with asyncio.timeout(self._dial_sec) as timeout:
                while True:
                    # Provisioning:     +CLCC: 1,0,2…
                    # Phone is ringing: +CLCC: 1,0,3…
                    # Answered:         +CLCC: 1,0,0…
                    # Declined:         Nothing, OK only
                    lines = await modem.execute_at(
                        "AT+CLCC",
                        timeout=2,
                        end_markers=["OK", "ERROR", "+CME ERROR"]
                    )
                    reply = " ".join(lines)
                    _LOGGER.debug(f"Modem replied with {reply}")

                    modem_responding = bool(lines)
                    if not modem_responding:
                        await asyncio.sleep(1)
                        continue

                    if not is_ringing and "+CLCC: 1,0,3" in reply:
                        is_ringing = True
                        _LOGGER.info(f"Callee's phone started ringing, waiting for {self._call_sec} seconds...")
                        new_deadline = asyncio.get_running_loop().time() + self._call_sec
                        timeout.reschedule(new_deadline)
                        continue

                    if "+CLCC: 1,0,0" in reply:
                        return EndedReason.ANSWERED

                    if "+CLCC: 1,0" not in reply:
                        return EndedReason.DECLINED

                    # Intervals lower than 1 sec are causing "+CME ERROR: 100" on some modems
                    await asyncio.sleep(1)
        except TimeoutError:
            if not modem_responding:
                raise HomeAssistantError("No response from the modem while waiting for an answer")
            return EndedReason.NOT_ANSWERED
