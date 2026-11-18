# Philips ORT7500 remote control

Tools for controlling a **Philips ORT7500** DAB+/FM radio over Bluetooth, without the official
Philips DigitalRadio app.

The radio speaks Frontier Silicon's binary FSAPI ("NetRemote") over Bluetooth Classic SPP
(RFCOMM channel 1, no pairing PIN or session). The protocol was reverse-engineered from the
Android app `com.philips.cl.dabradio` 1.0.0, then checked against a real radio.

## Contents

| Path | What it is |
|---|---|
| [`PROTOCOL.md`](PROTOCOL.md) | Wire protocol: framing, checksum, GET/SET/LIST commands, responses, node table, worked examples |
| [`fsbt.py`](fsbt.py) | Command-line client (Python 3 standard library only, Linux/BlueZ) |
| [`web/`](web/) | Browser remote (single `index.html` using Web Serial), see [`web/README.md`](web/README.md) |
| [`scan-results.txt`](scan-results.txt) | Result of reading every known node on a real ORT7500 |

## Quick start

Pair the radio first:

```bash
bluetoothctl    # power on / scan on / pair <MAC> / trust <MAC> / quit
```

Then use the CLI:

```bash
python3 fsbt.py <MAC> get sys.info.friendlyName sys.power sys.audio.volume
python3 fsbt.py <MAC> set sys.power ON
python3 fsbt.py <MAC> set volume 10            # node names can be suffixes
python3 fsbt.py <MAC> list sys.caps.validModes
python3 fsbt.py <MAC> listen                   # live notifications from the radio
python3 fsbt.py - nodes                        # list known nodes (offline)
python3 fsbt.py - set sys.power ON             # print the bytes without connecting
```

Add `-v` to see the raw TX/RX bytes.

Or run the web remote:

```bash
cd web && python3 -m http.server 8000
```

Open <http://localhost:8000> in Chrome, Chromium or Edge and click **Connect**.

## Known quirks

- Only one connection at a time: close `fsbt.py` before opening the web page, and the other way round.
- `nav.state` turns itself off after a while. Set it ON again before using `nav.*` actions.
- On firmware V5.1.7, `nav.action.selectPreset` returns OK but does nothing. The workaround is to
  find the preset's station in `nav.list` and select it with `nav.action.selectItem`.

## Disclaimer

This is an unofficial project with no connection to Philips or Frontier Silicon. The original APK is not
included in this repository.
