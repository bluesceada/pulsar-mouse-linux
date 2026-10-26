"""Regression tests for the phantom right-hand buttons (#30).

Four models share 3554:f507 and f508, and only one of them - the X2A
Wireless, KM=14 - has the right-hand thumb pair this driver's button table
was built from.  On the other three those slots hold something else, so a
mouse whose MID names one of them refuses both rather than reading a binding
that is not one and writing over whatever its firmware keeps there.

MID values from Fusion's Cfg.ini, contributed by @bluesceada; mid=7
corroborated on his own mouse by the CheckPsd read.
"""

import unittest

from pulsar_mouse.base import PulsarDevice
from pulsar_mouse.drivers.nordic import (
    KM_RIGHT_FLANK,
    MODELS_BY_MID,
    PulsarNordic,
)

XLITE_V3, X2A_WIRELESS, X2_V2, X2_V2_MINI = 0x07, 0x08, 0x0A, 0x0B


def mouse(mid=None, deaf=False):
    """A Nordic mouse whose handshake answers with `mid`, or not at all."""

    class Scripted(PulsarNordic):
        def __init__(self):
            super().__init__()
            self._fd = 17
            self._mem = {addr: 0x01 for addr in range(0x60, 0x90)}
            self.handshakes = 0

        def _send(self, packet):
            self.last = packet

        def _recv(self, timeout_ms=2000):
            self.handshakes += 1
            if deaf:
                raise IOError('asleep')
            body = bytearray(16)
            body[0], body[1] = 0x08, self.last[1]
            body[10], body[11] = 0x06, mid
            return bytes(body) + bytes([self._checksum(*body)])

        def _ensure_profile(self, profile):
            pass

    return Scripted()


class AbsentButtonTests(unittest.TestCase):
    def ids(self, device, *names):
        return [device.capabilities.buttons[n] for n in names]

    def test_a_six_button_model_refuses_the_right_flank(self):
        for mid in (XLITE_V3, X2_V2, X2_V2_MINI):
            device = mouse(mid)
            for btn_id in self.ids(device, *KM_RIGHT_FLANK):
                with self.assertRaises(NotImplementedError):
                    device.get_button(btn_id, 1)
                with self.assertRaises(NotImplementedError):
                    device.set_button(btn_id, 0x01, 0x01, 0x00, 1)

    def test_it_keeps_the_six_it_has(self):
        device = mouse(XLITE_V3)
        for btn_id in self.ids(device, 'left', 'right', 'wheel',
                               'thumb1', 'thumb2', 'dpi'):
            self.assertIsNotNone(device.get_button(btn_id, 1))

    def test_the_x2a_wireless_keeps_all_eight(self):
        device = mouse(X2A_WIRELESS)
        for btn_id in device.capabilities.buttons.values():
            self.assertIsNotNone(device.get_button(btn_id, 1))

    def test_a_mouse_that_will_not_say_keeps_all_eight(self):
        # Today's behaviour, and the safer way round: hiding two real
        # buttons from an X2A Wireless whose read failed would be worse than
        # leaving them, which is what the README has always warned about.
        device = mouse(deaf=True)
        for btn_id in device.capabilities.buttons.values():
            self.assertIsNotNone(device.get_button(btn_id, 1))

    def test_an_unknown_mid_keeps_all_eight(self):
        device = mouse(0x7F)
        for btn_id in device.capabilities.buttons.values():
            self.assertIsNotNone(device.get_button(btn_id, 1))

    def test_the_model_is_asked_once(self):
        device = mouse(X2A_WIRELESS)
        for _ in range(4):
            device.get_button(device.capabilities.buttons['thumb3'], 1)
        self.assertEqual(device.handshakes, 1)

    def test_a_deaf_mouse_is_asked_again(self):
        # Nothing is cached from a refusal, so a mouse that wakes up later
        # gets its buttons judged properly.
        device = mouse(deaf=True)
        for _ in range(3):
            device.get_button(device.capabilities.buttons['thumb3'], 1)
        self.assertEqual(device.handshakes, 3)

    def test_the_six_every_model_has_are_not_worth_asking_about(self):
        # No model is missing these, so reading them costs no handshake.
        device = mouse(XLITE_V3)
        for name in ('left', 'right', 'wheel', 'thumb1', 'thumb2', 'dpi'):
            device.get_button(device.capabilities.buttons[name], 1)
        self.assertEqual(device.handshakes, 0)

    def test_the_model_is_named(self):
        self.assertEqual(mouse(XLITE_V3).model_name(), 'Pulsar Xlite V3')
        self.assertEqual(mouse(X2A_WIRELESS).model_name(),
                         'Pulsar X2A Wireless')
        self.assertIsNone(mouse(deaf=True).model_name())

class RefineTests(unittest.TestCase):
    """What the window is built from, once the MID says which mouse it is."""

    def test_a_six_button_model_loses_the_right_flank(self):
        device = mouse(XLITE_V3)
        self.assertTrue(device.refine_capabilities())
        caps = device.capabilities
        self.assertEqual(caps.name, 'Pulsar Xlite V3')
        self.assertEqual(sorted(caps.buttons),
                         ['dpi', 'left', 'right', 'thumb1', 'thumb2', 'wheel'])
        self.assertNotIn('thumb3', caps.button_labels)

    def test_the_x2a_wireless_keeps_its_eight_and_gains_a_name(self):
        device = mouse(X2A_WIRELESS)
        self.assertTrue(device.refine_capabilities())
        caps = device.capabilities
        self.assertEqual(caps.name, 'Pulsar X2A Wireless')
        self.assertEqual(len(caps.buttons), 8)
        self.assertIn('thumb3', caps.buttons)

    def test_the_class_is_left_alone(self):
        # Only this instance is narrowed: scan_devices() reads the class.
        before = dict(PulsarNordic.capabilities.buttons)
        mouse(XLITE_V3).refine_capabilities()
        self.assertEqual(PulsarNordic.capabilities.buttons, before)
        self.assertEqual(len(before), 8)

    def test_the_second_call_changes_nothing(self):
        # The GUI rebuilds its pages on a True, so a driver that kept
        # saying True would rebuild them on every read.
        device = mouse(XLITE_V3)
        self.assertTrue(device.refine_capabilities())
        self.assertFalse(device.refine_capabilities())
        self.assertFalse(device.refine_capabilities())

    def test_a_mouse_that_will_not_say_is_left_as_the_family(self):
        device = mouse(deaf=True)
        self.assertFalse(device.refine_capabilities())
        self.assertEqual(device.capabilities, PulsarNordic.capabilities)

    def test_an_unknown_mid_is_left_as_the_family(self):
        device = mouse(0x7F)
        self.assertFalse(device.refine_capabilities())
        self.assertEqual(device.capabilities, PulsarNordic.capabilities)

    def test_every_other_driver_refines_nothing(self):
        from pulsar_mouse.drivers import discover_all
        for name, cls in discover_all().items():
            if issubclass(cls, PulsarNordic):
                continue
            device = cls.__new__(cls)
            self.assertFalse(PulsarDevice.refine_capabilities(device), name)


class CfgIniTests(unittest.TestCase):
    def test_the_table_is_the_one_from_the_cfg_ini(self):
        self.assertEqual(
            {mid: km for mid, (_name, km) in MODELS_BY_MID.items()},
            {0x07: 10, 0x08: 14, 0x0A: 10, 0x0B: 10})


if __name__ == '__main__':
    unittest.main()
