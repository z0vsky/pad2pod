# pad2pod

Reads speed from a WalkingPad C2 over BLE and broadcasts it as an ANT+ foot pod (SDM profile).

## Hardware

- Kingsmith WalkingPad C2
- Dynastream ANTUSB2 stick (ANT+)
- USB Bluetooth dongle

## Setup

```
git clone https://github.com/<you>/pad2pod ~/pad2pod
cd ~/pad2pod
uv sync
```

ANT+ USB stick udev rule (to run without sudo):

```
uv run python -m openant install
```

## Running as a service (systemd)

The service files expect the repo at `~/pad2pod`.

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
