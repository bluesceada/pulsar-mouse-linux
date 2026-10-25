"""Regression tests for the Nordic family's firmware string (#30).

Command 0x12 answers with two packed-decimal bytes, which the formatter
used to read as numbers - right for the X2 CrazyLight's 03 05 by luck, and
wrong for everything whose minor version reaches 0x10.
"""

import unittest

from pulsar_mouse.drivers.nordic import CMD_FW_VERSION, PulsarNordic
from pulsar_mouse.drivers.x2_crazylight import PulsarX2CrazyLight


def answering(cls, major, minor):
    """`cls` with a transport that answers command 0x12 with those bytes."""

    class Scripted(cls):
        def __init__(self):
            super().__init__()
            self._fd = 17           # pretend hidraw is open
            self.asked = []

        def _send(self, packet):
            self.asked.append(packet[1])

        def _recv(self, timeout_ms=2000):
            body = bytearray(16)
            body[0], body[1] = 0x08, self.asked[-1]
            body[6], body[7] = major, minor
            return bytes(body) + bytes([self._checksum(*body)])

    return Scripted()


class FirmwareStringTests(unittest.TestCase):
    def test_an_xlite_v3_reads_as_fusion_shows_it(self):
        # 02 18: "Mouse V0218" in Fusion, "V2.18" in Pulsar's updater.
        self.assertEqual(
            answering(PulsarNordic, 0x02, 0x18).get_firmware_version(), '2.18')

    def test_the_crazylight_is_unchanged(self):
        # 03 05 reads as 3.05 either way - the case that hid the bug.
        self.assertEqual(
            answering(PulsarX2CrazyLight, 0x03, 0x05).get_firmware_version(),
            '3.05')

    def test_a_dongle_version_keeps_its_trailing_zero(self):
        # 03 00 is "V0300", not "3.0".
        self.assertEqual(
            answering(PulsarNordic, 0x03, 0x00).get_firmware_version(), '3.00')

    def test_a_mouse_that_says_nothing_is_unknown(self):
        class Deaf(PulsarNordic):
            def __init__(self):
                super().__init__()
                self._fd = 17

            def _send(self, packet):
                pass

            def _recv(self, timeout_ms=2000):
                raise IOError('asleep')

        self.assertEqual(Deaf().get_firmware_version(), 'unknown')

    def test_the_command_is_the_one_in_the_capture(self):
        mouse = answering(PulsarNordic, 0x02, 0x18)
        mouse.get_firmware_version()
        self.assertEqual(mouse.asked, [CMD_FW_VERSION])


if __name__ == '__main__':
    unittest.main()
