from sqlalchemy import create_engine, Column, Integer, String, Boolean, Double, ForeignKey, JSON, DateTime, BigInteger
from db_base import Base

from sqlalchemy.orm import relationship
import datetime

import meshtastic

class RXPacket(Base):
    __tablename__ = 'rx_packets'  # Name of the table in the database
    id = Column(Integer, primary_key=True)

    pkt_id = Column(BigInteger) # from meshtastic firmware

    publisher_mesh_node_num = Column(String)
    publisher_discord_bot_user_id = Column(String) # it is a big integer...

    channel = Column(Integer)
    src_num = Column(BigInteger)
    src_id = Column(String)
    src_short_name = Column(String)
    src_long_name = Column(String)
    dst_num = Column(BigInteger)
    dst_id = Column(String)
    dst_short_name = Column(String)
    dst_long_name = Column(String)
    hop_limit = Column(Integer)
    hop_start = Column(Integer)
    pki_encrypted = Column(Boolean)
    portnum = Column(String)
    priority = Column(String)
    rx_time = Column(BigInteger) # epoch
    rx_rssi = Column(Double)
    rx_snr = Column(Double)
    to_all = Column(Boolean)
    want_ack = Column(Boolean)

    # text message
    text = Column(String)
    bitfield = Column(Integer)
    emoji = Column(Integer)
    reply_id = Column(BigInteger)

    # telemetry_data = Column(JSON)
    telemetry_air_quality_metrics = Column(JSON)
    telemetry_device_metrics = Column(JSON)
    telemetry_environment_metrics = Column(JSON)
    telemetry_power_metrics = Column(JSON)

    has_air_quality_metrics = Column(Boolean)
    has_device_metrics = Column(Boolean)
    has_environment_metrics = Column(Boolean)
    has_power_metrics = Column(Boolean)
    has_position_data = Column(Boolean)


    # position
    altitude = Column(Double)
    latitude = Column(Double)
    latitudeI = Column(Integer)
    longitude = Column(Double)
    longitudeI = Column(Integer)
    pos_time = Column(BigInteger) #presumably GPS time?
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

    # traceroute
    traceroute_data = Column(JSON)

    ts = Column(DateTime(timezone=True))

    @property
    def is_text_message(self):
        return self.portnum == 'TEXT_MESSAGE_APP'

    @property
    def src_descriptive(self):
        return f'{self.src_id} | {self.src_short_name} | {self.src_long_name}'

    @property
    def dst_descriptive(self):
        if self.dst_id == meshtastic.BROADCAST_ADDR:
            return 'All Nodes'
        else:
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
        src_num = d.get('from')
        dst_num = d.get('to')
        pkt_id = d.get('id')

        # attempt to get short and long names
        try:
            src_id = '!' + hex(src_num)[2:]
            src_short_name = mesh_client.get_short_name(src_id)
            src_long_name = mesh_client.get_long_name(src_id)
        except:
            src_id = None
            src_short_name = None
            src_long_name = None

        try:
            dst_id = '!' + hex(dst_num)[2:]
            dst_short_name = mesh_client.get_short_name(dst_id)
            dst_long_name = mesh_client.get_long_name(dst_id)
        except:
            dst_id = None
            dst_short_name = None
            dst_long_name = None

        to_all = dst_id == '!ffffffff'

        hop_limit = d.get('hopLimit')
        hop_start = d.get('hopStart')
        pki_encrypted = d.get('pkiEncrypted')
        priority = d.get('priority')


        rx_rssi = d.get('rxRssi')
        rx_snr = d.get('rxSnr')
        rx_time = d.get('rxTime')

        want_ack = d.get('wantAck')
        want_reponse = d.get('wantResponse')

        decoded = d.get('decoded', {})
        portnum = decoded.get('portnum')

        text = None
        bitfield = None
        emoji = None
        reply_id = None

        if portnum == 'TEXT_MESSAGE_APP':
            text = decoded.get('text')
            bitfield = decoded.get('bitfield')
            emoji = decoded.get('emoji')
            reply_id = decoded.get('replyId')


        has_position_data = False

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


        # initalize
        telemetry_air_quality_metrics = {}
        telemetry_device_metrics = {}
        telemetry_environment_metrics = {}
        telemetry_power_metrics = {}

        has_air_quality_metrics = False
        has_device_metrics = False
        has_environment_metrics = False
        has_power_metrics = False

        if portnum == 'TELEMETRY_APP':
            telemetry_data = decoded.get('telemetry', {})

            telemetry_air_quality_metrics = telemetry_data.get('airQualityMetrics', {})
            telemetry_device_metrics = telemetry_data.get('deviceMetrics', {})
            telemetry_environment_metrics = telemetry_data.get('environmentMetrics', {})
            telemetry_power_metrics = telemetry_data.get('powerMetrics', {})

            has_air_quality_metrics = bool(telemetry_air_quality_metrics)
            has_device_metrics = bool(telemetry_device_metrics)
            has_environment_metrics = bool(telemetry_environment_metrics)
            has_power_metrics = bool(telemetry_power_metrics)

        node_id = None
        node_short_name = None
        node_long_name = None
        mac_address = None
        hw_model = None
        public_key = None

        if portnum == 'NODEINFO_APP':
            nodeinfo_data = decoded.get('user', {})

            node_id = nodeinfo_data.get('id')
            node_short_name = nodeinfo_data.get('shortName')
            node_long_name = nodeinfo_data.get('longName')
            mac_address = nodeinfo_data.get('macaddr')
            hw_model = nodeinfo_data.get('hwModel')
            public_key = nodeinfo_data.get('publicKey')

        request_id = None
        error_reason = None

        if portnum == 'ROUTING_APP':
            request_id = decoded.get('requestId')
            error_reason = decoded.get('routing').get('errorReason')

        traceroute_data = {}

        if portnum == 'TRACEROUTE_APP':
            traceroute_data = decoded.get('traceroute', {})
            try:
                del traceroute_data['raw']
            except:
                pass

        out = RXPacket(

            pkt_id = pkt_id,

            publisher_mesh_node_num = publisher_mesh_node_num,
            publisher_discord_bot_user_id = publisher_discord_bot_user_id,
            has_device_metrics = has_device_metrics,
            has_environment_metrics = has_environment_metrics,
            has_air_quality_metrics = has_air_quality_metrics,
            has_power_metrics = has_power_metrics,
            has_position_data = has_position_data,
            channel = channel,
            src_num = src_num,
            src_id = src_id,
            src_short_name = src_short_name,
            src_long_name = src_long_name,
            dst_num = dst_num,
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
            bitfield = bitfield,
            emoji = emoji,
            reply_id = reply_id,
            telemetry_air_quality_metrics = telemetry_air_quality_metrics,
            telemetry_device_metrics = telemetry_device_metrics,
            telemetry_environment_metrics = telemetry_environment_metrics,
            telemetry_power_metrics = telemetry_power_metrics,
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
            error_reason = error_reason,
            traceroute_data = traceroute_data,
            ts=datetime.datetime.now(datetime.timezone.utc)

        )
        return out

