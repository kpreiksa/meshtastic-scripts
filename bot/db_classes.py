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