"""Regression tests for the GUI's whole-pass rule across more than one pass
(#24).

v0.1.21 stopped Apply writing widgets that were never read, by way of
_dpi_loaded; it only ever went back to False in MainWindow.__init__, so the
rule guarded a window's first read and nothing after it.  @f-o-o-g-s found
what that left: a later pass that loses a field keeps the one before it,
which on a profile switch is another profile's values, and Apply writes them
into the profile now selected - with no banner, because that was suppressed
on an already-loaded page too.

MainWindow is built with __new__ and given recording stand-ins for its
widgets: _populate_profile_inner() and _apply() are the two methods that
decide this, and they touch nothing else.  No display needed.
"""

import unittest

try:
    from pulsar_mouse.gui import MainWindow
except (ImportError, ValueError) as e:      # no GTK 4 / libadwaita here
    MainWindow = None
    _why = e

from pulsar_mouse.drivers.xlite_v4_wireless import PulsarXliteV4Wireless

PROFILE_1 = {'active': 1, 'count': 2, 'stages': [(800, 800), (1600, 1600)]}
PROFILE_2 = {'active': 1, 'count': 2, 'stages': [(400, 400), (3200, 3200)]}


class Row:
    """A widget that records what the page does to it."""

    def __init__(self, value=None):
        self.value, self.selected = value, None

    def set_value(self, v):
        self.value = v

    def get_value(self):
        return self.value

    def set_selected(self, i):
        self.selected = i

    def get_selected(self):
        return self.selected or 0

    def __getattr__(self, _name):
        return lambda *a, **kw: None


def page():
    """A window whose reads and writes are recorded rather than made."""
    caps = PulsarXliteV4Wireless.capabilities
    w = MainWindow.__new__(MainWindow)
    w._caps = caps
    w._profile = 1
    w._building = False
    w._device = None
    w._dpi_loaded = False
    w._read_complete = False
    w.errors, w.applied = [], []
    w._show_error = w.errors.append
    w._show_toast = lambda msg: None
    w._run_bg = lambda fn, *args: fn(*args)
    w._do_apply = w.applied.append
    w._lod_row = Row()
    w._stage_count_row = Row(2)
    w._active_stage_row = Row()
    w._poll_row = Row()
    w._dpi_rows = [Row() for _ in range(caps.max_dpi_stages)]
    w._color_buttons = []
    for name in ('_bright_row', '_led_row', '_breathe_row',
                 '_breathe_row_container', '_home_dpi_row', '_home_mode_row',
                 '_debounce_row', '_angle_row', '_ripple_row', '_motion_row',
                 '_turbo_row', '_fan_row', '_power_saving_row',
                 '_low_power_row'):
        setattr(w, name, None)
    return w


def read(w, dpi_info, lod=1, read_all=True):
    w._populate_profile_inner(lod, None, None, None, dpi_info, None, {},
                              read_all)


@unittest.skipIf(MainWindow is None, 'needs GTK 4 and libadwaita')
class PageTrustTests(unittest.TestCase):
    def test_a_complete_pass_lets_apply_write(self):
        w = page()
        read(w, PROFILE_1)
        w._apply()
        self.assertEqual(w.errors, [])
        self.assertEqual(w.applied[-1]['lod'], 1)
        self.assertEqual(w.applied[-1]['dpi_values'][:2], [800, 1600])

    def test_a_later_pass_that_loses_a_field_stops_apply(self):
        # Profile 1 read in full, then profile 2 with its lift-off lost: the
        # row still holds profile 1's 1 mm, and Apply used to write it into
        # profile 2 over the 0.7 mm that was there.
        w = page()
        read(w, PROFILE_1)
        w._profile = 2
        read(w, PROFILE_2, lod=None, read_all=False)
        self.assertIn('reload before applying', w.errors[-1])
        w.applied.clear()
        w._apply()
        self.assertEqual(w.applied, [])
        self.assertIn('reload before applying', w.errors[-1])

    def test_a_lost_dpi_read_on_a_later_pass_stops_apply_too(self):
        # Not only lift-off: the DPI rows keep the profile before them, and
        # the stage list and the active stage always go out together.
        w = page()
        read(w, PROFILE_1)
        w._profile = 2
        read(w, None, read_all=False)
        self.assertEqual([r.value for r in w._dpi_rows[:2]], [800, 1600])
        w.applied.clear()
        w._apply()
        self.assertEqual(w.applied, [])

    def test_a_complete_pass_after_it_lets_apply_write_again(self):
        w = page()
        read(w, PROFILE_1)
        w._profile = 2
        read(w, PROFILE_2, lod=None, read_all=False)
        read(w, PROFILE_2, lod=2)
        w.applied.clear()
        w._apply()
        self.assertEqual(w.applied[-1]['lod'], 2)
        self.assertEqual(w.applied[-1]['dpi_values'][:2], [400, 3200])

    def test_a_first_pass_that_read_nothing_is_unchanged(self):
        # The v0.1.21 message and its reason: these widgets are on their
        # construction values, and something retries that read on a timer.
        w = page()
        read(w, None, lod=None, read_all=False)
        self.assertIn('may be asleep', w.errors[-1])
        w._apply()
        self.assertEqual(w.applied, [])
        self.assertIn('Nothing has been read', w.errors[-1])


if __name__ == '__main__':
    unittest.main()
