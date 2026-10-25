"""Regression tests for the X3's lift-off distance (#24): byte 7 is a mode and
byte 8 the distance in tenths of a millimetre, which is what Fusion2 itself
writes - unlike the X2A, whose register x2a.py's table came from.  Also the 1K
dongle, which uses that encoding only while it is carrying such a mouse."""

import unittest

from pulsar_mouse.base import PulsarDevice
from pulsar_mouse.drivers.x2a import PulsarX2A
from pulsar_mouse.drivers.x3 import PulsarX3
from pulsar_mouse.drivers.xlite_v4 import PulsarXliteV4
from pulsar_mouse.drivers.xlite_v4_wireless import PulsarXliteV4Wireless

X3_PID = 0x3409
XLITE_V4_PID = 0x3401


def scripted(cls, byte7=0x02, byte8=0x0a, paired=X3_PID, pairing=True):
    """`cls` with a transport that records writes and answers a read of
    07/82/03 with `byte7`/`byte8`, as a mouse holding that pair would.

    A read of 01/84/04 is answered with `paired` as the cabled PID the
    dongle is carrying, or refused when `pairing` is False, as a dongle that
    will not say would.
    """

    class Scripted(cls):
        def __init__(self):
            super().__init__()
            self.sent = []
            self.pairing_reads = 0

        def _set_report(self, data):
            self.sent.append(bytes(data))

        def _get_report(self):
            rsp = bytearray(self.sent[-1])
            rsp[0] = 0x01
            if rsp[1:4] == bytes([0x07, 0x82, 0x03]):
                rsp[7], rsp[8] = byte7, byte8
            elif rsp[1:4] == bytes([0x01, 0x84, 0x04]):
                self.pairing_reads += 1
                if not pairing:
                    raise IOError('the dongle will not say')
                rsp[6:10] = bytes([0x10, 0x37,
                                   paired & 0xFF, paired >> 8])
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
        self.assertIs(PulsarDevice._lod_export_is_mode_byte(
            scripted(PulsarX2A)), False)
        mouse = scripted(PulsarX2A, 0x01, 0x00)
        mouse.import_profile(1, {'version': 1, 'lod_mm': 2})
        self.assertEqual(tuple(mouse.sent[-1][7:9]), (0x01, 0x01))


class DongleTests(unittest.TestCase):
    """The dongle follows the mouse it is carrying."""

    def test_an_x3_on_the_dongle_gets_the_tenths_encoding(self):
        dongle = scripted(PulsarXliteV4Wireless, 0x02, 0x0a, paired=X3_PID)
        self.assertEqual(dongle.get_lod(1), 1.0)
        dongle.set_lod(2, 1)
        self.assertEqual(tuple(dongle.sent[-1][7:9]), (0x02, 0x14))

    def test_another_mouse_on_the_dongle_keeps_the_x2a_encoding(self):
        dongle = scripted(PulsarXliteV4Wireless, 0x01, 0x00,
                          paired=XLITE_V4_PID)
        self.assertEqual(dongle.get_lod(1), 2)      # byte 7, x2a.py's table
        dongle.set_lod(2, 1)
        self.assertEqual(tuple(dongle.sent[-1][7:9]), (0x01, 0x01))

    def test_a_dongle_that_will_not_say_reads_nothing(self):
        # Not the X2A encoding as a fallback: see _lod_is_tenths().
        dongle = scripted(PulsarXliteV4Wireless, 0x01, 0x00, pairing=False)
        with self.assertRaises(IOError):
            dongle.get_lod(1)

    def test_the_pairing_is_asked_once_per_open(self):
        dongle = scripted(PulsarXliteV4Wireless, paired=X3_PID)
        for _ in range(3):
            dongle.get_lod(1)
        self.assertEqual(dongle.pairing_reads, 1)

    def test_a_refused_ask_writes_nothing(self):
        dongle = scripted(PulsarXliteV4Wireless, 0x02, 0x0a, pairing=False)
        with self.assertRaises(IOError):
            dongle.set_lod(2, 1)
        self.assertEqual([p[1:4] for p in dongle.sent],
                         [bytes([0x01, 0x84, 0x04])])

    def test_only_an_answer_is_remembered(self):
        # Nothing is cached from a refusal, so the next call asks again
        # rather than carrying a guess through the rest of the open.
        dongle = scripted(PulsarXliteV4Wireless, 0x01, 0x00, pairing=False)
        for _ in range(2):
            with self.assertRaises(IOError):
                dongle.get_lod(1)
        self.assertEqual(dongle.pairing_reads, 2)

    def test_a_read_and_a_later_open_s_write_cannot_disagree(self):
        # @f-o-o-g-s's case: the GUI reads the page in one open and applies
        # in a later one, so a refusal in either of them used to be a guess
        # that the other one did not share.  An X3 holding 02 0a (1 mm) with
        # the page read's ask lost: the row showed 2 mm and the Apply after
        # it wrote 02 14, moving a mouse nobody had touched to 2 mm (#24).
        dongle = scripted(PulsarXliteV4Wireless, 0x02, 0x0a, pairing=False)
        with self.assertRaises(IOError):
            dongle.get_lod(1)       # the page has no value to apply
        self.assertEqual(dongle.sent[-1][1:4], bytes([0x01, 0x84, 0x04]))

    def test_a_new_open_asks_again(self):
        dongle = scripted(PulsarXliteV4Wireless, 0x02, 0x0a, paired=X3_PID)
        dongle.get_lod(1)
        dongle._lod_tenths = None       # as open() does
        dongle.get_lod(1)
        self.assertEqual(dongle.pairing_reads, 2)

    def test_the_dongle_offers_the_two_every_fusion2_mouse_has(self):
        # Not the X3's 0.7 mm: capabilities are a class variable.
        self.assertEqual(PulsarXliteV4Wireless.capabilities.lod_values, [1, 2])
        dongle = scripted(PulsarXliteV4Wireless, paired=X3_PID)
        with self.assertRaisesRegex(ValueError, 'LOD must be one of'):
            dongle.set_lod(0.7, 1)

    def test_an_old_import_warns_when_the_dongle_will_not_say(self):
        # The version check asks the same question, and it used to sit
        # outside import_profile()'s try, so a refusal stopped the import
        # where it stood - after the DPI write, with nothing said (#24).
        dongle = scripted(PulsarXliteV4Wireless, pairing=False)
        warnings = dongle.import_profile(1, {'version': 2, 'lod_mm': 2,
                                             'brightness': 0x80})
        self.assertTrue(any('LOD' in w for w in warnings), warnings)
        # ...and the brightness after it still went out.
        self.assertEqual(dongle.sent[-1][1:4], bytes([0x03, 0x03, 0x03]))

    def test_an_old_export_translates_only_for_a_tenths_mouse(self):
        dongle = scripted(PulsarXliteV4Wireless, paired=X3_PID)
        dongle.import_profile(1, {'version': 2, 'lod_mm': 2})
        self.assertEqual(tuple(dongle.sent[-1][7:9]), (0x02, 0x0a))

        other = scripted(PulsarXliteV4Wireless, paired=XLITE_V4_PID)
        other.import_profile(1, {'version': 2, 'lod_mm': 2})
        self.assertEqual(tuple(other.sent[-1][7:9]), (0x01, 0x01))

    def test_the_cabled_xlite_v4_is_untouched(self):
        self.assertIs(PulsarXliteV4.get_lod, PulsarX2A.get_lod)
        self.assertIs(PulsarXliteV4.set_lod, PulsarX2A.set_lod)


if __name__ == '__main__':
    unittest.main()
