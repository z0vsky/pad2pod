import argparse
import logging
import time
import struct
from openant.easy.node import Node
from openant.easy.channel import Channel


# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ANT+ constants
NETWORK_KEY = [0xB9, 0xA5, 0x21, 0xFB, 0xBD, 0x72, 0xC3, 0x45]
FOOTPOD_DEVICE_TYPE = 124
DEVICE_NUMBER = 12345
CHANNEL_PERIOD = 8134  # ~4.03 Hz
RF_FREQUENCY = 57

class AntFootpod:
    def __init__(self, mock_speed: float | None = None, mock_cadence: float = 60.0):
        self.mock_speed = mock_speed      # m/s, or None to broadcast zeros when no shm
        self.mock_cadence = mock_cadence
        self.message_count = 0
        self.payload = [0, 0, 0, 0, 0, 0, 0, 0]
        self.last_stride_time = 0
        self.strides_done = 0
        self.distance_accu = 0
        self.speed_last = 0
        self.distance_last = 0
        self.time_rollover = 0
        self.last_time_event = time.time()
        self.program_start = time.time()

    def read_speed_cadence(self):
        ## Mock values for testing (replace with shared memory later)
        from multiprocessing import shared_memory
        try:
            shm = shared_memory.SharedMemory(name='speed_cadence')
            speed, cadence = struct.unpack('ff', shm.buf[:8])
            shm.close()
            return speed, cadence
        except:
            if self.mock_speed is not None:
                return self.mock_speed, self.mock_cadence
            logger.debug("No shared memory, broadcasting zeros")
            return 0.0, 0.0

    def create_next_datapage(self):
        self.message_count += 1
        speed, cadence = self.read_speed_cadence()
        if cadence == 0:
            logger.debug("Belt stopped, broadcasting zeros")
            return [0, 0, 0, 0, 0, 0, 0, 0]

        # Time calculations
        elapsed_seconds = time.time() - self.last_time_event
        self.last_time_event = time.time()
        update_latency = elapsed_seconds / 0.03125  # 1/32s units
        ul_7 = int(update_latency)

        # Stride count
        stride_count_up_value = 60.0 / (cadence / 2.0)
        while self.last_stride_time > stride_count_up_value:
            self.strides_done += 1
            self.last_stride_time -= stride_count_up_value
        self.last_stride_time += elapsed_seconds
        if self.strides_done > 255:
            self.strides_done -= 255

        # Distance
        distance_between = elapsed_seconds * speed
        self.distance_accu += distance_between
        if self.distance_accu > 255:
            self.distance_accu -= 255
        distance_h = int(self.distance_accu)
        distance_l_hex = int((self.distance_accu - distance_h) * 16)

        # Speed
        speed_ms_h = int(speed)
        speed_ms_l_hex = int((speed - speed_ms_h) * 256)

        # Time rollover
        if self.speed_last != speed or self.distance_last != self.distance_accu:
            self.time_rollover += elapsed_seconds
            if self.time_rollover > 255:
                self.time_rollover -= 255
        time_rollover_h = int(self.time_rollover)
        time_rollover_l_hex = int((self.time_rollover - time_rollover_h) * 200)
        if time_rollover_l_hex > 255:
            time_rollover_l_hex -= 255

        self.speed_last = speed
        self.distance_last = self.distance_accu

        # Data pages
        if self.message_count < 3:
            self.payload = [80, 0xFF, 0xFF, 1, 1, 1, 1, 1]  # Page 80: Manufacturer info
        elif 64 < self.message_count < 67:
            self.payload = [81, 0xFF, 0xFF, 1, 0xFF, 0xFF, 0xFF, 0xFF]  # Page 81: Product info
        else:
            self.payload = [
                1,                     # Data page 1
                time_rollover_l_hex,   # Time fractional
                time_rollover_h,       # Time integer
                distance_h,            # Distance integer
                (distance_l_hex * 16 + speed_ms_h),  # Distance fractional + Speed integer
                speed_ms_l_hex,        # Speed fractional
                self.strides_done,     # Stride count
                ul_7                   # Update latency
            ]
        if self.message_count > 131:
            self.message_count = 0
        return self.payload

    def on_broadcast_tx(self, data):
        payload = self.create_next_datapage()
        if len(payload) == 8:
            self.channel.send_broadcast_data(payload)
            logger.debug(f"TX: Data: {payload}")
        else:
            logger.error(f"Invalid payload length: {payload}")

    def open_channel(self):
        for attempt in range(3):
            try:
                logger.debug(f"Attempt {attempt + 1}: Initializing ANT+ node")
                self.node = Node()
                self.node.set_network_key(0x00, NETWORK_KEY)
                logger.debug("Network key set")

                logger.debug("Creating channel")
                self.channel = self.node.new_channel(Channel.Type.BIDIRECTIONAL_TRANSMIT)
                self.channel.set_id(DEVICE_NUMBER, FOOTPOD_DEVICE_TYPE, 5)
                self.channel.set_rf_freq(RF_FREQUENCY)
                self.channel.set_period(CHANNEL_PERIOD)
                logger.debug(f"Channel configured: device_number={DEVICE_NUMBER}, device_type={FOOTPOD_DEVICE_TYPE}")

                self.channel.on_broadcast_tx_data = self.on_broadcast_tx
                logger.debug("Opening channel")
                self.channel.open()
                return True
            except Exception as e:
                logger.error(f"Channel setup failed: {e}. Retrying in 2 seconds...")
                time.sleep(2)
        return False

    def run(self):
        while True:
            try:
                if not self.open_channel():
                    logger.error("Failed to open channel after 3 attempts. Restarting in 5 seconds...")
                    time.sleep(5)
                    continue
                logger.info("Broadcasting footpod data... Press Ctrl+C to stop.")
                self.node.start()
            except KeyboardInterrupt:
                logger.info("Stopping...")
                break
            except Exception as e:
                logger.error(f"Error: {e}. Restarting in 5 seconds...")
                time.sleep(5)
            finally:
                if hasattr(self, 'channel'):
                    try:
                        self.channel.close()
                        logger.debug("Channel closed")
                    except Exception as e:
                        logger.error(f"Error closing channel: {e}")
                if hasattr(self, 'node'):
                    try:
                        self.node.stop()
                        logger.debug("Node stopped")
                    except Exception as e:
                        logger.error(f"Error stopping node: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ANT+ foot pod broadcaster")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--mock-speed", type=float, metavar="KMH",
                        help="Broadcast a fixed mock speed (km/h) when shared memory is unavailable")
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)
    if not args.verbose:
        logging.getLogger("openant").setLevel(logging.WARNING)

    mock_ms = args.mock_speed / 3.6 if args.mock_speed is not None else None
    footpod = AntFootpod(mock_speed=mock_ms)
    footpod.run()
