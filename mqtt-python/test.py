import paho.mqtt.client as mqtt
from random import uniform
import time
import json

import meshtastic.protobuf.mqtt_pb2
import meshtastic.protobuf.mesh_pb2
import meshtastic.protobuf.telemetry_pb2
import meshtastic.protobuf.portnums_pb2

def on_message(mosq, obj, msg):
    
    if 'json' in msg.topic:
        print("Ignoring JSON message")
        return
    try:
        print(f"Message received on topic: {msg.topic}")
        pkt = meshtastic.protobuf.mqtt_pb2.ServiceEnvelope()
        pkt.ParseFromString(msg.payload)
        print(f"Received message with portnum: {pkt.packet.decoded.portnum}")
        pkt_from = getattr(pkt.packet, 'from')
        pkt_to = pkt.packet.to
        pkt_id = pkt.packet.id
        pkt_rx_snr = pkt.packet.rx_snr
        pkt_rx_rssi = pkt.packet.rx_rssi
        pkt_hop_limit = pkt.packet.hop_limit
        pkt_hop_start = pkt.packet.hop_start
        pkt_relay_node = pkt.packet.relay_node
        
        if pkt.packet.decoded.portnum == meshtastic.protobuf.portnums_pb2.NODEINFO_APP:
            print("Received a NodeInfo packet")
            ui = meshtastic.protobuf.mesh_pb2.User()
            ui.ParseFromString(pkt.packet.decoded.payload)
            u_id = ui.id
            u_long_name = ui.long_name
            u_short_name = ui.short_name
            u_macaddr = ui.macaddr
            u_hw_model = ui.hw_model
            u_role = ui.role
            u_public_key = ui.public_key
            u_is_unmessagable = ui.is_unmessagable
            print("Got NodeInfo:")
        elif pkt.packet.decoded.portnum == meshtastic.protobuf.portnums_pb2.POSITION_APP:
            print("Received a Position packet")
            pos = meshtastic.protobuf.mesh_pb2.Position()
            pos.ParseFromString(pkt.packet.decoded.payload)
            p_lat = pos.latitude_i / 1e7
            p_long = pos.longitude_i / 1e7
            p_alt = pos.altitude
            p_location_source = pos.location_source
            p_precision_bits = pos.precision_bits
            p_ground_speed = pos.ground_speed
            p_sats_in_view = pos.sats_in_view
            p_time = pos.time
            print("Got Position:")
            
        elif pkt.packet.decoded.portnum == meshtastic.protobuf.portnums_pb2.TEXT_MESSAGE_APP:
            print("Received a Text packet")
            text = pkt.packet.decoded.payload.decode('utf-8')
            print("Got Text:")
            
        elif pkt.packet.decoded.portnum == meshtastic.protobuf.portnums_pb2.TELEMETRY_APP:
            print("Received a Battery packet")
            telem = meshtastic.protobuf.telemetry_pb2.Telemetry()
            telem.ParseFromString(pkt.packet.decoded.payload)
            telem_dm_air_util_tx = telem.device_metrics.air_util_tx
            telem_dm_battery_level = telem.device_metrics.battery_level
            telem_dm_channel_utilization = telem.device_metrics.channel_utilization
            telem_dm_uptime_seconds = telem.device_metrics.uptime_seconds
            telem_dm_voltage = telem.device_metrics.voltage
            
            telem_em_barometric_pressure = telem.environment_metrics.barometric_pressure
            telem_em_temperature = telem.environment_metrics.temperature
            telem_em_humidity = telem.environment_metrics.relative_humidity
            print("Got Telemetry:")
            
        elif pkt.packet.decoded.portnum == meshtastic.protobuf.portnums_pb2.TRACEROUTE_APP:
            traceroute = meshtastic.protobuf.mesh_pb2.RouteDiscovery()
            traceroute.ParseFromString(pkt.packet.decoded.payload)
            route = traceroute.route
            route_back = traceroute.route_back
            
            snr_towards = traceroute.snr_towards
            snr_back = traceroute.snr_back
            print("Got Traceroute:")
            
        elif pkt.packet.decoded.portnum == meshtastic.protobuf.portnums_pb2.ROUTING_APP:
            routing = meshtastic.protobuf.mesh_pb2.Routing()
            routing.ParseFromString(pkt.packet.decoded.payload)
            r_error_reason = routing.error_reason
            r_request = routing.route_request
            r_request_route = r_request.route
            r_request_route_back = r_request.route_back
            r_request_snr_towards = r_request.snr_towards
            r_request_snr_back = r_request.snr_back
            r_reply = routing.route_reply
            r_reply_route = r_reply.route
            r_reply_route_back = r_reply.route_back
            r_reply_snr_towards = r_reply.snr_towards
            r_reply_snr_back = r_reply.snr_back
            print("Got Routing:")
            
              
        else:
            print("Received a different type of packet")
        
            

            
    except Exception as e:
        print(f"Error processing message: {e}")

def on_publish(mosq, obj, mid, reason_codes, properties):
    pass

def send_dm(client, sender, to_id, message_text):
    
    json_message = {
        "from": sender,
        "to": to_id,
        "type": "sendtext",
        "payload": message_text
    }
    
    (rc, mid) = client.publish("msh/US/2/json/mqtt/", json.dumps(json_message), qos=0)
    if rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"Failed to publish message: {mqtt.error_string(rc)}")
    else:
        print(f"Published message with mid: {mid}")
        
def send_chan(client, sender, message_text, chan_idx = 0):
    
    json_message = {
        "from": sender,
        "type": "sendtext",
        "channel": chan_idx,
        "payload": message_text
    }
    
    (rc, mid) = client.publish("msh/US/2/json/mqtt/", json.dumps(json_message), qos=0)
    if rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"Failed to publish message: {mqtt.error_string(rc)}")
    else:
        print(f"Published message with mid: {mid}")

if __name__ == '__main__':
    
    print("MQTT Test Client Starting")
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect('192.168.101.210')
    print(f"Connected to MQTT broker at 192.168.101.210")

    client.on_message = on_message
    client.on_publish = on_publish
    
    print("Subscribing to topic 'msh/#'")
    client.subscribe("msh/#", 0)
    print("Subscribed to topic 'msh/#'")
    
    time.sleep(10)
    
    send_chan(client, 4145999732, "Hello from MQTT test client!")
    

    while client.loop() == 0:
        pass