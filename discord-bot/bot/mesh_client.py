from pprint import pprint
import logging
import queue
import sys
import time
import re
from difflib import SequenceMatcher

import datetime

import meshtastic
import meshtastic.ble_interface
import meshtastic.serial_interface
import meshtastic.tcp_interface
import pytz
from pubsub import pub

from mesh_node_classes import MeshNode

from db_classes import TXPacket, RXPacket, ACK, MeshNodeDB

import util
# move all of this to config
battery_warning = 15 # move to config


class MeshClient():

    def onReceiveMesh(self, packet, interface):  # Called when a packet arrives from mesh.

        try:
            from_id = None
            if 'from' in packet and packet['from']:
                from_id = '!' + hex(packet['from'])[2:]
            portnum = packet.get('decoded', {}).get('portnum')

            db_packet = RXPacket.from_dict(packet, self)
            self._db_session.add(db_packet)
            try:
                self._db_session.commit() # save back to db
            except Exception as e:
                logging.error(f'DB ROLLBACK: {str(e)}')
                self._db_session.rollback()

            if db_packet.is_text_message:
                logging.info(f"Text message packet received from: {db_packet.src_descriptive}") # For debugging.
                self.discord_client.enqueue_mesh_text_msg_received(db_packet)

            elif db_packet.portnum == 'NODEINFO_APP':
                # get the nodeinfo and update the MeshNodeDB
                MeshNodeDB.update_from_nodeinfo(packet, self)

            elif db_packet.portnum == 'TRACEROUTE_APP':
                # get the nodeinfo and update the MeshNodeDB
                pass

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
                            try:
                                self._db_session.commit() # save back to db
                            except Exception as e:
                                logging.error(f'DB ROLLBACK: {str(e)}')
                                self._db_session.rollback()

                            self.discord_client.enqueue_ack(ack_obj)
                        else:
                            logging.error(f'No matching packet found for request_id: {db_packet.request_id}.\n Maybe the packet isnt in the DB yet, and/or is this a self-ack?')
            else:
                if portnum:
                    logging.info(f'Received unhandled packet type: {portnum} from: {from_id}')
                else:
                    # couldn't even get portnum. Check if 'encrypted' exists
                    encrypted = packet.get('encrypted')
                    if encrypted:
                        # packet is encrypted. Probably a mismatched key or a relayed message?
                        logging.info(f'Got packet with encrypted attribute, and unable to decode. From: {from_id}')

        except Exception as e:
            logging.error(f'Error parsing packet. Type: {portnum}. From: {from_id}. Exception: {str(type(e))}. Exception Detail: {e}')

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
                pass
                #MeshNodeDB.update_from_nodedb(node_num, node, self)
            else:
                new_node = MeshNodeDB.from_dict(node, self)
                self._db_session.add(new_node)
        # should only need to commit once
        try:
            self._db_session.commit() # save back to db
        except Exception as e:
            logging.error(f'DB ROLLBACK: {str(e)}')
            self._db_session.rollback()

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
        logging.info(f'Modem Preset:          {interface.localNode.localConfig.lora.modem_preset} - {self.config.channel_names[interface.localNode.localConfig.lora.modem_preset]}') # TODO make sure this isn't unique to serial_interface
        logging.info(f'TX Power:              {interface.localNode.localConfig.lora.tx_power}')
        logging.info('***************')

        node_descriptor = f'{self.my_node_info.user_info.user_id} | {self.my_node_info.user_info.short_name} | {self.my_node_info.user_info.long_name}'
        self.discord_client.enqueue_mesh_ready(node_descriptor, interface.localNode.localConfig.lora.modem_preset)

    def onDisconnect(self, interface):
        # this happens when a node gets updated... we should update the database
        self.discord_client.enqueue_lost_comm('Disconnect Event Received')
        logging.error('mesh device disconnected')

    def onNodeUpdated(self, node, interface):
        # this happens when a node gets updated... we should update the database
        logging.info(str(type(node)))
        logging.info(str(dir(node)))

    def onMsgResponse(self, d):
        # if there is a request Id... look it up in the Db and acknowledge

        db_packet = RXPacket.from_dict(d, self)
        self._db_session.add(db_packet)
        try:
            self._db_session.commit() # save back to db
        except Exception as e:
            logging.error(f'DB ROLLBACK: {str(e)}')
            self._db_session.rollback()

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
            try:
                self._db_session.commit() # save back to db
            except Exception as e:
                logging.error(f'DB ROLLBACK: {str(e)}')
                self._db_session.rollback()

            # enqueue response to be sent back to discord
            self.discord_client.enqueue_ack(ack_obj)
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

    def get_long_name(self, node_id=None, default = '?'):
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
                return f'{node_id} | ? | ?'
        else:
            node_id = self.get_node_id(node_id=node_id, nodenum=nodenum, shortname=shortname)
            return self.get_node_descriptive_string(node_id=node_id)

    def determine_node_type(self, node):
        """Gets an input that could be a node shortname, ID or number, and determines which it is
        It always returns a node num (because a node ID can always be converted to number)
        UNLESS the node is a shortname, in which case it returns the shortname - error checking for an invalid node shortname is later
        It does not check if the node ID/short name is valid, just that it is in the correct format.
        """
        # Regex has 4 options:  node shortname, node ID (starts with !), node ID (starts with 0x), or node number
        # must convert 0x to !
        regex = '(^.{1,4}$)|(^![a-zA-Z0-9]{8}$)|(^0x[a-zA-Z0-9]{8}$)|(\\d{1,10}$)'

        matches = re.findall(regex, node)
        if not matches:
            logging.error(f'Error: Node input {node} does not match any known formats.')
            return None, None
        elif len(matches) > 1:
            logging.error(f'Error: Node input {node} matches multiple formats: {matches}. This is not expected.')
            return None, None
        else:
            matches = list(matches[0])
            # find which one is not empty. matches should be a list of 1 tuple, and the tuple will have 4 elements, all should be empty strings except 1
            # check if tuple has 3 empty strings and 1 non-empty string
            empty_str_cnt = matches.count('')
            if empty_str_cnt == 3:
                # find index for non-empty string
                non_empty_index = matches.index(next(filter(lambda x: x != '', matches)))
                match non_empty_index:
                    case 0:
                        # node shortname
                        node_type = 'shortname'
                    case 1:
                        # node ID (starts with !)
                        node = self.get_node_num(node_id=node)
                        node_type = 'nodenum'
                    case 2:
                        # node ID (starts with 0x)
                        node = self.get_node_num(node_id='!'+node[2:])
                        node_type = 'nodenum'
                    case 3:
                        # node number
                        node = int(node)
                        node_type = 'nodenum'
                    case _:
                        logging.error(f'Error: Node input {node} matches an unexpected format: {matches}. This is not expected.')
                        return None
                return node_type, node
            else:
                logging.error(f'Error: Node input {node} matches multiple formats: {matches}. This is not expected.')
                return None, None

    def get_similar_nodes(self, shortname):
        """Given a shortname (that is not in the database), returns a list of the 3 nodes that are most similar shortnames"""
        similar_nodes = []
        for node in self.nodes.values():
            node_shortname = node.get('user', {}).get('shortName', '')
            if node_shortname:
                similarity = SequenceMatcher(None, shortname.lower(), node_shortname.lower()).ratio()
                similar_nodes.append([node_shortname, similarity])
        # sort by similarity
        similar_nodes = sorted(similar_nodes, key=lambda x: x[1], reverse=True)
        # return the top 3 most similar nodes; [:3] syntax protects against empty list
        logging.info(f'Found {len(similar_nodes)} similar nodes for shortname: {shortname}')
        return similar_nodes[:3]

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
                return {}

        if longname:
            nodes = [node_data for node_data in self.nodes.values() if node_data.get('user',{}).get('longName',)==longname]
            if len(nodes) == 1:
                return nodes[0]
            else:
                logging.info(f'Number of nodes found matching this shortname was {len(nodes)}')
                return {}

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

    def get_nodes_from_db(self, time_limit=None):
        """
        Gets nodes from DB with optional lookback time filter applied.
        """

        logging.info(f'get_nodes_from_db has been called with: {time_limit} mins')

        if time_limit is not None:
            # get all packets in the last x minutes, then get the node info
            active_after = datetime.datetime.now() - datetime.timedelta(minutes=int(time_limit))
            node_nums = self._db_session.query(RXPacket.src_num).filter(RXPacket.ts >= active_after).distinct().all()
            nodelist_start = f"**Nodes seen in the last {time_limit} minutes:**\n"
            node_nums = [x[0] for x in node_nums]
            # get nodes from the node db
            nodes = self._db_session.query(MeshNodeDB).filter(MeshNodeDB.node_num.in_(node_nums)).all()
        else:
            node_nums = self._db_session.query(RXPacket.src_num).distinct().all()
            nodelist_start = f"**All Nodes in DB:**\n"
            nodes = self._db_session.query(MeshNodeDB).all()

        nodelist = []
        for node in nodes:
            if node.node_num != self.my_node_info.node_num: # ignore ourselves
                # add lastHeard via latest packet RX'd and its type
                recent_packet_for_node = self._db_session.query(RXPacket).filter(RXPacket.src_num == node.node_num).order_by(RXPacket.ts.desc()).first()
                hr_ago_24 = datetime.datetime.now() - datetime.timedelta(days=1)
                cnt_packets_24_hr = self._db_session.query(RXPacket.id).filter(RXPacket.src_num == node.node_num).filter(RXPacket.ts >= hr_ago_24).count()
                cnt_packets_from_node = self._db_session.query(RXPacket.id).filter(RXPacket.src_num == node.node_num).count()
                last_packet_str = ''
                if recent_packet_for_node:
                    last_packet_str = f'{recent_packet_for_node.portnum} at {util.time_str_from_dt(recent_packet_for_node.ts)}'
                    nodelist.append([f"\n {node.user_id} | {node.short_name} | {node.long_name} | Last Packet: {last_packet_str} | {cnt_packets_from_node} Total Packets ({cnt_packets_24_hr} in past day)", recent_packet_for_node.ts])
                else:
                    nodelist.append([f"\n {node.user_id} | {node.short_name} | {node.long_name} | No Packets in DB (Yet!)", datetime.datetime.fromtimestamp(0)])

        if len(nodelist) == 0:
            if time_limit is not None:
                nodelist_start = f'**No Nodes seen in the last {time_limit} minutes**'
            else:
                nodelist_start = f'**No Nodes exist in DB**'

        # sort nodelist and remove ts from it
        nodelist_sorted = sorted(nodelist, key=lambda x: x[1], reverse=True)
        nodelist_sorted = [x[0] for x in nodelist_sorted]
        nodelist_sorted.insert(0, nodelist_start)
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
            nodenum: Node num to DM.
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
            nodeid: Node ID to DM.
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
            shortname: shortname of Node to DM.
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

    def enqueue_send_dm(self, node, message, discord_interaction_info):
        """
        Puts a message on the queue to be sent to a specific node (DM).

        Args:
            node: Node to DM.
            message: Message text to send.
            discord_interaction_info: Information about discord message to fascilitate replies.
        """

        self._enqueue_msg(
            {
                'msg_type': f'send_dm',
                'node': node,
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
        
        try:
            self._db_session.commit() # save back to db
        except Exception as e:
            logging.error(f'DB ROLLBACK: {str(e)}')
            self._db_session.rollback()

    def _send_dm(self, nodenum, message, discord_interaction_info=None):
        logging.info(f'Sending message to: {nodenum}')
        sent_packet = self.iface.sendText(message, destinationId=nodenum, wantResponse=True, wantAck=True, onResponse=self.onMsgResponse)
        if sent_packet:
            pkt = TXPacket.from_sent_packet(sent_packet=sent_packet, discord_interaction_info=discord_interaction_info, mesh_client=self)
            node_desc = self.get_node_descriptive_string(nodenum=nodenum)
            self.discord_client.enqueue_tx_confirmation_dm(discord_interaction_info.message_id, node_desc)
            self._db_session.add(pkt)
            
            try:
                self._db_session.commit() # save back to db
            except Exception as e:
                logging.error(f'DB ROLLBACK: {str(e)}')
                self._db_session.rollback()

    def _send_telemetry(self, nodenum=None, discord_interaction_info=None):
        sent_packet = self.iface.sendTelemetry(wantResponse=True)
        # sent_packet = self.iface.sendTelemetry(nodenum, wantResponse=True)
        if sent_packet:
            self.discord_client.enqueue_tx_confirmation(discord_interaction_info.message_id)
            pkt = TXPacket.from_sent_packet(sent_packet=sent_packet, discord_interaction_info=discord_interaction_info, mesh_client=self)
            self._db_session.add(pkt)
            
            try:
                self._db_session.commit() # save back to db
            except Exception as e:
                logging.error(f'DB ROLLBACK: {str(e)}')
                self._db_session.rollback()

    # queue processing/background loop

    def process_queue_message(self, msg):
        if isinstance(msg, dict):
            msg_type = msg.get('msg_type')
            message = msg.get('message')
            discord_interaction_info = msg.get('discord_interaction_info')

            if msg_type == 'send_channel':
                channel = msg.get('channel')
                self._send_channel(channel, message, discord_interaction_info)

            elif msg_type == 'send_nodenum': # TODO This is no longer necessary with /dm
                nodenum = msg.get('nodenum')
                self._send_dm(nodenum, message, discord_interaction_info)
            elif msg_type == 'send_nodeid': # TODO This is no longer necessary with /dm
                nodeid = msg.get('nodeid')
                nodenum = self.get_node_num(node_id=nodeid)
                self._send_dm(nodenum, message, discord_interaction_info)
            elif msg_type == 'send_shortname': # TODO This is no longer necessary with /dm
                shortname = msg.get('shortname')
                nodenum = self.get_node_num(shortname=shortname)
                if nodenum:
                    self._send_dm(nodenum, message, discord_interaction_info)
                else:
                    # get list of possible shortnames
                    similar_nodes = self.get_similar_nodes(shortname)
                    if similar_nodes:
                        similar_nodes_str = ''
                        for node in similar_nodes:
                            similar_nodes_str += f'`{node[0]}`\n'
                        self.discord_client.enqueue_tx_error(discord_interaction_info.message_id, f'Node shortname: `{shortname}` is not found.\nDid you mean:\n{similar_nodes_str}')
                    else:
                        self.discord_client.enqueue_tx_error(discord_interaction_info.message_id, f'Node shortname: `{shortname}` is not found. Please check the spelling and try again.')

            elif msg_type == 'send_dm':
                node = msg.get('node')
                node_type, proc_node = self.determine_node_type(node)
                if node_type == 'shortname':
                    nodenum = self.get_node_num(shortname=proc_node)
                    if not nodenum:
                        # get list of possible shortnames
                        similar_nodes = self.get_similar_nodes(proc_node)
                        if similar_nodes:
                            similar_nodes_str = ''
                            for node in similar_nodes:
                                similar_nodes_str += f'`{node[0]}`\n'
                            self.discord_client.enqueue_tx_error(discord_interaction_info.message_id, f'Node shortname: `{proc_node}` is not found.\nDid you mean:\n{similar_nodes_str}')
                        else:
                            self.discord_client.enqueue_tx_error(discord_interaction_info.message_id, f'Node shortname: `{proc_node}` is not found. Please check the spelling and try again.')
                    else:
                        self._send_dm(nodenum, message, discord_interaction_info)
                elif node_type == 'nodenum':
                    self._send_dm(proc_node, message, discord_interaction_info)
                else:
                    error_str = f'Input `{node}` is an invalid node format.\nPlease use a shortname, node ID (starting with !), or node number.'
                    self.discord_client.enqueue_tx_error(discord_interaction_info.message_id, error_str)

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
            if msg_type == 'traceroute_nodeid':
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

