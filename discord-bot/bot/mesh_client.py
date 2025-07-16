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
from util import MeshBotColors

from db_classes import TXPacket, MeshNodeDB

# move all of this to config
battery_warning = 15 # move to config


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
                if mesh_channel_index is None:
                    mesh_channel_index = 0
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

                embed = discord.Embed(title="Message Received", description=packetObj.decoded.text, color=MeshBotColors.RX())
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

        self.myNodeInfo = interface.getMyNodeInfo()
        self.my_node_info = MeshNode(self.myNodeInfo) # TODO: use this as myNodeInfo


        self.nodes = self.iface.nodes # this should take precedence

        # use nodesByNum because it will include ones that we do not have userInfo for
        for node_num, node in self.iface.nodesByNum.items():
            # see if node with num exists in db
            matching_node = self._db_session.query(MeshNodeDB).filter_by(node_num=node_num).first()
            if matching_node:
                # TODO: Make update func
                pass
            else:
                new_node = MeshNodeDB.from_dict(node, self)
                self._db_session.add(new_node)
        # should only need to commit once
        self._db_session.commit()

        logging.info('***CONNECTED***')
        logging.info('***************')
        logging.info(f'Node Num:   {self.my_node_info.node_num}')
        logging.info(f'Node ID:    {self.my_node_info.user_info.user_id}')
        logging.info(f'Short Name: {self.my_node_info.user_info.short_name}')
        logging.info(f'Long Name:  {self.my_node_info.user_info.long_name}')
        logging.info(f'MAC Addr:   {self.my_node_info.user_info.mac_address}')
        logging.info(f'HW Model:   {self.my_node_info.user_info.hw_model}')
        logging.info('***************')

    def onNodeUpdated(self, node, interface):
        # this happens when a node gets updated... we should update the database
        logging.info(str(type(node)))
        logging.info(str(dir(node)))

    def onMsgResponse(self, d):
        # if there is a request Id... look it up in the Db and acknowledge
        
        # TODO: Create a Node obj and use it here?
        response_from = d.get('from')
        response_to = d.get('to')
        response_from_id = d.get('fromId')
        response_to_id = d.get('toId')
        response_from_shortname = self.get_short_name(response_from_id)
        response_from_longname =  self.get_long_name(response_from_id)
        response_to_shortname = self.get_short_name(response_to_id)
        response_to_longname =  self.get_long_name(response_to_id)
        
        # TODO: Create a Packet obj and use it here?
        
        response_id = d.get('id')
        response_rx_time = d.get('rxTime')
        response_rx_snr = d.get('rxSnr')
        response_rx_rssi = d.get('rxRssi')
        response_hop_limit = d.get('hopLimit')
        response_hop_start = d.get('hopStart')
        request_id = d.get('decoded', {}).get('requestId')
        routing_error_reason = d.get('decoded', {}).get('routing', {}).get('errorReason')

        logging.info(f'Got Response to packet: {request_id} from {response_from_id}')
        
        matching_packet = self._db_session.query(TXPacket).filter_by(packet_id=request_id).first()
        if matching_packet:
            # if we find the packet in the db matching the request ID of the ACK... update it to say
            # it is acknowledged
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
                
                # enqueue response to be sent back to discord
                self.discord_client.enqueue_ack(matching_packet.discord_message_id, response_from_id, response_rx_rssi, response_rx_snr, response_hop_start, response_hop_limit)
        else:
            logging.error(f'No matching packet found for request_id: {request_id}.\n Maybe the packet isnt in the DB yet, and/or is this a self-ack?')


    def __init__(self, db_session, config):
        self.config = config
        
        # queue for incoming requests (e.g. from discord bot commands) to send things over the mesh
        self._meshqueue = queue.Queue(maxsize=20)
        
        # queue to perform admin actions involving the node
        self._adminqueue = queue.Queue(maxsize=20)

        # sqlalchemy database session
        self._db_session = db_session
        
        # reference to discord client - used for sending responses to user
        self.discord_client = None
        
        # meshtastic stuff
        self.iface = None
        self.nodes = {}
        self.myNodeInfo = None #TODO: switch this to use the node object created onConnectionMesh
        self.my_node_info = None

        

    def connect(self):
        """Connect to meshtastic device and subscribe to events for processing."""
        
        interface_info = self.config.interface_info

        logging.info(f'Connecting with interface: {interface_info.connection_descriptor}')

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

        pub.subscribe(self.onReceiveMesh, "meshtastic.receive")
        pub.subscribe(self.onConnectionMesh, "meshtastic.connection.established")
        pub.subscribe(self.onNodeUpdated, "meshtastic.node.updated")

    def link_discord(self, discord_client):
        self.discord_client = discord_client
        
    # TODO: remove these and use node objs everywhere

    def get_long_name(self, node_id, default = '?'):
        if node_id in self.nodes:
            return self.nodes[node_id]['user'].get('longName', default)
        elif node_id.lower() == '!ffffffff':
            return 'Broadcast'
        return default

    def get_short_name(self, node_id, default = '?'):
        if node_id in self.nodes:
            return self.nodes[node_id]['user'].get('shortName', default)
        elif node_id.lower() == '!ffffffff':
            return '^all'
        return default
    
    def get_node_descriptive_string(self, node_id=None, nodenum=None, shortname=None, default = '?'):

        if node_id:
            if node_id in self.nodes:
                return f'{node_id} | {self.get_short_name(node_id,default=default)} | {self.get_long_name(node_id, default=default)}'
        else:
            node_id = self.get_node_id(node_id=node_id, nodenum=nodenum, shortname=shortname)
            return self.get_node_descriptive_string(node_id=node_id)
        
        return default
    
    def get_node_info(self, node_id=None, nodenum=None, shortname=None, longname=None):
        if node_id:
            if not node_id.startswith('!'):
                node_id = '!' + node_id
            return self.nodes.get(node_id, {})
        if nodenum:
            node_id = '!' + hex(nodenum)[2:]
            return self.get_node_info(node_id=node_id)
        
        if shortname:
            nodes = [node_data for node_data in self.nodes.values() if node_data.get('user',{}).get('shortName',)==shortname]
            if len(nodes) == 1:
                return nodes[0]
            else:
                logging.info(f'Number of nodes found matching this shortname was {len(nodes)}')
                return None
            
        if longname:
            nodes = [node_data for node_data in self.nodes.values() if node_data.get('user',{}).get('longName',)==longname]
            if len(nodes) == 1:
                return nodes[0]
            else:
                logging.info(f'Number of nodes found matching this shortname was {len(nodes)}')
                return None
        
    def get_node_id(self, node_id=None, nodenum=None, shortname=None, longname=None):
        node = self.get_node_info(node_id=node_id, nodenum=nodenum, shortname=shortname, longname=longname)
        return node.get('user', {}).get('id')
    
    def get_node_num(self, node_id=None, nodenum=None, shortname=None, longname=None):
        node = self.get_node_info(node_id=node_id, nodenum=nodenum, shortname=shortname, longname=longname)
        return node.get('num')
        
    # admin tasks
        
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

        #TODO: use Node obj created in onConnectionMesh. Possibly make it auto-updating when accessed

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
                color=MeshBotColors.error()
            )
            if self.discord_client:
                self.discord_client.enqueue_msg(embed)

        
    # methods to ensure we enqueue the proper type of command/message

    def enqueue_send_channel(self, channel, message):
        """
        Puts a message on the queue to be sent on the specified channel.

        Args:
            channel: Channel Index to send the message on.
            message: Message text to send.
        """
        
        self._enqueue_msg(
            {
                'msg_type': 'send_channel',
                'channel': channel,
                'message': message
            }
        )

    def enqueue_send_nodenum(self, nodenum, message, guild_id, channel_id, discord_message_id):
        """
        Puts a message on the queue to be sent to a specific node (DM) by node number.

        Args:
            nodenum: Node to DM.
            message: Message text to send.
            guild_id: Guild ID of Discord server hosting the bot.
            channel_id: Channel ID the message was sent on.
            discord_message_id: Message ID of the command message.
        """
        
        self._enqueue_msg(
            {
                'msg_type': 'send_nodenum',
                'nodenum': nodenum,
                'message': message,
                'guild_id': guild_id,
                'channel_id': channel_id,
                'discord_message_id': discord_message_id,
            }
        )

    def enqueue_send_nodeid(self, nodeid, message, guild_id, channel_id, discord_message_id):
        """
        Puts a message on the queue to be sent to a specific node (DM) by ID.

        Args:
            nodeid: Node to DM.
            message: Message text to send.
            guild_id: Guild ID of Discord server hosting the bot.
            channel_id: Channel ID the message was sent on.
            discord_message_id: Message ID of the command message.
        """
        
        self._enqueue_msg(
            {
                'msg_type': 'send_nodeid',
                'nodeid': nodeid,
                'message': message,
                'guild_id': guild_id,
                'channel_id': channel_id,
                'discord_message_id': discord_message_id,
            }
        )

    def enqueue_send_shortname(self, shortname, message, guild_id, channel_id, discord_message_id):
        """
        Puts a message on the queue to be sent to a specific node (DM) by short name.

        Args:
            nodeid: Node to DM.
            message: Message text to send.
            guild_id: Guild ID of Discord server hosting the bot.
            channel_id: Channel ID the message was sent on.
            discord_message_id: Message ID of the command message.
        """


        self._enqueue_msg(
            {
                'msg_type': 'send_shortname',
                'shortname': shortname,
                'message': message,
                'guild_id': guild_id,
                'channel_id': channel_id,
                'discord_message_id': discord_message_id,
            }
        )

    def enqueue_active_nodes(self, active_time, method='node_db'):
        """
        Requests the active nodes.

        Args:
            active_time: Time to look back to find active nodes.
            method: Method used to calculate (node_db, db)
        """
        
        self._enqueue_admin_msg(
            {
                'msg_type': 'active_nodes',
                'active_time': active_time,
                'method': method,
            }
        )

    def enqueue_all_nodes(self, method='node_db'):
        """
        Requests all nodes in node db.
        
        Args:
            method: Method used to calculate (node_db, db)
            
        """
        self._enqueue_admin_msg(
            {
                'msg_type': 'all_nodes',
                'method': method,
            }
        )

    def _enqueue_msg(self, msg):
        """
        Puts a message on the queue for processing.
        
        Args:
            msg: Command message
            
        """
        self._meshqueue.put(msg)

    def _enqueue_admin_msg(self, msg):
        """
        Puts a message on the queue for processing.
        
        Args:
            msg: Command message
            
        """
        self._adminqueue.put(msg)

    def _send_channel(self, channel, message, discord_guild_id=None, discord_channel_id=None, discord_message_id=None):
        logging.info(f'Sending message to channel: {channel}')
        sent_packet = self.iface.sendText(message, channelIndex=channel, wantResponse=True, wantAck=True, onResponse=self.onMsgResponse)
        TXPacket.insert(sent_packet=sent_packet, discord_guild_id=discord_guild_id, discord_channel_id=discord_channel_id, discord_message_id=discord_message_id, mesh_client=self)
    
    def _send_dm(self, nodenum, message, discord_guild_id=None, discord_channel_id=None, discord_message_id=None):
        logging.info(f'Sending message to: {nodenum}')
        sent_packet = self.iface.sendText(message, destinationId=nodenum, wantResponse=True, wantAck=True, onResponse=self.onMsgResponse)
        if sent_packet:
            self.discord_client.enqueue_tx_confirmation(discord_message_id)
            TXPacket.insert(sent_packet=sent_packet, discord_guild_id=discord_guild_id, discord_channel_id=discord_channel_id, discord_message_id=discord_message_id, mesh_client=self)
    
    # queue processing

    def process_queue_message(self, msg):
        if isinstance(msg, dict):
            msg_type = msg.get('msg_type')
            message = msg.get('message')
            discord_guild_id = msg.get('guild_id')
            discord_channel_id = msg.get('channel_id')
            discord_message_id = msg.get('discord_message_id')
            
            if msg_type == 'send_channel':
                channel = msg.get('channel')
                self._send_channel(channel, message, discord_guild_id, discord_channel_id, discord_message_id)

            elif msg_type == 'send_nodenum':
                nodenum = msg.get('nodenum')
                self._send_dm(nodenum, message, discord_guild_id, discord_channel_id, discord_message_id)
            elif msg_type == 'send_nodeid':
                nodeid = msg.get('nodeid')
                nodenum = self.get_node_num(node_id=nodeid)
                if not nodenum:
                    self.discord_client.enqueue_tx_error(discord_message_id, f'Node ID: {nodeid} not found.')
                    return
                # TODO: If we did not get a nodenum back... respond to the original message with a 
                # descriptive error
                self._send_dm(nodenum, message, discord_guild_id, discord_channel_id, discord_message_id)
            elif msg_type == 'send_shortname':
                shortname = msg.get('shortname')
                nodenum = self.get_node_num(shortname=shortname)
                # TODO: If we did not get a nodenum back... respond to the original message with a 
                # descriptive error
                self._send_dm(nodenum, message, discord_guild_id, discord_channel_id, discord_message_id)
        else:
            logging.error(f'Unknown message type in mesh queue: {type(msg)}')
            logging.error(f'Message content: {msg}')

    def process_admin_queue_message(self, msg):
        if isinstance(msg, dict):
            msg_type = msg.get('msg_type')
            if msg_type == 'active_nodes':
                active_time = msg.get('active_time')
                method = msg.get('method') #TODO: Implement different way or getting active nodes
                chunks = self.get_active_nodes(active_time)
                if self.discord_client:
                    for chunk in chunks:
                        self.discord_client.enqueue_msg(chunk)
            elif msg_type == 'all_nodes':
                method = msg.get('method') #TODO: Implement different way or getting all nodes
                chunks = self.get_all_nodes()
                if self.discord_client:
                    for chunk in chunks:
                        self.discord_client.enqueue_msg(chunk)
            else:
                pass

    def background_process(self):

        #TODO: Update nodes. Not sure if we can do it every time.
        #TODO: Update local nodeDB (SQL)
        # self.nodes = self.iface.nodes

        #TODO: use Node obj created in onConnectionMesh. Possibly make it auto-updating when accessed
        # instead of updating here
        self.myNodeInfo = self.iface.getMyNodeInfo()

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
            self._adminqueue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            logging.exception('Exception processing adminqueue', exc_info=e)

