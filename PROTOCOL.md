# Philips ORT7500 – Bluetooth control protocol

Source: `Philips+DigitalRadio_1.0.0_APKPure.apk` (package `com.philips.cl.dabradio`), which uses
Frontier Silicon's `NetRemoteLib`, transport class `RadioBluetooth`. It's the binary version of
Frontier's FSAPI ("netRemote.*" nodes) carried over Bluetooth Classic SPP.
Everything here comes from the app's code and hasn't been checked against a real radio yet.

## 1. Link

| | |
|---|---|
| Transport | Bluetooth Classic, RFCOMM (SPP), **channel 1** (`createRfcommSocket(1)`) |
| Greeting | Once connected, the radio sends ASCII **`Philips_001`** (no framing). The app treats a device as a radio only if this string arrives. The library default is `Frontier-Silicon`. |
| Auth | None. `RequiresPIN() = false`, no session and no PIN. |
| Flow | One request in flight at a time. The app waits for the reply before sending the next request. |

## 2. Framing

```
C0 | payload ... | checksum | C0          (SLIP)
```
* SLIP escaping: `C0 → DB DC`, `DB → DB DD` (applies to payload and checksum).
* Checksum over the payload (Fletcher-8 variant):
  ```
  s1 = s2 = 0
  for b in payload: s1 = (s1 + b) & 0xFF; s2 = (s2 + s1) & 0xFF
  checksum = s1 ^ s2
  ```
  On receive, `0xEF` is also accepted as "no checksum".
* All multi-byte integers are **big-endian**.
* Bytes 0-1 of every payload are the **frame number** (1…65535, incremented per request). The
  reply carries the same frame number. Frame number `0000` means an unsolicited notification.

## 3. Requests (app → radio)

| Command | Payload |
|---|---|
| GET  (op `00`) | `FF FF 00 01 AA AA AA AA` |
| SET  (op `04`) | `FF FF 04 01 AA AA AA AA LL LL VV…` |
| LIST (op `09`, GET_NEXT_MULTI) | `FF FF 09 AA AA AA AA KK KK KK KK NN FC f1 f2 … 00 00` |

`FF FF` = frame number, `AA×4` = node address, `LL LL` = value length,
`VV` = value (big-endian, 1/2/4 bytes; strings are UTF-8 plus a trailing `00`, and that `00` counts in `LL`).
LIST: `KK×4` = start key (`FFFFFFFF` = start of list), `NN` = max items (≤255),
`FC` = number of non-key fields, followed by field indices `01..FC` and then `00 00`.

Other opcodes defined (unused by the app): `01` LIST_GET, `02` LIST_GET_NEXT, `0A` LIST_GET_PREV_MULTI.

## 4. Responses (radio → app)

| Type | Payload |
|---|---|
| GET reply (`80`) | `FF FF 80 01 SS LL LL VV…` |
| SET reply (`84`) | `FF FF 84 01 SS` |
| LIST reply (`89`) | `FF FF 89 SS NN { KK KK KK KK fc { LL LL data }×fc }×NN` |
| Notification (`C6`) | `00 00 C6 AA AA AA AA VV…` (value with **no** length prefix) |
| Error (`87`) | defined, but the app doesn't handle it |

Status `SS`: `00` OK, `01` LIST_END, `80` PACKET_BAD, `81` NODE_DOES_NOT_EXIST,
`82` ITEM_DOES_NOT_EXIST, `83` NODE_BLOCKED, `85` FAIL.

## 5. Worked examples (frame 1)

| Action | Bytes on the wire |
|---|---|
| Get power | `c0 00 01 00 01 10 10 30 00 8e c0` |
| Power ON | `c0 00 01 04 01 10 10 30 00 00 01 01 a1 c0` |
| Volume = 12 | `c0 00 01 04 01 10 10 51 00 00 01 0c 2d c0` |
| List valid modes | `c0 00 01 09 10 10 21 00 ff ff ff ff ff 03 01 02 03 00 00 56 c0` |

`python3 fsbt.py - set <node> <value>` prints these bytes for any command.

## 6. Most useful nodes

