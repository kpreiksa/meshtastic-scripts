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

from mesh_node_classes import MeshNode

from db_classes import TXPacket, RXPacket, ACK, MeshNodeDB

# move all of this to config
battery_warning = 15 # move to config


class MeshClient():

    def onReceiveMesh(self, packet, interface):  # Called when a packet arrives from mesh.

        try:
            db_packet = RXPacket.from_dict(packet, self)
            self._db_session.add(db_packet)
            self._db_session.commit() # save back to db
            
            if db_packet.is_text_message:
                logging.info(f"Text message packet received from: {db_packet.src_descriptive}") # For debugging.
                self.discord_client.enqueue_mesh_text_msg_received(packet)

            elif db_packet.portnum == 'ROUTING_APP':
                if db_packet.priority == 'ACK':
                    if db_packet.request_id:

                        logging.info(f'Got ACK from {db_packet.src_descriptive}. Request ID: {db_packet.request_id}')
                        
                        matching_packet = self._db_session.query(TXPacket).filter_by(packet_id=db_packet.request_id).first()
                        if matching_packet:
                            # if we find the packet in the db matching the request ID of the ACK... update it to say
                            # it is acknowledged

                            matching_packet.acknowledge_received = True
                            implicit_ack = db_packet.src_id == self.my_node_info.user_info.user_id
                            ack_obj = ACK.from_rx_packet(db_packet, self)
                            self._db_session.add(ack_obj)
                            matching_packet.acks.append(ack_obj)
                            self._db_session.commit() # save back to db
                            
                            self.discord_client.enqueue_ack(matching_packet.discord_message_id, db_packet.src_id, db_packet.rx_rssi, db_packet.rx_snr, db_packet.hop_start, db_packet.hop_limit, is_implicit=implicit_ack)
                        else:
                            logging.error(f'No matching packet found for request_id: {db_packet.request_id}.\n Maybe the packet isnt in the DB yet, and/or is this a self-ack?')
            else:
                logging.info(f'Received unhandled packet type: {db_packet.portnum}')

        except Exception as e:
            logging.error(f'Error parsing packet: {str(e)}')

    def onConnectionMesh(self, interface, topic=None):
        # interface, obj

        self.myNodeInfo = interface.getMyNodeInfo()
        self.my_node_info = MeshNode(self.myNodeInfo) # TODO: this is the only place this is used. probably remove this class and reference it from the DB or soemthing

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
        logging.info(f'Node Num:              {self.my_node_info.node_num}')
        logging.info(f'Node ID:               {self.my_node_info.user_info.user_id}')
        logging.info(f'Short Name:            {self.my_node_info.user_info.short_name}')
        logging.info(f'Long Name:             {self.my_node_info.user_info.long_name}')
        logging.info(f'MAC Addr:              {self.my_node_info.user_info.mac_address}')
        logging.info(f'HW Model:              {self.my_node_info.user_info.hw_model}')
        logging.info(f'Device Role:           {interface.localNode.localConfig.device.role}')
        logging.info(f'Node Info Periodicity: {interface.localNode.localConfig.device.node_info_broadcast_secs}')
        logging.info(f'Modem Preset:          {interface.localNode.localConfig.lora.modem_preset}')
        logging.info(f'TX Power:              {interface.localNode.localConfig.lora.tx_power}')
        logging.info('***************')
        
        node_descriptor = f'{self.my_node_info.user_info.user_id} | {self.my_node_info.user_info.short_name} | {self.my_node_info.user_info.long_name}'
        self.discord_client.enqueue_mesh_ready(node_descriptor, interface.localNode.localConfig.lora.modem_preset)

    def onDisconnect(self, interface):
        # this happens when a node gets updated... we should update the database
        self.discord_client.enqueue_lost_comm('Disconnect Event Received')
        logging.error('disconnected')

    def onNodeUpdated(self, node, interface):
        # this happens when a node gets updated... we should update the database
        logging.info(str(type(node)))
        logging.info(str(dir(node)))

    def onMsgResponse(self, d):
        # if there is a request Id... look it up in the Db and acknowledge
        
        db_packet = RXPacket.from_dict(d, self)
        self._db_session.add(db_packet)
        self._db_session.commit() # save back to db
        
        logging.info(f'Got Response to packet: {db_packet.request_id} from {db_packet.src_descriptive})')
        
        matching_packet = self._db_session.query(TXPacket).filter_by(packet_id=db_packet.request_id).first()
        if matching_packet:
            # if we find the packet in the db matching the request ID of the ACK... update it to say
            # it is acknowledged
            matching_packet.acknowledge_received = True
            
            implicit_ack = db_packet.request_id == self.my_node_info.user_info.user_id
            ack_obj = ACK.from_rx_packet(db_packet, self)
            
            self._db_session.add(ack_obj)
            matching_packet.acks.append(ack_obj)
            self._db_session.commit() # save back to db
            
            # enqueue response to be sent back to discord
            self.discord_client.enqueue_ack(matching_packet.discord_message_id, db_packet.src_id, db_packet.rx_rssi, db_packet.rx_snr, db_packet.hop_start, db_packet.hop_limit, is_implicit=implicit_ack)
        else:
            logging.error(f'No matching packet found for request_id: {db_packet.request_i}.\n Maybe the packet isnt in the DB yet, and/or is this a self-ack?')

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
        pub.subscribe(self.onDisconnect, 'meshtastic.connection.lost')

    def link_discord(self, discord_client):
        self.discord_client = discord_client
        
    # TODO: remove these and use node objs/db everywhere

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
        if node_id:
            return node_id
        elif nodenum:
            node_id = '!' + hex(nodenum)[2:]
            return node_id
        else:
            node = self.get_node_info(shortname=shortname, longname=longname)
            return node.get('user', {}).get('id')
    
    def get_node_num(self, node_id=None, nodenum=None, shortname=None, longname=None):
        
        if nodenum:
            return nodenum
        
        elif node_id:
            if node_id.startswith('!'):
                node_id = node_id.strip('!')
            try:
                nodenum = int(node_id, 16)
                return nodenum
            except: # could not convert to int... probably an invalid node_id
                return None
        else:
            node = self.get_node_info(shortname=shortname, longname=longname)
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
                # is_self = False
                id = node.get('user',{}).get('id','???')
                if id == self.my_node_info.user_info.user_id:
                    # do not include SELF
                    continue
                    # is_self = True
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
                    # if is_self:
                    #     nodelist.append([f"\n {id} (**SELF**) | {shortname} | {longname} | **Hops:** {hopsaway} | **SNR:** {snr} | **Last Heard:** {timestr}",ts])
                    # else:
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
                # is_self = False
                id = node.get('user',{}).get('id','???')
                if id == self.my_node_info.user_info.user_id:
                    # do not include SELF
                    continue
                    # is_self = True
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
                    
                # if is_self:
                #     nodelist.append([f"\n {id} (**SELF**) | {shortname} | {longname} | **Hops:** {hopsaway} | **SNR:** {snr} | **Last Heard:** {timestr}",ts])
                # else:
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
        
        
        battery_level = self.myNodeInfo.get('deviceMetrics',{}).get('batteryLevel',100)
        
        self.my_node_info.device_metrics.battery_level
        if battery_level > (battery_warning + battery_level/2):
            self.battery_warning_sent = False
        elif self.battery_warning_sent is False and battery_level < battery_warning:
            logging.info(f'Battery is below threshold, sending message to discord')
            self.battery_warning_sent = True
            # send message to discord
            text = (
                f"**NodeName:** {self.my_node_info.user_info.short_name} | {self.my_node_info.user_info.long_name}\n"
                f"**Battery Level:** {battery_level}%"
            )
            
            self.discord_client.enqueue_battery_low_alert(text)


        
    # methods to ensure we enqueue the proper type of command/message

    def enqueue_send_channel(self, channel, message, discord_interaction_info):
        """
        Puts a message on the queue to be sent on the specified channel.

        Args:
            channel: Channel Index to send the message on.
            message: Message text to send.
            discord_interaction_info: Information about discord message to fascilitate replies.
        """
        
        self._enqueue_msg(
            {
                'msg_type': 'send_channel',
                'channel': channel,
                'message': message,
                'discord_interaction_info': discord_interaction_info,
            }
        )

    def enqueue_send_nodenum(self, nodenum, message, discord_interaction_info):
        """
        Puts a message on the queue to be sent to a specific node (DM) by node number.

        Args:
            nodenum: Node to DM.
            message: Message text to send.
            discord_interaction_info: Information about discord message to fascilitate replies.
        """
        
        self._enqueue_msg(
            {
                'msg_type': 'send_nodenum',
                'nodenum': nodenum,
                'message': message,
                'discord_interaction_info': discord_interaction_info,
            }
        )

    def enqueue_send_nodeid(self, nodeid, message, discord_interaction_info):
        """
        Puts a message on the queue to be sent to a specific node (DM) by ID.

        Args:
            nodeid: Node to DM.
            message: Message text to send.
            discord_interaction_info: Information about discord message to fascilitate replies.
        """
        
        self._enqueue_msg(
            {
                'msg_type': 'send_nodeid',
                'nodeid': nodeid,
                'message': message,
                'discord_interaction_info': discord_interaction_info,
            }
        )

    def enqueue_send_shortname(self, shortname, message, discord_interaction_info):
        """
        Puts a message on the queue to be sent to a specific node (DM) by short name.

        Args:
            nodeid: Node to DM.
            message: Message text to send.
            discord_interaction_info: Information about discord message to fascilitate replies.
        """


        self._enqueue_msg(
            {
                'msg_type': 'send_shortname',
                'shortname': shortname,
                'message': message,
                'discord_interaction_info': discord_interaction_info,
            }
        )

    def enqueue_telemetry_broadcast(self, discord_interaction_info):
        """
        Enqueues a telemetry broadcast

        Args:
            discord_interaction_info: Information about discord message to fascilitate replies.
        """
        
        self._enqueue_msg(
            {
                'msg_type': 'telemetry_broadcast',
                'discord_interaction_info': discord_interaction_info,
            }
        )

    def enqueue_telemetry_nodenum(self, nodenum, discord_interaction_info):
        """
        Enqueues a telemetry request to the specified node.

        Args:
            nodenum: Node to send telemetry request to.
            discord_interaction_info: Information about discord message to fascilitate replies.
        """
        
        self._enqueue_msg(
            {
                'msg_type': 'telemetry_nodenum',
                'nodenum': nodenum,
                'discord_interaction_info': discord_interaction_info,
            }
        )

    def enqueue_telemetry_nodeid(self, nodeid, discord_interaction_info):
        """
        Enqueues a telemetry request to the specified node.

        Args:
            nodeid: Node tp send telemetry request to.
            discord_interaction_info: Information about discord message to fascilitate replies.
        """
        
        self._enqueue_msg(
            {
                'msg_type': 'telemetry_nodeid',
                'nodeid': nodeid,
                'discord_interaction_info': discord_interaction_info,
            }
        )

    def enqueue_telemetry_shortname(self, shortname, discord_interaction_info):
        """
        Enqueues a telemetry request to the specified node.

        Args:
            nodeid: Node tp send telemetry request to.
            discord_interaction_info: Information about discord message to fascilitate replies.
        """


        self._enqueue_msg(
            {
                'msg_type': 'telemetry_shortname',
                'shortname': shortname,
                'discord_interaction_info': discord_interaction_info,
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
        
    def enqueue_traceroute(self, node_id):
        """
        Requests all nodes in node db.
        
        Args:
            node_id: Node ID to traceroute
            
        """
        self._enqueue_admin_msg(
            {
                'msg_type': 'traceroute_node_id',
                'node_id': node_id,
                # 'guild_id': guild_id,
                # 'channel_id': channel_id,
                # 'discord_message_id': discord_message_id
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

    # single-point to the meshtastic APIs

    def _send_channel(self, channel, message, discord_interaction_info=None):
        logging.info(f'Sending message to channel: {channel}')
        sent_packet = self.iface.sendText(message, channelIndex=channel, wantResponse=True, wantAck=True)
        if sent_packet:
            self.discord_client.enqueue_tx_confirmation(discord_interaction_info.message_id)
        pkt = TXPacket.from_sent_packet(sent_packet=sent_packet, discord_interaction_info=discord_interaction_info, mesh_client=self)
        self._db_session.add(pkt)
        self._db_session.commit()
    
    def _send_dm(self, nodenum, message, discord_interaction_info=None):
        logging.info(f'Sending message to: {nodenum}')
        sent_packet = self.iface.sendText(message, destinationId=nodenum, wantResponse=True, wantAck=True, onResponse=self.onMsgResponse)
        if sent_packet:
            self.discord_client.enqueue_tx_confirmation(discord_interaction_info.message_id)
            pkt = TXPacket.from_sent_packet(sent_packet=sent_packet, discord_interaction_info=discord_interaction_info, mesh_client=self)
            self._db_session.add(pkt)
            self._db_session.commit()
            
    def _send_telemetry(self, nodenum=None, discord_interaction_info=None):
        sent_packet = self.iface.sendTelemetry(wantResponse=True)
        # sent_packet = self.iface.sendTelemetry(nodenum, wantResponse=True)
        if sent_packet:
            self.discord_client.enqueue_tx_confirmation(discord_interaction_info.message_id)
            pkt = TXPacket.from_sent_packet(sent_packet=sent_packet, discord_interaction_info=discord_interaction_info, mesh_client=self)
            self._db_session.add(pkt)
            self._db_session.commit()
    
    # queue processing/background loop

    def process_queue_message(self, msg):
        if isinstance(msg, dict):
            msg_type = msg.get('msg_type')
            message = msg.get('message')
            discord_interaction_info = msg.get('discord_interaction_info')
            
            if msg_type == 'send_channel':
                channel = msg.get('channel')
                self._send_channel(channel, message, discord_interaction_info)

            elif msg_type == 'send_nodenum':
                nodenum = msg.get('nodenum')
                self._send_dm(nodenum, message, discord_interaction_info)
            elif msg_type == 'send_nodeid':
                nodeid = msg.get('nodeid')
                nodenum = self.get_node_num(node_id=nodeid)
                if not nodenum:
                    self.discord_client.enqueue_tx_error(discord_interaction_info.message_id, f'Node ID: {nodeid} is invalid.')
                    return
                # TODO: If we did not get a nodenum back... respond to the original message with a 
                # descriptive error
                self._send_dm(nodenum, message, discord_interaction_info)
            elif msg_type == 'send_shortname':
                shortname = msg.get('shortname')
                nodenum = self.get_node_num(shortname=shortname)
                # TODO: If we did not get a nodenum back... respond to the original message with a 
                # descriptive error
                self._send_dm(nodenum, message, discord_interaction_info)
            elif msg_type == 'telemetry_broadcast':
                # TODO: Add ability to send on other channels if this even makes sense
                self._send_telemetry(discord_interaction_info=discord_interaction_info)
            elif msg_type == 'telemetry_nodenum':
                nodenum = msg.get('nodenum')
                self._send_telemetry(nodenum=nodenum, discord_interaction_info=discord_interaction_info)
            elif msg_type == 'telemetry_nodeid':
                nodeid = msg.get('nodeid')
                nodenum = self.get_node_num(node_id=nodeid)
                if not nodenum:
                    self.discord_client.enqueue_tx_error(discord_interaction_info.message_id, f'Node ID: {nodeid} is invalid.')
                    return
                self._send_telemetry(nodenum=nodenum, discord_interaction_info=discord_interaction_info)
            elif msg_type == 'telemetry_shortname':
                shortname = msg.get('shortname')
                nodenum = self.get_node_num(shortname=shortname)
                self._send_telemetry(nodenum=nodenum, discord_interaction_info=discord_interaction_info)
                
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
            elif msg_type == 'traceroute_nodeid':
                node_id = msg.get('node_id')
                # discord_guild_id = msg.get('guild_id')
                # discord_channel_id = msg.get('channel_id')
                # discord_message_id = msg.get('discord_message_id')
                self.iface.sendTraceRoute(node_id)
                # have to keep track of the traceroute request and respond to it
            else:
                pass

    def background_process(self):

        #TODO: Update nodes. Not sure if we can do it every time.
        #TODO: Update local nodeDB (SQL)
        # self.nodes = self.iface.nodes

        #TODO: use Node obj created in onConnectionMesh. Possibly make it auto-updating when accessed
        # instead of updating here
        self.myNodeInfo = self.iface.getMyNodeInfo()
        
        try:
            self.iface.sendHeartbeat()
        except Exception as e:
            logging.error(f'Heartbeat failed')
            self.discord_client.enqueue_lost_comm(e)

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

