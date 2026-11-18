# ORT7500 web remote

A single file, `index.html`: plain JavaScript using the Web Serial API, no build step and no dependencies.

## Run

```bash
cd web
python3 -m http.server 8000
```
Open <http://localhost:8000> in **Chromium/Chrome/Edge** (Firefox and Safari don't have Web Serial).
Web Serial needs a secure context, which `localhost` counts as. A page opened as `file://` may not work.

Click **Connect** and pick **PHILIPS ORT7500** (Serial Port) from the list.

## If the radio doesn't show up in the port picker

Chrome only lists Bluetooth SPP devices on some platforms. As a fallback, bind the radio to a
classic serial device and pick `/dev/rfcomm0` instead:

```bash
sudo pacman -S bluez-deprecated-tools          # provides `rfcomm` on Arch
sudo rfcomm bind 0 00:1D:DF:DF:26:79 1
sudo chmod a+rw /dev/rfcomm0                   # or add yourself to the `uucp` group
```

Only one program can hold the connection at a time, so close `fsbt.py` and the page before switching between them.

## What it does

Power, mute, volume, mode (DAB/FM/Smart Device/AUX), FM step tuning, presets
(click to recall; right-click to store the current station), the station list (folders are
browsable, and ↑ goes up a folder), now-playing name and text, signal strength, and the clock. It
also handles live notifications from the radio. Raw TX/RX bytes are in the Log panel.

## Android phone

Chrome on Android supports Web Serial over Bluetooth from version 137, but only on HTTPS or localhost pages.
To use the page from the laptop's server over Wi-Fi:

1. On the laptop: `python3 -m http.server 8000 --bind 0.0.0.0` (or bind to the laptop's LAN IP).
2. On the phone, in Chrome, open `chrome://flags`, search for **Insecure origins treated as secure**,
   enable it, enter `http://<laptop-ip>:8000`, and relaunch Chrome.
3. Pair the radio with the phone in Android's Bluetooth settings.
4. Open `http://<laptop-ip>:8000`, tap **Connect** and pick the ORT7500.

The radio allows one serial connection at a time, so disconnect the laptop (page or `fsbt.py`) first.