| Node (`netRemote.` prefix omitted) | Addr | Type | Values |
|---|---|---|---|
| sys.power | 10103000 | E8 | 0 OFF, 1 ON |
| sys.mode | 10104000 | U32 | key from `sys.caps.validModes` list |
| sys.caps.validModes | 10102100 | list | key, id, selectable, label |
| sys.audio.volume | 10105100 | U8 | 0…`sys.caps.volumeSteps`−1 |
| sys.audio.mute | 10105200 | E8 | 0 NOT_MUTE, 1 MUTE |
| sys.audio.eqPreset | 10105300 | U8 | key from `sys.caps.eqPresets` |
| sys.audio.eqLoudness | 10105500 | E8 | 0 OFF, 1 ON |
| sys.audio.eqCustom.param0..4 | 10105401..05 | S16 | bass/treble etc. (`sys.caps.eqBands`) |
| play.control | 10305000 | E8 | 0 STOP, 1 PLAY, 2 PAUSE, 3 NEXT, 4 PREVIOUS |
| play.frequency | 1030C000 | U32 | FM in kHz; DAB = key from `sys.caps.dabFreqList`; `FFFFFFFF` = none |
| play.info.name / .text | 10304010 / 20 | C8 | station name / DLS-RDS text |
| play.signalStrength | 1030D000 | U8 | |
| play.status | 10301000 | E8 | IDLE, BUFFERING, PLAYING, PAUSED, REBUFFERING, ERROR |
| play.addPreset | 1030E000 | U32 | store current station into preset N |
| nav.state | 10201000 | E8 | must be ON before using nav.* (app sets it) |
| nav.presets | 10207000 | list | key, name |
| nav.action.selectPreset | 1020A030 | U32 | recall preset key |
| nav.list | 10206000 | list | key, name, type, subType (station list) |
| nav.action.selectItem | 1020A020 | U32 | play station with that key |
| nav.action.navigate | 1020A010 | U32 | enter folder key; `FFFFFFFF` = go up |
| nav.action.dabScan | 1020A050 | E8 | 1 SCAN (full DAB scan) |
| sys.caps.fmFreqRange.lower/upper/stepSize | 10102601..03 | U32 | used for FM up/down tuning |
| sys.clock.localTime / localDate | 10107300 / 200 | C8 | |
| sys.info.friendlyName / version / radioId | 10101010 / 20 / 30 | C8 | |

`python3 fsbt.py - nodes` lists all 104 nodes.

How the app does the common actions:
* **FM tune up/down**: read `fmFreqRange.*` and `play.frequency`, then SET `play.frequency` = current ± step, wrapping at the range ends.
* **Presets**: SET `nav.state` ON, LIST `nav.presets`, SET `nav.action.selectPreset` = key.
  **On the ORT7500 (firmware V5.1.7) `selectPreset` returns OK but does nothing.** Workaround that
  was tested and works: look up the preset's name in `nav.list` and SET `nav.action.selectItem` = that station's key.
* `nav.state` turns itself OFF after a while; set it ON again before nav actions.
* **DAB scan**: SET `nav.state` ON, then `nav.action.dabScan` SCAN. Watch `nav.dabScanUpdate` notifications.
* **Mode**: LIST `sys.caps.validModes`, then SET `sys.mode` = item key.

## 7. Testing from a Linux laptop

```bash
bluetoothctl            # then: power on / scan on / pair <MAC> / trust <MAC> / quit
# optional: `bluetoothctl info <MAC>` should list the Serial Port UUID 00001101-…

python3 fsbt.py <MAC> get sys.info.friendlyName -v      # -v shows raw TX/RX bytes
python3 fsbt.py <MAC> get sys.power sys.mode sys.audio.volume
python3 fsbt.py <MAC> set sys.power ON
python3 fsbt.py <MAC> set volume 10                     # suffix match is fine
python3 fsbt.py <MAC> list sys.caps.validModes
python3 fsbt.py <MAC> dump
python3 fsbt.py <MAC> listen                            # live notifications
python3 fsbt.py <MAC> raw 00 01 10 10 30 00             # hand-made payload (frame + checksum are added)
```
If the connection is refused, the radio may need the app's Bluetooth/remote mode enabled, or
another RFCOMM channel (`-c 2`, `-c 3` …). Bluetooth sockets need Python 3 on Linux with BlueZ.
