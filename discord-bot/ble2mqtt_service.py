import meshtastic
import meshtastic.ble_interface
import paho.mqtt.client as mqtt
import json
from pubsub import pub  # Import the pubsub library

# MQTT broker settings
MQTT_SERVER = "192.168.1.1" #address of mqtt server
MQTT_PORT = 1883

# Define the static topic parts
MQTT_ROOT = "msh/US/2"
CHANNEL_NAME = "LongFast"
ble_address = "mesh_1234"
ble_node_id = '!12345678'

def on_meshtastic_receive(packet, interface):
    global ble_node_id
    global CHANNEL_NAME
    if not ble_node_id:
        print("Waiting for BLE connection to be fully established and Node ID to be retrieved...", flush=True)
        return

    print(f"Received Meshtastic packet: {packet}", flush=True)

    try:
        encrypted_topic = f"{MQTT_ROOT}/e/{CHANNEL_NAME}/{ble_node_id}"
        encrypted_payload = str(packet)
        client.publish(encrypted_topic, encrypted_payload)
        print(f"Published to {encrypted_topic}:\n{encrypted_payload}", flush=True)

        decoded_topic = f"{MQTT_ROOT}/json/{CHANNEL_NAME}/{ble_node_id}"
        
        
        try:
            decoded_payload = json.dumps(packet, indent=2, default=str)
        except Exception:
            decoded_payload = str(packet)
        
        client.publish(decoded_topic, decoded_payload)
        print(f"Published to {decoded_topic}:\n{decoded_payload}", flush=True)

    except Exception as e:
        print(f"Error publishing packet to MQTT: {e}", flush=True)


def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker")
    else:
        print(f"Failed to connect, return code {rc}")

# Initialize MQTT client
client = mqtt.Client()
client.on_connect = on_mqtt_connect
client.connect(MQTT_SERVER, MQTT_PORT, 60)
client.loop_start()
# 2. Subscribe to ALL received Meshtastic packets
pub.subscribe(on_meshtastic_receive, "meshtastic.receive")

try:
    # Create a Bluetooth interface to the RAK device
    interface = meshtastic.ble_interface.BLEInterface(address=ble_address)
 
    # interface.on_data_received = on_meshtastic_message
    # print("Listening for Meshtastic packets over Bluetooth...",flush=True)
    print("Listening for ALL Meshtastic packets via pub/sub over Bluetooth...", flush=True)


    while True:
        # The interface handles the message loop internally
        pass

except Exception as e:
    print(f"Error: {e}")
    interface.close()
    client.loop_stop()

