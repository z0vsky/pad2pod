import logging
from openant.easy.node import Node
from openant.easy.channel import Channel

logging.basicConfig(level=logging.INFO)

# ANT+ device type for footpod = 124 (0x7C)
FOOTPOD_DEVICE_TYPE = 124

def on_data(data):
    print("Broadcast data:", data)

def main():
    node = Node()

    # Create a channel in receive mode
    channel = node.new_channel(Channel.Type.BIDIRECTIONAL_RECEIVE)
    channel.set_id(device_type=FOOTPOD_DEVICE_TYPE, device_number=0, transmission_type=0)

    # Attach callback for received data
    channel.on_broadcast_data = on_data

    # Open channel
    channel.open()

    try:
        print("Listening for footpod data... Press Ctrl+C to stop.")
        node.start()   # blocks until stopped
    except KeyboardInterrupt:
        print("Stopping...")
        node.stop()

if __name__ == "__main__":
    main()
