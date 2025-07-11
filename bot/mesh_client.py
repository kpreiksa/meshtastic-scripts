import discord # needed for embeds
from pprint import pprint
import logging
import queue
import sys
import time

from datetime import datetime

import meshtastic
import meshtastic.ble_interface
import meshtastic.serial_interface
import meshtastic.tcp_interface
import pytz
from pubsub import pub

from mesh_packets import MeshPacket
from mesh_node_classes import MeshNode
from config_classes import Config
from util import get_current_time_str

from db_classes import TXPacket

# move all of this to config
battery_warning = 15 # move to config
green_color = 0x67ea94  # Meshtastic Green
red_color = 0xed4245  # Red
    
class MeshClient():
    
    def onReceiveMesh(self, packet, interface):  # Called when a packet arrives from mesh.
        
        try:
            packetObj = MeshPacket(packet, self)
            packetObj.to_db()
            # pprint(packetObj.packet_summary_json())
            if packetObj.is_text_message:
                # new_user1 = User(name='Alice', email='alice@example.com')
                # new_user2 = User(name='Bob', email='bob@example.com')

                # session.add(new_user1)
                # session.add(new_user2)
                # session.commit()  # Commit changes to save to the database
                logging.info("Text message packet received") # For debugging.
                # logging.info(f"Packet: {packet}") # Print the entire packet for debugging.
                
                mesh_channel_index = packetObj.channel
                mesh_channel_name = self.config.channel_names.get(mesh_channel_index, f"Unknown Channel ({mesh_channel_index})")

                current_time = get_current_time_str()
                
                hop_start = packetObj.hop_start

                if packetObj.hop_limit and packetObj.hop_start:
                    hops = int(packetObj.hop_limit) - int(packetObj.hop_limit)
                else:
                    hops = "?"
                    if not packetObj.hop_limit:
                        hop_start = "?"
                
                logging.info(f'From: {packetObj.from_descriptive}')

                embed = discord.Embed(title="Message Received", description=packetObj.decoded.text, color=green_color)
                embed.add_field(name="From Node", value=packetObj.from_descriptive, inline=False)
                embed.add_field(name="RxSNR / RxRSSI", value=f"{packetObj.rx_snr_str} / {packetObj.rx_rssi_str}", inline=True)
                embed.add_field(name="Hops", value=f"{hops} / {hop_start}", inline=True)
                embed.set_footer(text=f"{current_time}")

                if packetObj.to_all:
                    embed.add_field(name="To Channel", value=mesh_channel_name, inline=True)
                else:
                    embed.add_field(name="To Node", value=packetObj.to_descriptive, inline=True)

                logging.info(f'Putting Mesh Received message on Discord queue')
                if self.discord_client:
                    self.discord_client.enqueue_msg(embed)
            else:
                logging.info(f'Received unhandled packet type: {packetObj.portnum}')

        except Exception as e:
            logging.error(f'Error parsing packet: {str(e)}')
    
    def onConnectionMesh(self, interface, topic=None):
        # interface, obj
        
        
        node_info = interface.getMyNodeInfo()
        node_obj = MeshNode(node_info)
        
        logging.info('***CONNECTED***')
        logging.info('***************')
        logging.info(f'Node Num:   {node_obj.node_num}')
        logging.info(f'Node ID:    {node_obj.user_info.user_id}')
        logging.info(f'Short Name: {node_obj.user_info.short_name}')
        logging.info(f'Long Name:  {node_obj.user_info.long_name}')
        logging.info(f'MAC Addr:   {node_obj.user_info.mac_address}')
        logging.info(f'HW Model:   {node_obj.user_info.hw_model}')
        logging.info('***************')
        
    def onNodeUpdated(self, node, interface):
        # this happens when a node gets updated... we should update the database
        logging.info(str(type(node)))
        logging.info(str(dir(node)))
        
    def onMsgResponse(self, d):
        # if there is a request Id... look it up in the Db and acknowledge
        response_from = d.get('from')
        response_to = d.get('to')
        response_from_id = d.get('fromId')
        response_to_id = d.get('toId')
        response_id = d.get('id')
        response_rx_time = d.get('rxTime')
        response_rx_snr = d.get('rxSnr')
        response_rx_rssi = d.get('rxRssi')
        response_hop_limit = d.get('hopLimit')
        response_hop_start = d.get('hopStart')
        request_id = d.get('decoded', {}).get('requestId')
        routing_error_reason = d.get('decoded', {}).get('routing', {}).get('errorReason')
        response_from_shortname = self.get_short_name(response_from_id)    
        response_from_longname =  self.get_long_name(response_from_id)  
        response_to_shortname = self.get_short_name(response_to_id)    
        response_to_longname =  self.get_long_name(response_to_id)  
        
        logging.info(f'Got Response to packet: {request_id} from {response_from_id}')
        db_updated = False
        matching_packet = self._db_session.query(TXPacket).filter_by(packet_id=request_id).first()
        if matching_packet: # if it exists
            if matching_packet.acknowledge_received == True:
                logging.info(f'Packet already acknowledged')
            else:
                matching_packet.acknowledge_received = True
                matching_packet.response_from = response_from
                matching_packet.response_from_id = response_from_id
                matching_packet.response_from_shortname = response_from_shortname
                matching_packet.response_from_longname = response_from_longname
                matching_packet.response_to = response_to
                matching_packet.response_to_id = response_to_id
                matching_packet.response_to_shortname = response_to_shortname
                matching_packet.response_to_longname = response_to_longname
                matching_packet.response_packet_id = response_id
                matching_packet.response_rx_time = response_rx_time
                matching_packet.response_rx_snr = response_rx_snr
                matching_packet.response_rx_rssi = response_rx_rssi
                matching_packet.response_hop_limit = response_hop_limit
                matching_packet.response_hop_start = response_hop_start
                matching_packet.response_routing_error_reason = routing_error_reason
                self._db_session.commit() # save back to db
                db_updated = True
                self.discord_client.enqueue_msg(f'https://discord.com/channels/{matching_packet.discord_guild_id}/{matching_packet.discord_channel_id}/{matching_packet.discord_message_id} Msg to {matching_packet.dest_id} | {matching_packet.dest_shortname} | {matching_packet.dest_longname} - Acknowledged. Snr: {response_rx_snr}. Rssi: {response_rx_rssi}. DB Updated = {db_updated}')
                self.discord_client.enqueue_mesh_response(
                    {
                        'discord_guild_id': matching_packet.discord_guild_id,
                        'discord_channel_id': matching_packet.discord_channel_id,
                        'discord_message_id': matching_packet.discord_message_id,
                        'response_from': response_from,
                        'response_from_id': response_from_id,
                        'response_from_shortname': response_from_shortname,
                        'response_from_longname': response_from_longname,
                        'response_rx_time': response_rx_time,
                        'response_to': response_to,
                        'response_to_id': response_to_id,
                        'response_to_shortname': response_to_shortname,
                        'response_to_longname': response_to_longname,
                        'response_rx_snr': response_rx_snr,
                        'response_rx_rssi': response_rx_rssi,
                        'response_hop_limit': response_hop_limit,
                        'response_hop_start': response_hop_start,
                    }
                )
        else:
            self.discord_client.enqueue_msg(f'Msg to {response_from_id} |   - Acknowledged. Snr: {response_rx_snr}. Rssi: {response_rx_rssi}. DB Updated = {db_updated}')
        
            
    def __init__(self, db_session):
        self._meshqueue = queue.Queue(maxsize=20)
        self._adminqueue = queue.Queue(maxsize=20)
        
        self._db_session = db_session
        
        self.config = Config()
        
        self.iface = None
        
        self.nodes = {}
        self.myNodeInfo = None
        
        self.connect()
        
        self.discord_client = None        
        
        pub.subscribe(self.onReceiveMesh, "meshtastic.receive")
        pub.subscribe(self.onConnectionMesh, "meshtastic.connection.established")
        pub.subscribe(self.onNodeUpdated, "meshtastic.node.updated")
        
    def connect(self):
        interface_info = self.config.interface_info
        
        logging.info(f'Connecting with interface: {interface_info.interface_type}')
        
        if interface_info.interface_type == 'serial':
            try:
                self.iface = meshtastic.serial_interface.SerialInterface()
            except Exception as ex:
                logging.info(f"Error: Could not connect {ex}")
                sys.exit(1)
        elif interface_info.interface_type == 'tcp':
            addr = interface_info.interface_address
            if not addr:
                logging.info(f'interface.address required for tcp connection')
            try:
                self.iface = meshtastic.tcp_interface.TCPInterface(addr)
            except Exception as ex:
                logging.info(f"Error: Could not connect {ex}")
                sys.exit(1)
        elif interface_info.interface_type == 'ble':
            try:
                ble_node = interface_info.interface_ble_node
                self.iface = meshtastic.ble_interface.BLEInterface(address=ble_node)
            except Exception as ex:
                logging.info(f'Error: Could not connect {ex}')
                sys.exit(1)
        else:
            logging.info(f'Unsupported interface: {interface_info.interface_type}')
            return
            
        myinfo = self.iface.getMyUser()
        shortname = myinfo.get('shortName','???')
        longname = myinfo.get('longName','???')
        self.nodes = self.iface.nodes # this should take precedence
        logging.info(f'Bot connected to Mesh node: {shortname} | {longname} with connection {interface_info.interface_type}')
        
    def link_discord(self, discord_client):
        self.discord_client = discord_client
        
    def get_long_name(self, node_id, default = '?'):
        if node_id in self.nodes:
            return self.nodes[node_id]['user'].get('longName', default)
        return default

    def get_short_name(self, node_id, default = '?'):
        if node_id in self.nodes:
            return self.nodes[node_id]['user'].get('shortName', default)
        return default
    
    def get_node_info_from_id(self, node_id):
        if not node_id.startswith('!'):
            node_id = '!' + node_id
        return self.nodes.get(node_id, {})

    def get_node_info_from_num(self, node_num):
        node_id = '!' + hex(node_num)[2:]
        return self.get_node_info_from_id(self, node_id)
    
    def get_node_id_from_num(self, node_num):
        node_id = '!' + hex(node_num)[2:]
        return node_id

    def get_node_info_from_shortname(self, shortname):
        nodes = [node_data for node_data in self.nodes.values() if node_data.get('user',{}).get('shortName',)==shortname]
        if len(nodes) == 1:
            return nodes[0]
        else:
            logging.info(f'Number of nodes found matching this shortname was {len(nodes)}')
            return len(nodes)

    def get_node_info_from_longname(self, longname):
        nodes = [node_data for node_data in self.nodes.values() if node_data.get('user',{}).get('longName',)==longname]
        if len(nodes) == 1:
            return nodes[0]
        else:
            logging.info(f'Number of nodes found matching this shortname was {len(nodes)}')
            return len(nodes)
        
    def enqueue_send_channel(self, channel, message):
        self.enqueue_msg(
            {
                'msg_type': 'send_channel',
                'channel': channel,
                'message': message
            }
        )
        
    def enqueue_send_nodenum(self, nodenum, message):
        self.enqueue_msg(
            {
                'msg_type': 'send_nodenum',
                'nodenum': nodenum,
                'message': message
            }
        )
        
    def enqueue_send_nodeid(self, nodeid, message):
        self.enqueue_msg(
            {
                'msg_type': 'send_nodeid',
                'nodeid': nodeid,
                'message': message
            }
        )
        
    def enqueue_send_shortname(self, shortname, message, guild_id, channel_id, discord_message_id):
        
        
        self.enqueue_msg(
            {
                'msg_type': 'send_shortname',
                'shortname': shortname,
                'message': message,
                'guild_id': guild_id,
                'channel_id': channel_id,
                'discord_message_id': discord_message_id,
            }
        )
        
    def enqueue_active_nodes(self, active_time):
        self.enqueue_admin_msg(
            {
                'msg_type': 'active_nodes',
                'active_time': active_time
            }
        )
        
    def enqueue_all_nodes(self):
        self.enqueue_admin_msg(
            {
                'msg_type': 'all_nodes',
            }
        )
        
    def enqueue_msg(self, msg):
        self._meshqueue.put(msg)
        
    def enqueue_admin_msg(self, msg):
        self._adminqueue.put(msg)
        
    def insert_tx_packet_to_db(self, sent_packet, discord_guild_id, discord_channel_id, discord_message_id, ack_requested=True):
        
        channel = sent_packet.channel
        hop_limit = sent_packet.hop_limit
        packet_id = sent_packet.id
        dest = sent_packet.to
        dest_id = self.get_node_id_from_num(dest)
        dest_shortname = self.get_short_name(dest_id)
        dest_longname = self.get_long_name(dest_id)
        
        db_pkt_obj = TXPacket(
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
        self._db_session.add(db_pkt_obj)
        self._db_session.commit()
        
    def process_queue_message(self, msg):
        if isinstance(msg, dict):
            msg_type = msg.get('msg_type')
            if msg_type == 'send_channel':
                channel = msg.get('channel')
                message = msg.get('message')
                discord_guild_id = msg.get('guild_id')
                discord_channel_id = msg.get('channel_id')
                discord_message_id = msg.get('discord_message_id')
                logging.info(f'Sending message to channel: {channel}')
                sent_packet = self.iface.sendText(message, channelIndex=channel, wantResponse=True, wantAck=True, onResponse=self.onMsgResponse)
                self.insert_tx_packet_to_db(sent_packet, discord_guild_id, discord_channel_id, discord_message_id)
            elif msg_type == 'send_nodenum':
                nodenum = msg.get('nodenum')
                message = msg.get('message')
                discord_guild_id = msg.get('guild_id')
                discord_channel_id = msg.get('channel_id')
                discord_message_id = msg.get('discord_message_id')
                logging.info(f'Sending message to: {nodenum}')
                sent_packet = self.iface.sendText(message, destinationId=nodenum, wantResponse=True, wantAck=True, onResponse=self.onMsgResponse)
                self.insert_tx_packet_to_db(sent_packet, discord_guild_id, discord_channel_id, discord_message_id)
            elif msg_type == 'send_nodeid':
                nodeid = msg.get('nodeid')
                message = msg.get('message')
                nodenum = int(nodeid, 16)
                discord_guild_id = msg.get('guild_id')
                discord_channel_id = msg.get('channel_id')
                discord_message_id = msg.get('discord_message_id')
                logging.info(f'Sending message to: {nodenum}')
                sent_packet = self.iface.sendText(message, destinationId=nodenum, wantResponse=True, wantAck=True, onResponse=self.onMsgResponse)
                self.insert_tx_packet_to_db(sent_packet, discord_guild_id, discord_channel_id, discord_message_id)
            elif msg_type == 'send_shortname':
                shortname = msg.get('shortname')
                message = msg.get('message')
                node_info = self.get_node_info_from_shortname(shortname)
                nodenum = node_info.get('num')
                discord_guild_id = msg.get('guild_id')
                discord_channel_id = msg.get('channel_id')
                discord_message_id = msg.get('discord_message_id')
                logging.info(f'Sending message to: {nodenum}')                
                sent_packet = self.iface.sendText(message, destinationId=nodenum, wantResponse=True, wantAck=True, onResponse=self.onMsgResponse)
                self.insert_tx_packet_to_db(sent_packet, discord_guild_id, discord_channel_id, discord_message_id)
            
    def process_admin_queue_message(self, msg):
        if isinstance(msg, dict):
            msg_type = msg.get('msg_type')
            if msg_type == 'active_nodes':
                active_time = msg.get('active_time')
                chunks = self.get_active_nodes(active_time)
                if self.discord_client:
                    for chunk in chunks:
                        self.discord_client.enqueue_msg(chunk)
            elif msg_type == 'all_nodes':
                chunks = self.get_all_nodes()
                if self.discord_client:
                    for chunk in chunks:
                        self.discord_client.enqueue_msg(chunk)
            else:
                pass
            
    def get_active_nodes(self, time_limit=15):

        logging.info(f'get_active_nodes has been called with: {time_limit} mins')

        # use self.nodes that was pulled 1m ago
        nodelist = []
        time_limit = int(time_limit)
        nodelist_start = f"**Nodes seen in the last {time_limit} minutes:**\n"

        for node in self.nodes.values():
            try:
                id = node.get('user',{}).get('id','???')
                shortname = node.get('user',{}).get('shortName','???')
                longname = node.get('user',{}).get('longName','???')
                hopsaway = node.get('hopsAway', '?')
                snr = node.get('snr','?')

                # some nodes don't have last heard, when listing active nodes, don't return these
                lastheard = node.get('lastHeard')
                if lastheard: # ignore if doesn't have lastHeard property
                    ts = int(lastheard)
                    # if ts > time.time() - (time_limit * 60): # Only include if its less then time_limit
                    timezone = pytz.timezone(self.config.time_zone)
                    local_time = datetime.fromtimestamp(ts, tz=pytz.utc).astimezone(timezone)
                    timestr = local_time.strftime('%d %B %Y %I:%M:%S %p')
                else:
                    timestr = '???'
                    ts = 0

                # check if they are greater then the time limit
                if ts > time.time() - (time_limit * 60):
                    nodelist.append([f"\n {id} | {shortname} | {longname} | **Hops:** {hopsaway} | **SNR:** {snr} | **Last Heard:** {timestr}",ts])

            except KeyError as e:
                logging.error(e)
                pass

        if len(nodelist) == 0:
            # no nodes found, change response
            nodelist_start = f'**No Nodes seen in the last {time_limit} minutes**'
            
        # sort nodelist and remove ts from it
        nodelist_sorted = sorted(nodelist, key=lambda x: x[1], reverse=True)
        nodelist_sorted = [x[0] for x in nodelist_sorted]
        nodelist_sorted.insert(0, nodelist_start)

        # Split node list into chunks of 10 rows.
        nodelist_chunks = ["".join(nodelist_sorted[i:i + 10]) for i in range(0, len(nodelist_sorted), 10)]
        return nodelist_chunks
    
    def get_all_nodes(self):
        # Get All nodes = BIG print.
        logging.info(f'get_all_nodes has been called')

        # use self.nodes that was pulled 1m ago
        nodelist = []
        
        nodelist_start = f"**All Nodes Seen:**\n"

        for node in self.nodes.values():
            try:
                id = node.get('user',{}).get('id','???')
                shortname = node.get('user',{}).get('shortName','???')
                longname = node.get('user',{}).get('longName','???')
                hopsaway = node.get('hopsAway', '?')
                snr = node.get('snr','?')

                # some nodes don't have last heard, when listing active nodes, don't return these
                lastheard = node.get('lastHeard')
                if lastheard: # ignore if doesn't have lastHeard property
                    ts = int(lastheard)
                    # if ts > time.time() - (time_limit * 60): # Only include if its less then time_limit
                    timezone = pytz.timezone(self.config.time_zone)
                    local_time = datetime.fromtimestamp(ts, tz=pytz.utc).astimezone(timezone)
                    timestr = local_time.strftime('%d %B %Y %I:%M:%S %p')
                else:
                    timestr = '???'
                    ts = 0
                nodelist.append([f"\n {id} | {shortname} | {longname} | **Hops:** {hopsaway} | **SNR:** {snr} | **Last Heard:** {timestr}",ts])

            except KeyError as e:
                logging.error(e)
                pass

        # sort nodelist and remove ts from it
        nodelist_sorted = sorted(nodelist, key=lambda x: x[1], reverse=True)
        nodelist_sorted = [x[0] for x in nodelist_sorted]
        nodelist_sorted.insert(0, nodelist_start)

        # Split node list into chunks of 10 rows.
        nodelist_chunks = ["".join(nodelist_sorted[i:i + 10]) for i in range(0, len(nodelist_sorted), 10)]
        return nodelist_chunks

    def check_battery(self, channel, battery_warning=battery_warning):
        # runs every minute, not eff but idk what else to do

        shortname = self.myNodeInfo.get('user',{}).get('shortName','???')
        longname = self.myNodeInfo.get('user',{}).get('longName','???')
        battery_level = self.myNodeInfo.get('deviceMetrics',{}).get('batteryLevel',100)
        if battery_level > (battery_warning + battery_level/2):
            self.battery_warning_sent = False
        elif self.battery_warning_sent is False and battery_level < battery_warning:
            logging.info(f'Battery is below threshold, sending message to discord')
            self.battery_warning_sent = True
            # send message to discord
            text = (
                f"**NodeName:** {shortname} | {longname}\n"
                f"**Battery Level:** {battery_level}%"
            )
            embed = discord.Embed(
                title='Node Battery Low!',
                description=text,
                color=red_color
            )
            if self.discord_client:
                self.discord_client.enqueue_msg(embed)
        
    def background_process(self):
        
        # don't do this stuff every time...
        # self.nodes = self.iface.nodes
        # self.myNodeInfo = self.iface.getMyNodeInfo()
        
        # do this stuff every time
        try:
            meshmessage = self._meshqueue.get_nowait()
            self.process_queue_message(meshmessage)
            self._meshqueue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            logging.exception('Exception processing meshqueue', exc_info=e)
        
        try:
            adminmessage = self._adminqueue.get_nowait()
            self.process_admin_queue_message(adminmessage)
            self._meshqueue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            logging.exception('Exception processing meshqueue', exc_info=e)
        
