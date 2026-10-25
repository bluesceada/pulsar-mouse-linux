"""Regression tests for the X3's lift-off distance (x3.py, #24): byte 7 is a
mode and byte 8 the distance in tenths of a millimetre, which is what Fusion2
itself writes - unlike the X2A, whose register x2a.py's table came from."""

import unittest

from pulsar_mouse.base import PulsarDevice
from pulsar_mouse.drivers.x2a import PulsarX2A
from pulsar_mouse.drivers.x3 import PulsarX3


def scripted(cls, byte7=0x02, byte8=0x0a):
    """`cls` with a transport that records writes and answers a read of
    07/82/03 with `byte7`/`byte8`, as a mouse holding that pair would."""

    class Scripted(cls):
        def __init__(self):
            super().__init__()
            self.sent = []

        def _set_report(self, data):
            self.sent.append(bytes(data))

        def _get_report(self):
            rsp = bytearray(self.sent[-1])
            rsp[0] = 0x01
            if rsp[1:4] == bytes([0x07, 0x82, 0x03]):
                rsp[7], rsp[8] = byte7, byte8
            return bytes(rsp)

    return Scripted()


class X3LodTests(unittest.TestCase):
    def test_the_three_fusion2_settings_round_trip(self):
        for mm, pair in ((0.7, (0x02, 0x07)),
                         (1, (0x02, 0x0a)),
                         (2, (0x02, 0x14))):
            mouse = scripted(PulsarX3, *pair)
            mouse.set_lod(mm, 1)
            self.assertEqual(mouse.sent[-1][1:4], bytes([0x07, 0x02, 0x03]))
            self.assertEqual(mouse.sent[-1][6], 1)
            self.assertEqual(tuple(mouse.sent[-1][7:9]), pair)
            self.assertEqual(mouse.get_lod(1), mm)

    def test_the_stock_pair_is_one_millimetre_not_two(self):
        # 02 0a is what an X3 ships on, and what x2a.py's get_lod() called
        # "2 mm" because it read the mode byte.
        self.assertEqual(scripted(PulsarX3, 0x02, 0x0a).get_lod(1), 1.0)
        self.assertEqual(scripted(PulsarX2A, 0x02, 0x0a).get_lod(1), 2)

    def test_a_pair_this_app_wrote_reads_as_one_millimetre(self):
        # Neither mode 0 (the old "1 mm") nor mode 1 (the old "2 mm") says a
        # distance; both landed at or near the mouse's 1 mm.
        self.assertEqual(scripted(PulsarX3, 0x00, 0x00).get_lod(1), 1.0)
        self.assertEqual(scripted(PulsarX3, 0x01, 0x01).get_lod(1), 1.0)

    def test_a_value_the_mouse_cannot_be_set_to_is_refused(self):
        mouse = scripted(PulsarX3)
        for mm in (0, 0.5, 1.5, 3):
            with self.assertRaisesRegex(ValueError, 'LOD must be one of'):
                mouse.set_lod(mm, 1)
        self.assertEqual(mouse.sent, [])

    def test_lod_values_are_what_fusion2_offers(self):
        self.assertEqual(PulsarX3.capabilities.lod_values, [0.7, 1, 2])


class OldExportTests(unittest.TestCase):
    def test_an_old_export_restores_the_mouse_s_one_millimetre(self):
        for version in (1, 2):
            for saved in (1, 2):
                mouse = scripted(PulsarX3)
                mouse.import_profile(1, {'version': version, 'lod_mm': saved})
                self.assertEqual(tuple(mouse.sent[-1][7:9]), (0x02, 0x0a))

    def test_a_current_export_is_taken_as_written(self):
        mouse = scripted(PulsarX3)
        mouse.import_profile(1, {'version': 3, 'lod_mm': 2})
        self.assertEqual(tuple(mouse.sent[-1][7:9]), (0x02, 0x14))

    def test_exports_say_version_3(self):
        mouse = scripted(PulsarX3)
        self.assertEqual(mouse.export_profile(1)['version'], 3)

    def test_no_other_driver_translates_an_old_lod(self):
        self.assertIs(PulsarDevice._PRE_V3_EXPORTS_LOD_IS_MODE_BYTE, False)
        self.assertIs(PulsarX2A._PRE_V3_EXPORTS_LOD_IS_MODE_BYTE, False)
        mouse = scripted(PulsarX2A, 0x01, 0x00)
        mouse.import_profile(1, {'version': 1, 'lod_mm': 2})
        self.assertEqual(tuple(mouse.sent[-1][7:9]), (0x01, 0x01))


if __name__ == '__main__':
    unittest.main()
