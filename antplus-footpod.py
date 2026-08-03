import time
import json
import logging
import usb.core
import usb.util
from openant.easy.node import Node
from openant.easy.channel import Channel
from openant.base.commons import format_list

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("footpod")

JSON_FILE = "walkingpad_data.json"  # treadmill output

ANT_NETWORK_KEY = [0xB9, 0xA5, 0x21, 0xFB, 0xBD, 0x72, 0xC3, 0x45]

def read_treadmill_data():
    """Read speed and cadence from JSON file, fallback to 0 if missing."""
    try:
        with open(JSON_FILE, "r") as f:
            data = json.load(f)
        speed = float(data.get("speed", 0.0))
        cadence = int(data.get("cadence", 0))
        return speed, cadence
    except Exception as e:
        logger.error(f"Error reading {JSON_FILE}: {e}")
        return 0.0, 0

def main():
    # Init ANT+ stick
    dev = usb.core.find(idVendor=0x0fcf, idProduct=0x1008)  # typical Garmin stick
    if dev is None:
        logger.error("ANT+ USB stick not found")
        return

    #node = Node(dev)
    node = Node()
    node.set_network_key(0, ANT_NETWORK_KEY)

    channel = node.new_channel(Channel.Type.BIDIRECTIONAL_TRANSMIT)
    channel.set_period(8134)  # ~4 Hz (Stride & Distance standard)
    channel.set_frequency(57)
    channel.set_id(122, 1, 1)  # 122 = Footpod profile

    logger.info("Starting ANT+ footpod emulation")
    channel.open()

    try:
        event_counter = 0
        while True:
            speed, cadence = read_treadmill_data()
            logger.debug(f"Treadmill speed={speed:.2f} m/s, cadence={cadence} spm")

            # Build ANT+ Stride & Distance broadcast (8 bytes)
            # Very simplified: only speed/cadence encoded
            event_counter = (event_counter + 1) % 256
            msg = [
                0x10,               # Page number (example: 0x10 = speed/cadence)
                event_counter,      # Event count
                int(cadence) & 0xFF, 
                int(speed * 256) & 0xFF,        # lower byte of speed (1/256 m/s)
                (int(speed * 256) >> 8) & 0xFF, # upper byte
                0x00, 0x00, 0x00    # filler / stride length / distance etc.
            ]

            channel.send_broadcast_data(msg)
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping footpod emulation")
    finally:
        channel.close()
        node.stop()

if __name__ == "__main__":
    main()