class TXPacket(Base):
    __tablename__ = 'tx_packets'  # Name of the table in the database
    id = Column(Integer, primary_key=True)

    publisher_mesh_node_num = Column(String)
    publisher_discord_bot_user_id = Column(String) # it is a big integer...

    packet_id = Column(BigInteger) # maybe int
    channel = Column(Integer) # maybe int
    hop_limit = Column(Integer)
    dest = Column(BigInteger)
    dest_id = Column(String)
    dest_shortname = Column(String)
    dest_longname = Column(String)
    acknowledge_requested = Column(Boolean)
    acknowledge_received = Column(Boolean)

    discord_guild_id = Column(String)
    discord_channel_id = Column(String)
    discord_message_id = Column(String)
    discord_user_id = Column(String)
    discord_user_display_name = Column(String)
    discord_user_global_name = Column(String)
    discord_user_name = Column(String)
    discord_user_mention = Column(String)
    ts = Column(DateTime(timezone=True))

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
            discord_message_id = discord_interaction_info.message_id,
            discord_user_id = discord_interaction_info.user_id,
            discord_user_display_name = discord_interaction_info.user_display_name,
            discord_user_global_name = discord_interaction_info.user_global_name,
            discord_user_name = discord_interaction_info.user_name,
            discord_user_mention = discord_interaction_info.user_mention,
            ts=datetime.datetime.now(datetime.timezone.utc)
        )
        return db_pkt_obj


