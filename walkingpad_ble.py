"""
Read speed from WalkingPad C2 over BLE and write it to shared memory.
antplus-footpod.py reads from that shared memory and broadcasts ANT+ SDM.

Shared memory layout: 8 bytes, struct 'ff'
  float[0]: speed in m/s
  float[1]: cadence in steps/min (estimated from speed)
"""
import asyncio
import argparse
import logging
import signal
import struct
from multiprocessing import shared_memory

from bleak import BleakClient, BleakScanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

NOTIFY_UUID = "0000fe01-0000-1000-8000-00805f9b34fb"
WRITE_UUID  = "0000fe02-0000-1000-8000-00805f9b34fb"

CMD_STATUS  = bytes([0xF7, 0xA2, 0x00, 0x00, 0xA2, 0xFD])
CMD_PROFILE = bytes([0xF7, 0xA5, 0x60, 0x4A, 0x4D, 0x93, 0x71, 0x29, 0xC9, 0xFD])
CMD_BEEP    = bytes([0xF7, 0xA2, 0x03, 0x07, 0xAC, 0xFD])

# Rough cadence estimate: ~160 steps/min at 4 km/h, scaling linearly
def estimate_cadence(speed_kmh: float) -> float:
    if speed_kmh < 0.1:
        return 0.0
    return max(60.0, speed_kmh * 40.0)


def open_shared_memory() -> tuple[shared_memory.SharedMemory, bool]:
    try:
        shm = shared_memory.SharedMemory(name="speed_cadence", create=False)
        logger.info("Attached to existing shared memory 'speed_cadence'")
        return shm, False
    except FileNotFoundError:
        shm = shared_memory.SharedMemory(name="speed_cadence", create=True, size=8)
        logger.info("Created shared memory 'speed_cadence'")
        return shm, True


def write_speed(shm: shared_memory.SharedMemory, speed_ms: float, cadence: float):
    struct.pack_into("ff", shm.buf, 0, speed_ms, cadence)


async def find_walkingpad(timeout: float = 10.0) -> str:
    logger.info("Scanning for WalkingPad (KS-*)...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.name and (d.name.startswith("KS-") or "walkingpad" in d.name.lower()):
            logger.info(f"Found: {d.name} @ {d.address}")
            return d.address
    raise RuntimeError("WalkingPad not found. Is it powered on and in range?")


async def run(address: str | None = None):
    shm, created = open_shared_memory()
    write_speed(shm, 0.0, 0.0)

    if address is None:
        address = await find_walkingpad()

    logger.info(f"Connecting to {address}...")

    def on_notify(sender, data: bytearray):
        if len(data) < 4 or data[0] != 0xF8 or data[1] != 0xA2:
            return
        belt_state = data[2]
        speed_kmh  = data[3] / 10.0
        speed_ms   = speed_kmh / 3.6
        cadence    = estimate_cadence(speed_kmh)
        write_speed(shm, speed_ms, cadence)
        logger.info(
            f"Belt: {'running' if belt_state == 1 else 'standby'} | "
            f"Speed: {speed_kmh:.1f} km/h ({speed_ms:.3f} m/s) | "
            f"Cadence: {cadence:.0f} spm"
        )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        async with BleakClient(address, timeout=20.0) as client:
            logger.info("Connected. Subscribing to notifications...")
            await client.start_notify(NOTIFY_UUID, on_notify)

            # Connection ceremony required before belt sends notifications
            await asyncio.sleep(1.5)
            await client.write_gatt_char(WRITE_UUID, CMD_PROFILE)
            await asyncio.sleep(1.5)
            await client.write_gatt_char(WRITE_UUID, CMD_BEEP)
            await asyncio.sleep(1.0)

            logger.info("Ready — polling status every 0.75s. Ctrl+C to stop.")
            while not stop_event.is_set():
                await client.write_gatt_char(WRITE_UUID, CMD_STATUS)
                await asyncio.sleep(0.75)
    finally:
        write_speed(shm, 0.0, 0.0)
        shm.close()
        if created:
            shm.unlink()
        logger.info("Stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WalkingPad BLE speed reader")
    parser.add_argument("address", nargs="?", help="BLE address (auto-scan if omitted)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)
    if not args.verbose:
        logging.getLogger("bleak").setLevel(logging.WARNING)

    asyncio.run(run(args.address))
