from db_classes import DBPacket

class DeviceMetrics():
    def __init__(self, d):
        self._d = d

    def __repr__(self):
        return f'<Class {self.__class__.__name__}>.'

    def packet_summary_json(self):
        out = {
            'Battery Level': self.battery_level,
            'Voltage': self.voltage,
            'Channel Utilization': self.channel_utilization,
            'Air Utilization': self.air_util_tx,
            'Uptime Seconds': self.uptime_seconds,
        }
        return out

    @property
    def battery_level(self):
        return self._d.get('batteryLevel')

    @property
    def voltage(self):
        return self._d.get('voltage')

    @property
    def channel_utilization(self):
        return self._d.get('channelUtilization')

    @property
    def air_util_tx(self):
        return self._d.get('airUtilTx')

    @property
    def uptime_seconds(self):
        return self._d.get('uptimeSeconds')

class TelemetryPacket():
    def __init__(self, d):
        self._d = d

    def __repr__(self):
        return f'<Class {self.__class__.__name__}>.'

    def packet_summary_json(self):
        out = {
            'Time': self.time,
            'Device Metrics': self.device_metrics.packet_summary_json()
        }
        return out

    @property
    def time(self):
        return self._d.get('time')

    @property
    def device_metrics(self):
        return DeviceMetrics(self._d.get('deviceMetrics', {}))

class PositionPacket():
    def __init__(self, d):
        self._d = d

    def __repr__(self):
        return f'<Class {self.__class__.__name__}>.'

    def packet_summary_json(self):
        out = {
            'Time': self.time,
            'Latitude I': self.latitudeI,
            'Longitude I': self.longitudeI,
            'Latitude': self.latitude,
            'Longitude': self.longitude,
            'Altitude': self.altitude,
        }
        return out

    @property
    def time(self):
        return self._d.get('time')

    @property
    def latitudeI(self):
        return self._d.get('latitudeI')

    @property
    def longitudeI(self):
        return self._d.get('longitudeI')

    @property
    def altitude(self):
        return self._d.get('altitude')

    @property
    def latitude(self):
        return self._d.get('latitude')

    @property
    def longitude(self):
        return self._d.get('longitude')

class TraceroutePacket():
    def __init__(self, d):
        self._d = d

    def __repr__(self):
        return f'<Class {self.__class__.__name__}>.'

    def packet_summary_json(self):
        out = {
            'SNR Towards': self.snr_towards,
        }
        return out

    @property
    def snr_towards(self):
        return self._d.get('snrTowards', [])


class RoutingPacket():
    def __init__(self, d):
        self._d = d

    def __repr__(self):
        return f'<Class {self.__class__.__name__}>.'

    def packet_summary_json(self):
        out = {
            'Error Reason': self.error_reason,
        }
        return out

    @property
    def error_reason(self):
        return self._d.get('errorReason')



class NodeInfoPacket():
    def __init__(self, d):
        self._d = d

    def __repr__(self):
        return f'<Class {self.__class__.__name__}>.'

    def packet_summary_json(self):
        out = {
            'Node ID': self.node_id,
            'Node Long Name': self.node_long_name,
            'Node Short Name': self.node_short_name,
            'MAC Address': self.mac_addr,
            'HW Model': self.hw_model,
            'Public Key': self.public_key,
        }
        return out

    @property
    def node_id(self):
        return self._d.get('id')

    @property
    def node_long_name(self):
        return self._d.get('longName')

    @property
    def node_short_name(self):
        return self._d.get('shortName')

    @property
    def mac_addr(self):
        return self._d.get('macaddr')

    @property
    def hw_model(self):
        return self._d.get('hwModel')

    @property
    def public_key(self):
        return self._d.get('publicKey')

class DecodedPacket():
    def __init__(self, d):
        self._d = d

    def __repr__(self):
        return f'<Class {self.__class__.__name__}>. PortNum= {self.portnum}'

    def packet_summary_json(self):
        out = {
            'PortNum': self.portnum,
            'Channel': self.channel,
            'WantResponse': self.want_response,
            'Telemetry': self.telemetry.packet_summary_json() if self.telemetry else None,
            'Position': self.position.packet_summary_json() if self.position else None,
            'Text': self.text if self.text else None,
            'Traceroute': self.traceroute.packet_summary_json() if self.traceroute else None,
            'User': self.user.packet_summary_json() if self.user else None,
            'Keys': list(self._d.keys())
        }
        return out

    @property
    def portnum(self):
        return self._d.get('portnum')

    @property
    def channel(self):
        return self._d.get('channel')

    @property
    def want_response(self):
        return self._d.get('want_response')

    @property
    def request_id(self):
        return self._d.get('requestId')

    @property
    def telemetry(self):
        if self.portnum == 'TELEMETRY_APP':
            return TelemetryPacket(self._d.get('telemetry', {}))
        else: return None

    @property
    def position(self):
        if self.portnum == 'POSITION_APP':
            return PositionPacket(self._d.get('position', {}))
        else: return None

    @property
    def user(self):
        if self.portnum == 'NODEINFO_APP':
            return NodeInfoPacket(self._d.get('user', {}))
        else: return None

    @property
    def traceroute(self):
        if self.portnum == 'TRACEROUTE':
            return TraceroutePacket(self._d.get('traceroute', {}))
        else: return None

    @property
    def text(self):
        if self.portnum == 'TEXT_MESSAGE_APP':
            return self._d.get('text')
        else:
            return None

    @property
    def routing(self):
        if self.portnum == 'ROUTING_APP':
            return RoutingPacket(self._d.get('routing', {}))
        else: return None