class ACK(Base):
    __tablename__ = 'acks'  # Name of the table in the database
    id = Column(Integer, primary_key=True)

    publisher_mesh_node_num = Column(String)
    publisher_discord_bot_user_id = Column(String) # it is a big integer...

    tx_packet_id = Column(BigInteger, ForeignKey('tx_packets.id'))
    tx_packet = relationship("TXPacket", back_populates="acks") # Defines the many-to-one relationship with 'User'

    ack_packet_id = Column(BigInteger, ForeignKey('rx_packets.id'))
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

    node_num = Column(BigInteger) # is an int in the node dict
    is_favorite = Column(Boolean)

    # no user info means we don't know the name yet
    user_id_nodedb = Column(String)
    user_long_name_nodedb = Column(String)
    user_short_name_nodedb = Column(String)
    user_mac_addr_nodedb = Column(String)
    user_hw_model_nodedb = Column(String)
    user_public_key_nodedb = Column(String)

    user_id_nodeinfo = Column(String)
    user_long_name_nodeinfo = Column(String)
    user_short_name_nodeinfo = Column(String)
    user_mac_addr_nodeinfo = Column(String)
    user_hw_model_nodeinfo = Column(String)
    user_public_key_nodeinfo = Column(String)

    crt_ts = Column(DateTime(timezone=True))
    upd_ts_nodedb = Column(DateTime(timezone=True))
    upd_ts_nodeinfo = Column(DateTime(timezone=True))

    def __repr__(self):
        return f'<{self.__class__.__name__}. {self.descriptive_name_nodedb_nodedb}>'

    @property
    def descriptive_name(self):
        return f'{self.user_id} | {self.short_name} | {self.long_name}'

    @property
    def descriptive_name_nodedb(self):
        return f'{self.user_id_nodedb} | {self.user_short_name_nodedb} | {self.user_long_name_nodedb}'

    @property
    def descriptive_name_nodeinfo(self):
        return f'{self.user_id_nodeinfo} | {self.user_short_name_nodeinfo} | {self.user_long_name_nodeinfo}'

    # prefer nodeinfo if it exists
    @property
    def user_id(self):
        if self.user_id_nodeinfo:
            return self.user_id_nodeinfo
        else:
            return self.user_id_nodedb

    @property
    def long_name(self):
        if self.user_long_name_nodeinfo:
            return self.user_long_name_nodeinfo
        else:
            return self.user_long_name_nodedb

    @property
    def short_name(self):
        if self.user_short_name_nodeinfo:
            return self.user_short_name_nodeinfo
        else:
            return self.user_short_name_nodedb

    @property
    def mac_addr(self):
        if self.user_mac_addr_nodeinfo:
            return self.user_mac_addr_nodeinfo
        else:
            return self.user_mac_addr_nodedb

    @property
    def hw_model(self):
        if self.user_hw_model_nodeinfo:
            return self.user_hw_model_nodeinfo
        else:
            return self.user_hw_model_nodedb

    @property
    def public_key(self):
        if self.user_public_key_nodeinfo:
            return self.user_public_key_nodeinfo
        else:
            return self.user_public_key_nodedb


    def update_from_nodeinfo(d, mesh_client):
        bot_node_num = mesh_client.my_node_info.node_num_str
        nodenum = d.get('from')
        if nodenum is not None:
            matching_node = mesh_client._db_session.query(MeshNodeDB).filter_by(node_num=nodenum).filter(MeshNodeDB.publisher_mesh_node_num == bot_node_num).first()
            if matching_node:
                decoded = d.get('decoded', {})
                user_dict = decoded.get('user', {})
                if user_dict:

                    user_id = user_dict.get('id')
                    if user_id is not None:
                        matching_node.user_id_nodeinfo = user_id

                    long_name = user_dict.get('longName')
                    if long_name is not None:
                        matching_node.user_long_name_nodeinfo = long_name

                    short_name = user_dict.get('shortName')
                    if short_name is not None:
                        matching_node.user_short_name_nodedb = short_name

                    mac_addr = user_dict.get('macaddr')
                    if mac_addr is not None:
                        matching_node.user_mac_addr_nodeinfo = mac_addr

                    hw_model = user_dict.get('hwModel')
                    if hw_model is not None:
                        matching_node.user_hw_model_nodeinfo = hw_model

                    public_key = user_dict.get('publicKey')
                    if public_key is not None:
                        matching_node.user_public_key_nodeinfo = public_key

                matching_node.upd_ts_nodeinfo = datetime.datetime.now(datetime.timezone.utc)

    def update_from_nodedb(node_num, d, mesh_client):
        bot_node_num = mesh_client.my_node_info.node_num_str
        matching_node = mesh_client._db_session.query(MeshNodeDB).filter_by(node_num=node_num).filter(MeshNodeDB.publisher_mesh_node_num == bot_node_num).first()
        if matching_node:
            is_favorite = d.get('isFavorite')
            if is_favorite is not None:
                matching_node.is_favorite = is_favorite

            user_dict = d.get('user', {})

            # "user" key
            user_id = user_dict.get('id')
            if user_id is not None:
                matching_node.user_id_nodedb = user_id

            user_long_name = user_dict.get('longName')
            if user_long_name is not None:
                matching_node.user_long_name_nodedb = user_long_name

            user_short_name = user_dict.get('shortName')
            if user_short_name is not None:
                matching_node.user_short_name_nodeinfo = user_short_name

            user_mac_addr = user_dict.get('macaddr')
            if user_mac_addr is not None:
                matching_node.user_mac_addr_nodedb = user_mac_addr

            user_hw_model = user_dict.get('hwModel')
            if user_hw_model is not None:
                matching_node.user_hw_model_nodedb = user_hw_model

            user_public_key = user_dict.get('publicKey')
            if user_public_key is not None:
                matching_node.user_public_key_nodedb = user_public_key

            matching_node.upd_ts_nodedb = datetime.datetime.now(datetime.timezone.utc)

    def from_dict(d, mesh_client):

        user_dict = d.get('user', {})

        return MeshNodeDB(
            publisher_mesh_node_num = mesh_client.my_node_info.node_num,
            publisher_discord_bot_user_id = mesh_client.discord_client.user.id,
            node_num = d.get('num'),
            is_favorite = d.get('isFavorite'),

            # "user" key
            user_id_nodedb = user_dict.get('id'),
            user_long_name_nodedb = user_dict.get('longName'),
            user_short_name_nodedb = user_dict.get('shortName'),
            user_mac_addr_nodedb = user_dict.get('macaddr'),
            user_hw_model_nodedb = user_dict.get('hwModel'),
            user_public_key_nodedb = user_dict.get('publicKey'),
            crt_ts = datetime.datetime.now(datetime.timezone.utc),
            upd_ts_nodedb = datetime.datetime.now(datetime.timezone.utc),
            upd_ts_nodeinfo = None,
        )

