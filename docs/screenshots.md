# Regenerating the screenshots

The images in `screenshots/`, shown in the README, are of the real GUI
reading a real mouse. Every number in them came off hardware. That is the
one rule here: no mock-ups, no edited values, no device that isn't actually
plugged in. The current set is a Pulsar X3 on the 1K dongle, taken by
@f-o-o-g-s; `09-tray.png` is older and from a different machine.

It also means **the screenshots can only show what the photographer's mouse
can do**. A wired mouse has no Power page; a mouse without per-stage LEDs has
no colour picker; only the Feinmann Noctua has a fan slider, and only the 1K
dongle reports link quality. If you own a mouse that shows more than the
current set does, a pull request replacing them is welcome.

## The script

```sh
tools/screenshots.py --out screenshots     # all of them
tools/screenshots.py --list                # what it can take
tools/screenshots.py --only 06-power       # just one
```

It runs the GUI in a throwaway X server, so nothing appears on your screen
and nothing steals your pointer — no desktop session, compositor or panel
needed. It drives the real window through the same handlers the UI uses,
waits for the device reads to land, and captures each window by its X11 id.

It also takes your desktop out of the frame, so that two people
photographing the same mouse get the same pictures: the session variables
are unset, `XDG_CONFIG_HOME` points at an empty directory, and the title bar
is fixed to GNOME's single close button. Without that the GUI grows a
"Hyprland Mouse Settings" group under Hyprland and GTK uses whatever theme,
font and icon set is around it. One thing the scrub does not reach is **Start
on Login** — that reads `~/.config/autostart` directly, so it shows your real
setting.

And it won't photograph a sleeping mouse. A wireless one that has nodded off
does not stop answering: the dongle replies for it with 125 Hz, every DPI
stage at its minimum and no battery, and the whole set comes out looking
plausible and completely wrong. The script reads the battery before the first
shot and stops if nothing is home, and checks again at the end in case the
mouse fell asleep partway through — which is easy, since a 30-second sleep
timer is shorter than a full run.

Install first, on Debian/Ubuntu:

```sh
sudo apt install xvfb xdotool imagemagick
```

Plus the GUI's own dependencies, and access to the mouse — the udev rules in
`udev/`, or run it with `sudo`. The script stops with a clear message if no
supported mouse is found, because a screenshot of "no mouse detected" is not
worth taking.

Shots the mouse can't produce are skipped with the reason, so this is
expected output on a wired mouse:

```
skip  06-power   (this mouse has no power page)
```

## What each file is

| File | What it shows | Needs |
|---|---|---|
| `01-home.png` | Home: model, connection, polling rate, DPI — plus battery and connection quality on a wireless mouse | — |
| `02-performance.png` | The long page: polling, debounce, angle snap, ripple, motion sync, lift-off, every DPI stage | — |
| `03-color-picker.png` | The stage-colour chooser | per-stage LEDs |
| `04-customize.png` | Button bindings and LED settings | — |
| `05-remap-button.png` | The button remapping dialog | — |
| `06-power.png` | Battery, charging, sleep timer, low-power threshold | a wireless mouse |
| `07-tools.png` | Autostart, diagnostics, profile import/export | — |
| `08-input-test.png` | The live button/scroll/DPI tester | — |
| `09-tray.png` | The tray icon and its menu | taken by hand, see below |

## The tray shot is manual

A tray icon needs a desktop with a status-icon host, and the private X server
has no panel — so `09-tray.png` can't be automated this way. Take it on your
own desktop:

1. Start `pulsar-mouse-gui` and close its window so it lives in the tray.
2. Open the tray menu and let the battery line populate (up to a minute on
   first run).
3. Capture the icon and open menu together, in your desktop's own
   screenshot tool. Crop to roughly the menu plus a little of the panel —
   the current one is 840×430.

## Conventions

- **Dark theme.** The set is dark; `--theme light` exists but don't mix.
- **640 px wide** for the window shots, so the README's two-column table
  lines up. Heights are measured per page, so a short page isn't mostly
  empty grey. Dialogs come out at their natural size.
- **Keep the file names.** The README references them by name, so replacing
  an image needs no README change.
- **Don't press Apply.** The script never writes to the mouse, and neither
  should you while taking these — a screenshot is not worth changing
  someone's settings over.
- **Keep the mouse awake** for the whole run — move it just before you start.
  The script will tell you if it wasn't, but it can only tell you afterwards.

## If you are handing this to an agent

Everything it needs is the paragraph below plus this file.

> Regenerate the project's screenshots from my mouse. Read
> `docs/screenshots.md`, install what it lists, then run
> `tools/screenshots.py --out screenshots` from the repo root with the mouse
> plugged in. Report which shots were skipped and why, and anything it said
> about the mouse sleeping. Take `09-tray.png` by hand per the manual section
> if the tray is available. Don't touch any setting on the mouse, and don't
> press Apply in the GUI.

Two failure modes are worth knowing in advance, both learned the hard way:

- **A second process using the GUI's application id doesn't start a new
  window** — it wakes the copy already running in your tray and exits
  immediately, looking exactly like the script doing nothing. The script
  takes its own id and `NON_UNIQUE` for this reason; don't "simplify" that
  away.
- **Values need time to arrive.** The window reads the mouse on a worker
  thread as it opens, so a capture taken too early shows blanks or
  placeholder text. The script waits; if you write your own, wait too.
- **A sleeping mouse photographs fine.** It is the dongle answering, not the
  mouse, and nothing in the images says so. The script's battery check is
  what catches it; `--ignore-sleep` exists for a mouse whose battery reading
  is genuinely broken, and skips the only guard there is.
