from sqlalchemy import create_engine, Column, Integer, String, Boolean, Double, ForeignKey
from db_base import Base

from sqlalchemy.orm import relationship

import meshtastic

class RXPacket(Base):
    __tablename__ = 'rx_packets'  # Name of the table in the database
    id = Column(Integer, primary_key=True)
    
    publisher_mesh_node_num = Column(String)
    publisher_discord_bot_user_id = Column(String) # it is a big integer...
    
    channel = Column(Integer)
    src_id = Column(String)
    src_short_name = Column(String)
    src_long_name = Column(String)
    dst_id = Column(String)
    dst_short_name = Column(String)
    dst_long_name = Column(String)
    hop_limit = Column(Integer)
    hop_start = Column(Integer)
    pki_encrypted = Column(Boolean)
    portnum = Column(String)
    priority = Column(String)
    rx_time = Column(Integer) # epoch
    rx_rssi = Column(Double)
    rx_snr = Column(Double)
    to_all = Column(Boolean)
    want_ack = Column(Boolean)
    
    # text message
    text = Column(String)
    
    # telemetry/air quality metrics
    has_air_quality_metrics = Column(Boolean)
    air_quality_co2 = Column(Double)
    air_quality_particles_03um = Column(Double)
    air_quality_particles_05um = Column(Double)
    air_quality_particles_10um = Column(Double)
    air_quality_particles_25um = Column(Double)
    air_quality_particles_50um = Column(Double)
    air_quality_particles_100um = Column(Double)
    air_quality_pm10_environmental = Column(Double)
    air_quality_pm10_standard = Column(Double)
    air_quality_pm25_environmental = Column(Double)
    air_quality_pm25_standard = Column(Double)
    air_quality_pm100_environmental = Column(Double)
    air_quality_pm100_standard = Column(Double)
    
    # telemetry/device metrics
    has_device_metrics = Column(Boolean)
    air_util_tx = Column(Double)
    battery_level = Column(Double)
    channel_utilization = Column(Double)
    uptime_seconds = Column(Double)
    voltage = Column(Double)
    
    # telemetry/environment metrics
    has_environment_metrics = Column(Boolean)
    environment_barometric_pressure = Column(Double)
    environment_current = Column(Double)
    environment_distance = Column(Double)
    environment_gas_resistance = Column(Double)
    environment_iaq = Column(Double)
    environment_ir_lux = Column(Double)
    environment_lux = Column(Double)
    environment_radiation = Column(Double)
    environment_rainfall_1h = Column(Double)
    environment_rainfall_24h = Column(Double)
    environment_relative_humidity = Column(Double)
    environment_soil_moisture = Column(Double)
    environment_soil_temperature = Column(Double)
    environment_temperature = Column(Double)
    environment_uv_lux = Column(Double)
    environment_voltage = Column(Double)
    environment_weight = Column(Double)
    environment_white_lux = Column(Double)
    environment_wind_direction = Column(Double)
    environment_wind_gust = Column(Double)
    environment_wind_lull = Column(Double)
    environment_wind_speed = Column(Double)
    
    # telemetry/power metrics
    has_power_metrics = Column(Boolean)
    power_ch1_current = Column(Double)
    power_ch1_voltage = Column(Double)
    power_ch2_current = Column(Double)
    power_ch2_voltage = Column(Double)
    power_ch3_current = Column(Double)
    power_ch3_voltage = Column(Double)
    
    # position
    has_position_data = Column(Boolean)
    altitude = Column(Double)
    latitude = Column(Double)
    latitudeI = Column(Integer)
    longitude = Column(Double)
    longitudeI = Column(Integer)
    pos_time = Column(Integer) #presumably GPS time?
    location_source = Column(String)
    pdop = Column(Double)
    ground_speed = Column(Double)
    ground_track = Column(Double)
    sats_in_view = Column(Integer)
    precision_bits = Column(Integer)
    
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
    
    @property
    def is_text_message(self):
        return self.portnum == 'TEXT_MESSAGE_APP'
    
    @property
    def src_descriptive(self):
        return f'{self.src_id} | {self.src_short_name} | {self.src_long_name}'
    
    @property
    def dst_descriptive(self):
        return f'{self.dst_id} | {self.dst_short_name} | {self.dst_long_name}'
    
    @property
    def rx_snr_str(self):
        if self.rx_snr:
            return f'{self.rx_snr} dB'
        else:
            return '?'

    @property
    def rx_rssi_str(self):
        if self.rx_rssi:
            return f'{self.rx_rssi} dB'
        else:
            return '?'
    
    def from_dict(d:dict, mesh_client):
        
        # metadata (discord)
        publisher_mesh_node_num = mesh_client.my_node_info.node_num
        publisher_discord_bot_user_id = mesh_client.discord_client.user.id
        
        # COMMON SECTION
        channel = d.get('channel')
        src_id = d.get('fromId')
        src_short_name = mesh_client.get_short_name(src_id)
        src_long_name = mesh_client.get_long_name(src_id)
        
        dst_id = d.get('toId')
        dst_short_name = mesh_client.get_short_name(dst_id)
        dst_long_name = mesh_client.get_long_name(dst_id)
        
        to_all = dst_id == '!ffffffff'
        
        hop_limit = d.get('hopLimit')
        hop_start = d.get('hopStart')
        pki_encrypted = d.get('pkiEncrypted')
        priority = d.get('priority')
        
        portnum = d.get('decoded', {}).get('portnum')
        
        rx_rssi = d.get('rxRssi')
        rx_snr = d.get('rxSnr')
        rx_time = d.get('rxTime')
        
        want_ack = d.get('wantAck')
        want_reponse = d.get('wantResponse')
        
        decoded = d.get('decoded', {})
        
        if portnum == 'TEXT_MESSAGE_APP':
            text = decoded.get('text')
        else:
            text = None
            
        has_position_data = False
            
        if portnum == 'POSITION_APP':
            has_position_data = True
            pos_data = decoded.get('position', {})
            altitude = pos_data.get('altitude')
            latitude = pos_data.get('latitude')
            longitude = pos_data.get('longitude')
            latitudeI = pos_data.get('latitudeI')
            longitudeI = pos_data.get('longitudeI')
            
            pos_time = pos_data.get('time')
            location_source = pos_data.get('locationSource')
            pdop = pos_data.get('PDOP')
            ground_speed = pos_data.get('groundSpeed')
            ground_track = pos_data.get('groundTrack')
            sats_in_view = pos_data.get('satsInView')
            precision_bits = pos_data.get('precisionBits')
        else:
            altitude = None
            latitude = None
            longitude = None
            latitudeI = None
            longitudeI = None
            
            pos_time = None
            location_source = None
            pdop = None
            ground_speed = None
            ground_track = None
            sats_in_view = None
            precision_bits = None
            
        if portnum == 'TELEMETRY_APP':
            telemetry_data = decoded.get('telemetry', {})
            raw_pb = telemetry_data.get('raw')
            
            has_air_quality_metrics = 'airQualityMetrics' in telemetry_data
            has_device_metrics = 'deviceMetrics' in telemetry_data
            has_environment_metrics = 'environmentMetrics' in telemetry_data
            has_power_metrics = 'powerMetrics' in telemetry_data
            
            if isinstance(raw_pb, meshtastic.protobuf.telemetry_pb2.Telemetry):
                
                air_util_tx = raw_pb.device_metrics.air_util_tx
                battery_level = raw_pb.device_metrics.battery_level
                channel_utilization = raw_pb.device_metrics.channel_utilization
                uptime_seconds = raw_pb.device_metrics.uptime_seconds
                voltage = raw_pb.device_metrics.voltage
            
                air_quality_co2 = raw_pb.air_quality_metrics.co2
                air_quality_particles_03um = raw_pb.air_quality_metrics.particles_03um
                air_quality_particles_05um = raw_pb.air_quality_metrics.particles_05um
                air_quality_particles_10um = raw_pb.air_quality_metrics.particles_10um
                air_quality_particles_25um = raw_pb.air_quality_metrics.particles_25um
                air_quality_particles_50um = raw_pb.air_quality_metrics.particles_50um
                air_quality_particles_100um = raw_pb.air_quality_metrics.particles_100um
                air_quality_pm10_environmental = raw_pb.air_quality_metrics.pm10_environmental
                air_quality_pm10_standard = raw_pb.air_quality_metrics.pm10_standard
                air_quality_pm25_environmental = raw_pb.air_quality_metrics.pm25_environmental
                air_quality_pm25_standard = raw_pb.air_quality_metrics.pm25_standard
                air_quality_pm100_environmental = raw_pb.air_quality_metrics.pm100_environmental
                air_quality_pm100_standard = raw_pb.air_quality_metrics.pm100_standard
                
                
                # telemetry/environment metrics
                environment_barometric_pressure = raw_pb.environment_metrics.barometric_pressure
                environment_current = raw_pb.environment_metrics.current
                environment_distance = raw_pb.environment_metrics.distance
                environment_gas_resistance = raw_pb.environment_metrics.gas_resistance
                environment_iaq = raw_pb.environment_metrics.iaq
                environment_ir_lux = raw_pb.environment_metrics.ir_lux
                environment_lux = raw_pb.environment_metrics.lux
                environment_radiation = raw_pb.environment_metrics.radiation
                environment_rainfall_1h = raw_pb.environment_metrics.rainfall_1h
                environment_rainfall_24h = raw_pb.environment_metrics.rainfall_24h
                environment_relative_humidity = raw_pb.environment_metrics.relative_humidity
                environment_soil_moisture = raw_pb.environment_metrics.soil_moisture
                environment_soil_temperature = raw_pb.environment_metrics.soil_temperature
                environment_temperature = raw_pb.environment_metrics.temperature
                environment_uv_lux = raw_pb.environment_metrics.uv_lux
                environment_voltage = raw_pb.environment_metrics.voltage
                environment_weight = raw_pb.environment_metrics.weight
                environment_white_lux = raw_pb.environment_metrics.white_lux
                environment_wind_direction = raw_pb.environment_metrics.wind_direction
                environment_wind_gust = raw_pb.environment_metrics.wind_gust
                environment_wind_lull = raw_pb.environment_metrics.wind_lull
                environment_wind_speed = raw_pb.environment_metrics.wind_speed
                
                power_ch1_current = raw_pb.power_metrics.ch1_current
                power_ch1_voltage = raw_pb.power_metrics.ch1_voltage
                power_ch2_current = raw_pb.power_metrics.ch2_current
                power_ch2_voltage = raw_pb.power_metrics.ch2_voltage
                power_ch3_current = raw_pb.power_metrics.ch3_current
                power_ch3_voltage = raw_pb.power_metrics.ch3_voltage
                
            else:
                
                air_util_tx = None
                battery_level = None
                channel_utilization = None
                uptime_seconds = None
                voltage = None
                
                air_quality_co2 = None
                air_quality_particles_03um = None
                air_quality_particles_05um = None
                air_quality_particles_10um = None
                air_quality_particles_25um = None
                air_quality_particles_50um = None
                air_quality_particles_100um = None
                air_quality_pm10_environmental = None
                air_quality_pm10_standard = None
                air_quality_pm25_environmental = None
                air_quality_pm25_standard = None
                air_quality_pm100_environmental = None
                air_quality_pm100_standard = None
                
                # telemetry/environment metrics
                environment_barometric_pressure = None
                environment_current = None
                environment_distance = None
                environment_gas_resistance = None
                environment_iaq = None
                environment_ir_lux = None
                environment_lux = None
                environment_radiation = None
                environment_rainfall_1h = None
                environment_rainfall_24h = None
                environment_relative_humidity = None
                environment_soil_moisture = None
                environment_soil_temperature = None
                environment_temperature = None
                environment_uv_lux = None
                environment_voltage = None
                environment_weight = None
                environment_white_lux = None
                environment_wind_direction = None
                environment_wind_gust = None
                environment_wind_lull = None
                environment_wind_speed = None
                
                power_ch1_current = None
                power_ch1_voltage = None
                power_ch2_current = None
                power_ch2_voltage = None
                power_ch3_current = None
                power_ch3_voltage = None
        else:
            
            has_air_quality_metrics = False
            has_device_metrics = False
            has_environment_metrics = False
            has_power_metrics = False
            
            air_util_tx = None
            battery_level = None
            channel_utilization = None
            uptime_seconds = None
            voltage = None
            
            air_quality_co2 = None
            air_quality_particles_03um = None
            air_quality_particles_05um = None
            air_quality_particles_10um = None
            air_quality_particles_25um = None
            air_quality_particles_50um = None
            air_quality_particles_100um = None
            air_quality_pm10_environmental = None
            air_quality_pm10_standard = None
            air_quality_pm25_environmental = None
            air_quality_pm25_standard = None
            air_quality_pm100_environmental = None
            air_quality_pm100_standard = None
            
            # telemetry/environment metrics
            environment_barometric_pressure = None
            environment_current = None
            environment_distance = None
            environment_gas_resistance = None
            environment_iaq = None
            environment_ir_lux = None
            environment_lux = None
            environment_radiation = None
            environment_rainfall_1h = None
            environment_rainfall_24h = None
            environment_relative_humidity = None
            environment_soil_moisture = None
            environment_soil_temperature = None
            environment_temperature = None
            environment_uv_lux = None
            environment_voltage = None
            environment_weight = None
            environment_white_lux = None
            environment_wind_direction = None
            environment_wind_gust = None
            environment_wind_lull = None
            environment_wind_speed = None
            
            power_ch1_current = None
            power_ch1_voltage = None
            power_ch2_current = None
            power_ch2_voltage = None
            power_ch3_current = None
            power_ch3_voltage = None
            
        
        if portnum == 'NODEINFO_APP':
            nodeinfo_data = decoded.get('user', {})
            
            node_id = nodeinfo_data.get('id')
            node_short_name = nodeinfo_data.get('shortName')
            node_long_name = nodeinfo_data.get('longName')
            mac_address = nodeinfo_data.get('macaddr')
            hw_model = nodeinfo_data.get('hwModel')
            public_key = nodeinfo_data.get('publicKey')
        else:
            node_id = None
            node_short_name = None
            node_long_name = None
            mac_address = None
            hw_model = None
            public_key = None
            
        if portnum == 'ROUTING_APP':
            request_id = decoded.get('requestId')
            error_reason = decoded.get('routing').get('errorReason')
        else:
            request_id = None
            error_reason = None
        
        out = RXPacket(
            
            publisher_mesh_node_num = publisher_mesh_node_num,
            publisher_discord_bot_user_id = publisher_discord_bot_user_id,
            has_device_metrics = has_device_metrics,
            has_environment_metrics = has_environment_metrics,
            has_air_quality_metrics = has_air_quality_metrics,
            has_power_metrics = has_power_metrics,
            has_position_data = has_position_data,
            channel = channel,
            src_id = src_id,
            src_short_name = src_short_name,
            src_long_name = src_long_name,
            dst_id = dst_id,
            dst_short_name = dst_short_name,
            dst_long_name = dst_long_name,
            hop_limit = hop_limit,
            hop_start = hop_start,
            pki_encrypted = pki_encrypted,
            portnum = portnum,
            priority = priority,
            rx_time = rx_time,
            rx_rssi = rx_rssi,
            rx_snr = rx_snr,
            to_all = to_all,
            want_ack = want_ack,
            text = text,
            air_util_tx = air_util_tx,
            battery_level = battery_level,
            channel_utilization = channel_utilization,
            uptime_seconds = uptime_seconds,
            voltage = voltage,
            air_quality_co2 = air_quality_co2,
            air_quality_particles_03um = air_quality_particles_03um,
            air_quality_particles_05um = air_quality_particles_05um,
            air_quality_particles_10um = air_quality_particles_10um,
            air_quality_particles_25um = air_quality_particles_25um,
            air_quality_particles_50um = air_quality_particles_50um,
            air_quality_particles_100um = air_quality_particles_100um,
            air_quality_pm10_environmental = air_quality_pm10_environmental,
            air_quality_pm10_standard = air_quality_pm10_standard,
            air_quality_pm25_environmental = air_quality_pm25_environmental,
            air_quality_pm25_standard = air_quality_pm25_standard,
            air_quality_pm100_environmental = air_quality_pm100_environmental,
            air_quality_pm100_standard = air_quality_pm100_standard,
            
            # telemetry/environment metrics
            environment_barometric_pressure = environment_barometric_pressure,
            environment_current = environment_current,
            environment_distance = environment_distance,
            environment_gas_resistance = environment_gas_resistance,
            environment_iaq = environment_iaq,
            environment_ir_lux = environment_ir_lux,
            environment_lux = environment_lux,
            environment_radiation = environment_radiation,
            environment_rainfall_1h = environment_rainfall_1h,
            environment_rainfall_24h = environment_rainfall_24h,
            environment_relative_humidity = environment_relative_humidity,
            environment_soil_moisture = environment_soil_moisture,
            environment_soil_temperature = environment_soil_temperature,
            environment_temperature = environment_temperature,
            environment_uv_lux = environment_uv_lux,
            environment_voltage = environment_voltage,
            environment_weight = environment_weight,
            environment_white_lux = environment_white_lux,
            environment_wind_direction = environment_wind_direction,
            environment_wind_gust = environment_wind_gust,
            environment_wind_lull = environment_wind_lull,
            environment_wind_speed = environment_wind_speed,
            
            power_ch1_current = power_ch1_current,
            power_ch1_voltage = power_ch1_voltage,
            power_ch2_current = power_ch2_current,
            power_ch2_voltage = power_ch2_voltage,
            power_ch3_current = power_ch3_current,
            power_ch3_voltage = power_ch3_voltage,
            
            altitude = altitude,
            latitude = latitude,
            latitudeI = latitudeI,
            longitude = longitude,
            longitudeI = longitudeI,
            pos_time = pos_time,
            location_source = location_source,
            pdop = pdop,
            ground_speed = ground_speed,
            ground_track = ground_track,
            sats_in_view = sats_in_view,
            precision_bits = precision_bits,
            
            node_id = node_id,
            node_short_name = node_short_name,
            node_long_name = node_long_name,
            mac_address = mac_address,
            hw_model = hw_model,
            public_key = public_key,
            request_id = request_id,
            error_reason = error_reason
            
        )
        return out
        
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

    discord_guild_id = Column(String)
    discord_channel_id = Column(String)
    discord_message_id = Column(String)
    
    acks = relationship("ACK", back_populates="tx_packet")
    
    def from_sent_packet(sent_packet, discord_interaction_info, mesh_client, ack_requested=True):
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
            discord_guild_id = discord_interaction_info.guild_id,
            discord_channel_id = discord_interaction_info.channel_id,
            discord_message_id = discord_interaction_info.message_id
        )
        return db_pkt_obj
        

class ACK(Base):
    __tablename__ = 'acks'  # Name of the table in the database
    id = Column(Integer, primary_key=True)
    
    publisher_mesh_node_num = Column(String)
    publisher_discord_bot_user_id = Column(String) # it is a big integer...
    
    tx_packet_id = Column(Integer, ForeignKey('tx_packets.id'))
    tx_packet = relationship("TXPacket", back_populates="acks") # Defines the many-to-one relationship with 'User'
    
    ack_packet_id = Column(Integer, ForeignKey('rx_packets.id'))
    ack_packet = relationship("RXPacket") # Defines the many-to-one relationship with 'User'
    
    implicit_ack = Column(Boolean)
    
    def from_rx_packet(pkt, mesh_client):
        
        implicit_ack = pkt.src_id == mesh_client.my_node_info.user_info.user_id
        
        ack_obj = ACK(
            publisher_mesh_node_num = mesh_client.my_node_info.node_num,
            publisher_discord_bot_user_id = mesh_client.discord_client.user.id,
            ack_packet = pkt,
            implicit_ack = implicit_ack  
        )
        return ack_obj
    

# TODO: Refactor this so it can be used for everything node-related - with the possible exception of the local node
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
        