class MeshPacket():
    def __init__(self, d, mesh_client):
        self._d = d
        self._mesh_client = mesh_client

    def __repr__(self):
        return f'<Class {self.__class__.__name__}>. PortNum: {self.portnum} From: {self.from_descriptive} To: {self.to_descriptive}'

    def packet_summary_json(self):
        out = {
            'Channel': self.channel,
            'From': f'{self.from_num} | {self.from_descriptive}',
            'To': f'{self.to_num} | {self.to_descriptive}',
            'Priority': self.priority,
            'Decoded': self.decoded.packet_summary_json()
        }
        return out

    def to_db(self):
        if self.portnum == 'TEXT_MESSAGE_APP':
            new_packet = DBPacket(
                channel = self.channel,
                from_id = self.from_id,
                from_shortname = self.from_shortname,
                from_longname = self.from_longname,
                to_id = self.to_id,
                to_shortname = self.to_shortname,
                to_longname = self.to_longname,
                hop_limit = self.hop_limit,
                hop_start = self.hop_start,
                pki_encrypted = self.pki_encrypted,
                portnum = self.portnum,
                priority = self.priority,
                rxTime = self.rxTime,
                rx_rssi = self.rx_rssi,
                rx_snr = self.rx_snr,
                to_all = self.to_all,
                want_ack = self.want_ack,
                text = self.decoded.text
            )
            self._mesh_client._db_session.add(new_packet)
            self._mesh_client._db_session.commit()
        elif self.portnum == 'POSITION_APP':
            new_packet = DBPacket(
                channel = self.channel,
                from_id = self.from_id,
                from_shortname = self.from_shortname,
                from_longname = self.from_longname,
                to_id = self.to_id,
                to_shortname = self.to_shortname,
                to_longname = self.to_longname,
                hop_limit = self.hop_limit,
                hop_start = self.hop_start,
                pki_encrypted = self.pki_encrypted,
                portnum = self.portnum,
                priority = self.priority,
                rxTime = self.rxTime,
                rx_rssi = self.rx_rssi,
                rx_snr = self.rx_snr,
                to_all = self.to_all,
                want_ack = self.want_ack,
                altitude = self.decoded.position.altitude,
                latitude = self.decoded.position.latitude,
                longitude = self.decoded.position.longitude,
                latitudeI = self.decoded.position.latitudeI,
                longitudeI = self.decoded.position.longitudeI,
            )
            self._mesh_client._db_session.add(new_packet)
            self._mesh_client._db_session.commit()

        elif self.portnum == 'TELEMETRY_APP':
            new_packet = DBPacket(
                channel = self.channel,
                from_id = self.from_id,
                from_shortname = self.from_shortname,
                from_longname = self.from_longname,
                to_id = self.to_id,
                to_shortname = self.to_shortname,
                to_longname = self.to_longname,
                hop_limit = self.hop_limit,
                hop_start = self.hop_start,
                pki_encrypted = self.pki_encrypted,
                portnum = self.portnum,
                priority = self.priority,
                rxTime = self.rxTime,
                rx_rssi = self.rx_rssi,
                rx_snr = self.rx_snr,
                to_all = self.to_all,
                want_ack = self.want_ack,
                air_util_tx = self.decoded.telemetry.device_metrics.air_util_tx,
                battery_level = self.decoded.telemetry.device_metrics.battery_level,
                channel_utilization = self.decoded.telemetry.device_metrics.channel_utilization,
                uptime_seconds = self.decoded.telemetry.device_metrics.uptime_seconds,
                voltage = self.decoded.telemetry.device_metrics.voltage,
            )
            self._mesh_client._db_session.add(new_packet)
            self._mesh_client._db_session.commit()

        elif self.portnum == 'NODEINFO_APP':
            new_packet = DBPacket(
                channel = self.channel,
                from_id = self.from_id,
                from_shortname = self.from_shortname,
                from_longname = self.from_longname,
                to_id = self.to_id,
                to_shortname = self.to_shortname,
                to_longname = self.to_longname,
                hop_limit = self.hop_limit,
                hop_start = self.hop_start,
                pki_encrypted = self.pki_encrypted,
                portnum = self.portnum,
                priority = self.priority,
                rxTime = self.rxTime,
                rx_rssi = self.rx_rssi,
                rx_snr = self.rx_snr,
                to_all = self.to_all,
                want_ack = self.want_ack,
                node_id = self.decoded.user.node_id,
                node_short_name = self.decoded.user.node_short_name,
                node_long_name = self.decoded.user.node_long_name,
                mac_address = self.decoded.user.mac_addr,
                hw_model = self.decoded.user.hw_model,
                public_key = self.decoded.user.public_key
            )
            self._mesh_client._db_session.add(new_packet)
            self._mesh_client._db_session.commit()

        elif self.portnum == 'ROUTING_APP':
            new_packet = DBPacket(
                channel = self.channel,
                from_id = self.from_id,
                from_shortname = self.from_shortname,
                from_longname = self.from_longname,
                to_id = self.to_id,
                to_shortname = self.to_shortname,
                to_longname = self.to_longname,
                hop_limit = self.hop_limit,
                hop_start = self.hop_start,
                pki_encrypted = self.pki_encrypted,
                portnum = self.portnum,
                priority = self.priority,
                rxTime = self.rxTime,
                rx_rssi = self.rx_rssi,
                rx_snr = self.rx_snr,
                to_all = self.to_all,
                request_id = self.decoded.request_id,
                error_reason = self.decoded.routing.error_reason
            )
            self._mesh_client._db_session.add(new_packet)
            self._mesh_client._db_session.commit()

        else:
            new_packet = DBPacket(
                channel = self.channel,
                from_id = self.from_id,
                from_shortname = self.from_shortname,
                from_longname = self.from_longname,
                to_id = self.to_id,
                to_shortname = self.to_shortname,
                to_longname = self.to_longname,
                hop_limit = self.hop_limit,
                hop_start = self.hop_start,
                pki_encrypted = self.pki_encrypted,
                portnum = self.portnum,
                priority = self.priority,
                rxTime = self.rxTime,
                rx_rssi = self.rx_rssi,
                rx_snr = self.rx_snr,
                to_all = self.to_all,
                want_ack = self.want_ack
            )
            self._mesh_client._db_session.add(new_packet)
            self._mesh_client._db_session.commit()

    @property
    def from_num(self):
        return self._d.get('from')

    @property
    def to_num(self):
        return self._d.get('to')

    @property
    def packet_id(self):
        return self._d.get('id')

    @property
    def rxTime(self):
        return self._d.get('rxTime')

    @property
    def hopLimit(self):
        return self._d.get('hopLimit')

    @property
    def priority(self):
        return self._d.get('priority')

    @property
    def from_id(self):
        return self._d.get('fromId')

    @property
    def to_id(self):
        if self._d.get('toId') == '^all': # Consider using 'to' and converting from dec to hex instead of toID since toID gets replaced by ^all (by mesh library when broadcast)
            return '!ffffffff'
        else:
            return self._d.get('toId')

    @property
    def rx_snr(self):
        return self._d.get('rxSnr')

    @property
    def rx_rssi(self):
        return self._d.get('rxRssi')

    @property
    def hop_limit(self):
        return self._d.get('hopLimit')

    @property
    def hop_start(self):
        return self._d.get('hopStart')

    @property
    def decoded(self):
        return DecodedPacket(self._d.get('decoded', {}))

    @property
    def want_ack(self):
        return self._d.get('wantAck')

    @property
    def public_key(self):
        return self._d.get('publicKey')

    @property
    def pki_encrypted(self):
        return self._d.get('pkiEncrypted')

    @property
    def from_descriptive(self):
        return f'{self.from_id} | {self.from_shortname} | {self.from_shortname}'

    @property
    def to_descriptive(self):
        return f'{self.to_id} | {self.to_shortname} | {self.to_longname}'

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

    @property
    def channel(self):
        return self._d.get('channel')

    @property
    def channel_str(self):
        out = 0
        top_channel = self._d.get('channel')
        if top_channel is not None:
            out = top_channel
        else:
            decoded_channel = self.decoded.channel
            if decoded_channel is not None:
                out = decoded_channel
        return out

    @property
    def portnum(self):
        return self.decoded.portnum

    @property
    def is_text_message(self):
        return self.portnum == 'TEXT_MESSAGE_APP'

    @property
    def to_all(self):
        return self.to_id == '!ffffffff'

    @property
    def from_shortname(self):
        return self._mesh_client.get_short_name(self.from_id)

    @property
    def to_shortname(self):
        if self.to_all:
            return '^all'
        else:
            return self._mesh_client.get_short_name(self.to_id)

    @property
    def from_longname(self):
        return self._mesh_client.get_long_name(self.from_id, '?')

    @property
    def to_longname(self):
        if self.to_all:
            return "Broadcast"
        else:
            return self._mesh_client.get_long_name(self.to_id, '?')