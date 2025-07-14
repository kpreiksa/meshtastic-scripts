from sqlalchemy import create_engine, Column, Integer, String, Boolean, Double
from db_base import Base

# 3. Define the DBPacket 
class DBPacket(Base):
    __tablename__ = 'packets'  # Name of the table in the database
    id = Column(Integer, primary_key=True)
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
    