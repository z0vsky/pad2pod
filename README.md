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

## Running as a service (systemd)

```
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now walkingpad-ble@$USER antplus-footpod@$USER
```

Both services restart automatically on failure. `antplus-footpod` waits for `walkingpad-ble` to be up.

Logs:

```
journalctl -fu walkingpad-ble@$USER
journalctl -fu antplus-footpod@$USER
```

## Manual usage

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
