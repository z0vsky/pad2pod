# footpod-back

Reads speed from a WalkingPad C2 over BLE and broadcasts it as an ANT+ foot pod (SDM profile).

## Hardware

- Kingsmith WalkingPad C2
- Dynastream ANTUSB2 stick (ANT+)
- USB Bluetooth dongle

## Setup

Install dependencies:

```
uv sync
```

ANT+ USB stick udev rule (to run without sudo):

```
uv run python -m openant install
```


Terminal 1 — read walking pad speed:

```
uv run walkingpad_ble.py
```

Terminal 2 — broadcast as ANT+ foot pod:

```
uv run antplus-footpod.py
```

The watch sees the ANT+ stick as a foot pod and receives live speed data.

## Options

`walkingpad_ble.py [address] [-v]`
- `address` — BLE address of the pad (auto-scans if omitted)
- `-v` — debug logging

`antplus-footpod.py [-v] [--mock-speed KMH]`
- `-v` — debug logging
- `--mock-speed` — broadcast a fixed speed (km/h) instead of reading shared memory
