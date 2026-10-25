# Fusion2 macros on the Sonix 64-byte protocol

Decoded from a usbmon capture of Pulsar Fusion2 1.0.5.8 driving a **Pulsar X3 on
the 1K wireless dongle** (`3710:5402`) inside a Windows 11 VM, contributed by
[@f-o-o-g-s](https://github.com/f-o-o-g-s) in
[issue #29](https://github.com/packerlschupfer/pulsar-mouse-linux/issues/29).
Scripts, the decoded exchange list and the VM setup are in
[his gist](https://gist.github.com/f-o-o-g-s/9d816b8da9fa932758c993b35ba61a10).

**Nothing in this file is implemented.** It is recorded here so the capture is not
lost in an issue; macros are not in the app, and this is what they would need.

Offsets are the driver's own, as in `drivers/x2a.py`: byte `[1]` category, `[2]`
register, `[3]` sub-register, `[6]` onwards payload. A read sets bit 7 of the
register (`_build_read()`), so `0x82` is a read of register `0x02`.

## Macro storage — category `0x06`

`[6..7]` is the macro id, u16 LE. It was `01 00` throughout, which is also what
the list answer and the button binding carry for that macro. With one macro
stored and profile 1 active, the capture cannot rule out `[6]` being a profile
byte instead.

| command | request | answer |
|---|---|---|
| `06/82/38` list | — | `[6]` count, `[12..]` ids, u16 LE |
| `06/85/3a` read name | `[6..7]` id, `[8..9]` `00 00`, `[10..11]` length | `[10..11]` name length in bytes, `[12..]` name, UTF-16LE |
| `06/05/3a` write name | `[6..7]` id, `[8..9]` `00 00`, `[10..11]` length, `[12..]` name | echo |
| `06/83/06` data size | `[6..7]` id | `[8..11]` size, u32 LE |
| `06/03/06` set size | `[6..7]` id, `[8..11]` size, u32 LE | echo |
| `06/06/(6+n)` write data | `[6..7]` id, `[8..11]` `00 00 00 00`, `[12..]` n bytes | echo |
| `06/86/(6+n)` read data | `[6..7]` id, `[8..11]` `00 00 00 00` | `[12..]` n bytes |
| `06/04/02` delete | `[6..7]` id | echo |

The zero fields look like offsets, for a name or a macro too long for one report,
but the macro captured was small enough that only zeros were ever seen. Fusion2
asks for a name with length 0 first, and that answer already carries both the
length and the name.

Answers also carry leftover bytes from earlier replies after the real answer, so
only the bytes named above mean anything — the same latched-reply behaviour
`xlite_v4_wireless.py`'s `_transact()` exists to deal with.

## Macro data

The macro was "test" — `a` down, `a` up, `b` down, `b` up, 50 ms between steps —
stored as 14 bytes, two per step:

```
03 04  0c 32  04 04  0c 32  03 05  0c 32  04 05
```

- `03 kk` key down, `kk` the HID usage (`04` = a, `05` = b)
- `04 kk` key up
- `0c 32` delay, 50 ms

Only plain key steps were recorded, so whatever else the editor can store is not
in here. Stopping the recorder wrote the macro at once (set size `0x0e`, data,
name), and Fusion2's Save button deleted it and wrote it again the same way.

## Binding a macro to a button

The same `04/01/06` that `set_button()` uses: `[6]` profile, `[7]` button, `[8]`
type, `[9..]` data.

| type | data | e.g. button `05`, macro 1 |
|---|---|---|
| `04` run N times | `[9..10]` id, `[11]` N | `04 01 00 01`, `04 01 00 03` |
| `05` repeat while held | `[9..10]` id | `05 01 00` |
| `06` repeat until pressed again | `[9..10]` id | `06 01 00` |

Types `0x04`–`0x06` are not in `hid.py`'s vocabulary (`BTN_TYPE_*` uses `0x00`–
`0x03`, `0x08`, `0x09`, `0x0d`, `0x0e`), so nothing is misread today:
`describe_button()` falls through to `type=0x04 a1=0x01 a2=0x00`. Such a string
is not something `parse_button_function()` accepts, so a profile file exported
with a macro on a button warns on that one button when it is imported and leaves
the binding alone.

Note that "run N times" needs one payload byte more than `set_button()` writes
and `get_button()` reads.

## Playback

The mouse plays the macro itself: the keystrokes arrive as **report `03` on the
dongle's interface 1**, with no command from the PC in between. That interface's
report descriptor declares report `03` as a keyboard — a modifier byte then 14
key bytes — so the kernel should type them on Linux with nothing of ours running.
Untested on Linux.

While a button had a macro on it, its bit never appeared in interface 0's button
byte; only the `04 10` on interface 1.

| binding | observed |
|---|---|
| run 1 | per press: `03 00 04`, `03 00 00`, `03 00 05`, `03 00 00`, 24–26 ms apart — the stored 50 ms played as about 25 |
| run 3 | one press typed "ab" three times, still going after the release |
| repeat while held | held 1.6 s, "ab" 21 times, stopped at the release |
| repeat until pressed again | "ab" 43 times and one more "a", then a second press 3.3 s later stopped it before the "b" |

The DPI button (`0b`) accepted `04 01 00 01` and read it back, but two presses
played nothing — only its `04 20` / `04 00`, and no `05 05` DPI report either.
The side button played every time.
