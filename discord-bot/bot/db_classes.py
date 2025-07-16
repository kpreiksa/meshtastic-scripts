from sqlalchemy import create_engine, Column, Integer, String, Boolean, Double
from db_base import Base

# 3. Define the DBPacket 
class DBPacket(Base):
    __tablename__ = 'packets'  # Name of the table in the database
    id = Column(Integer, primary_key=True)
    
    publisher_mesh_node_num = Column(String)
    publisher_discord_bot_user_id = Column(String) # it is a big integer...
    
    channel = Column(Integer)
    from_id = Column(String)
    to_id = Column(String)
    from_shortname = Column(String)
    to_shortname = Column(String)
    from_longname = Column(String)
    to_longname = Column(String)
    hop_limit = Column(Integer)
    hop_start = Column(Integer)
    pki_encrypted = Column(Boolean)
    portnum = Column(String)
    priority = Column(String)
    rxTime = Column(Integer) # epoch
    rx_rssi = Column(Double)
    rx_snr = Column(Double)
    to_all = Column(Boolean)
    want_ack = Column(Boolean)
    
    # text message
    text = Column(String)
    
    # telemetry/device metrics
    air_util_tx = Column(Double)
    battery_level = Column(Double)
    channel_utilization = Column(Double)
    uptime_seconds = Column(Double)
    voltage = Column(Double)
    
    # position
    altitude = Column(Double)
    latitude = Column(Double)
    latitudeI = Column(Integer)
    longitude = Column(Double)
    longitudeI = Column(Integer)
    
    # nodeinfo
    node_id = Column(String)
    node_short_name = Column(String)
    node_long_name = Column(String)
    mac_address = Column(String)
    hw_model = Column(String)
    public_key = Column(String)
    
    # routing
    request_id = Column(String) # maybe int?
    error_reason = Column(String)
    
    
class TXPacket(Base):
    __tablename__ = 'tx_packets'  # Name of the table in the database
    id = Column(Integer, primary_key=True)
    
    publisher_mesh_node_num = Column(String)
    publisher_discord_bot_user_id = Column(String) # it is a big integer...
    
    packet_id = Column(Integer) # maybe int
    channel = Column(Integer) # maybe int
    hop_limit = Column(Integer)
    dest = Column(Integer)
    dest_id = Column(String)
    dest_shortname = Column(String)
    dest_longname = Column(String)
    acknowledge_requested = Column(Boolean)
    acknowledge_received = Column(Boolean)
    response_from = Column(Integer)
    response_from_id = Column(String)
    response_from_shortname = Column(String)
    response_from_longname = Column(String)
    response_to = Column(Integer)
    response_to_id = Column(String)
    response_to_shortname = Column(String)
    response_to_longname = Column(String)
    response_packet_id = Column(Integer)
    response_rx_time = Column(Integer)
    response_rx_snr = Column(Double)
    response_rx_rssi = Column(Double)
    response_hop_limit = Column(Integer)
    response_hop_start = Column(Integer)
    response_routing_error_reason = Column(String)
    discord_guild_id = Column(String)
    discord_channel_id = Column(String)
    discord_message_id = Column(String)
    
    def insert(sent_packet, discord_guild_id, discord_channel_id, discord_message_id, mesh_client, ack_requested=True):
        channel = sent_packet.channel
        hop_limit = sent_packet.hop_limit
        packet_id = sent_packet.id
        
        # this should use a node obj?
        dest = sent_packet.to
        # KAP FIX
        dest_id = mesh_client.get_node_id(nodenum=dest)
        dest_shortname = mesh_client.get_short_name(dest_id)
        dest_longname = mesh_client.get_long_name(dest_id)

        db_pkt_obj = TXPacket(
            publisher_mesh_node_num = mesh_client.my_node_info.node_num,
            publisher_discord_bot_user_id = mesh_client.discord_client.user.id,
            packet_id = packet_id,
            channel=channel,
            hop_limit=hop_limit,
            dest=dest,
            acknowledge_requested = ack_requested,
            acknowledge_received = False,
            dest_id = dest_id,
            dest_shortname = dest_shortname,
            dest_longname = dest_longname,
            discord_guild_id = discord_guild_id,
            discord_channel_id = discord_channel_id,
            discord_message_id = discord_message_id
        )
        mesh_client._db_session.add(db_pkt_obj)
        mesh_client._db_session.commit()
    
class MeshNodeDB(Base):
    __tablename__ = 'nodes'
    
    id = Column(Integer, primary_key=True)
    
    publisher_mesh_node_num = Column(String)
    publisher_discord_bot_user_id = Column(String) # it is a big integer...
    
    # all of the following info may or may not be there for each node
    # no user info means we don't know the name yet
    
    node_num = Column(Integer) # is an int in the node dict
    is_favorite = Column(Boolean)
    snr = Column(Double)
    lastHeard = Column(Double)
    hopsAway = Column(Integer)
    
    # "user" key
    user_id = Column(String)
    user_long_name = Column(String)
    user_short_name = Column(String)
    user_mac_addr = Column(String)
    user_hw_model = Column(String)
    user_public_key = Column(String)
    
    # "position" key
    pos_latitude = Column(Double)
    pos_latitudeI = Column(Integer)
    pos_longitude = Column(Double)
    pos_longitudeI = Column(Integer)
    pos_altitude = Column(Integer) #?
    pos_location_source = Column(String)
    
    # "deviceMetrics" key
    device_metrics_battery_level = Column(Integer)
    device_metrics_voltage = Column(Double)
    device_metrics_channel_utilization = Column(Double)
    device_metrics_air_utilization_tx = Column(Double)
    device_metrics_uptime_seconds = Column(Integer)
    
    def from_dict(d, mesh_client):
        return MeshNodeDB(
            publisher_mesh_node_num = mesh_client.my_node_info.node_num,
            publisher_discord_bot_user_id = mesh_client.discord_client.user.id,
            node_num = d.get('num'),
            is_favorite = d.get('is_favorite'),
            snr = d.get('snr'),
            lastHeard = d.get('lastHeard'),
            hopsAway = d.get('hopsAway'),
            
            # "user" key
            user_id = d.get('user', {}).get('id'),
            user_long_name = d.get('user', {}).get('longName'),
            user_short_name = d.get('user', {}).get('shortName'),
            user_mac_addr = d.get('user', {}).get('macaddr'),
            user_hw_model = d.get('user', {}).get('hwModel'),
            user_public_key = d.get('user', {}).get('publicKey'),
            
            # "position" key
            pos_latitude = d.get('position', {}).get('latitude'),
            pos_latitudeI = d.get('position', {}).get('latitudeI'),
            pos_longitude = d.get('position', {}).get('longitude'),
            pos_longitudeI = d.get('position', {}).get('longitudeI'),
            pos_altitude = d.get('position', {}).get('altitude'),
            pos_location_source = d.get('position', {}).get('locationSource'),
            
            # "deviceMetrics" key
            device_metrics_battery_level = d.get('deviceMetrics', {}).get('batteryLevel'),
            device_metrics_voltage = d.get('deviceMetrics', {}).get('voltage'),
            device_metrics_channel_utilization = d.get('deviceMetrics', {}).get('channelUtilization'),
            device_metrics_air_utilization_tx = d.get('deviceMetrics', {}).get('airUtilTx'),
            device_metrics_uptime_seconds = d.get('deviceMetrics', {}).get('uptimeSeconds'),
        )
    

