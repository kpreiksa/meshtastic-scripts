import asyncio
import json
import logging
import queue
import os
import sys
import time
from datetime import datetime
import discord
from discord import app_commands, ButtonStyle
from discord.ui import View, Button
import meshtastic
import meshtastic.ble_interface
import meshtastic.serial_interface
import meshtastic.tcp_interface
import pytz
from pubsub import pub

# TODO add try/except for Bleaker dbus error and for ble disconnection (heartbeat error?)

green_color = 0x67ea94  # Meshtastic Green
red_color = 0xed4245  # Red

# env var params - ie from docker
IS_DOCKER = os.environ.get('IS_DOCKER')
# other params?
log_file = 'meshtastic-discord-bot.log'
if IS_DOCKER:
    log_dir = 'config'
else:
    log_dir = '.'
    
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, log_file)),
        logging.StreamHandler()
    ]
)


def get_current_time_str():
    return datetime.now().strftime('%d %B %Y %I:%M:%S %p')


battery_warning = 15
nodelistq = queue.Queue(maxsize=20) # queue for /active command

class Config():
    
    class InterfaceInfo():
        def __init__(self, d):
            self._d = d
            
        @property
        def interface_type(self):
            self._d.get('method', 'serial')
            
        @property
        def interface_address(self):
            if self.interface_type == 'tcp':
                return self._d.get('address')
            else:
                print(f'WARNING: interface_address is invalid for interface_type: {self.interface_type}')
                return None
            
        @property
        def interface_port(self):
            if self.interface_type == 'tcp':
                return self._d.get('port')
            else:
                print(f'WARNING: interface_port is invalid for interface_type: {self.interface_type}')
                return None
            
        @property
        def interface_ble_node(self):
            if self.interface_type == 'ble':
                return self._d.get('ble_node')
            else:
                print(f'WARNING: interface_ble_node is invalid for interface_type: {self.interface_type}')
                return None     
    
    def __init__(self):
        self._config = self.load_config()
    
    def load_config(self):
        config = {}
        if os.path.exists("config.json"):
            try:
                logging.info(f'Found config.json, attempting to load configuration.')
                with open("config.json", "r") as config_file:
                    config = json.load(config_file)
                    config["channel_names"] = {int(k): v for k, v in config["channel_names"].items()}
                    return config
            except json.JSONDecodeError:
                logging.critical("config.json is not a valid JSON file.")
                raise
            except Exception as e:
                logging.critical(f"An unexpected error occurred while loading config.json: {e}")
                raise
        else:
            # Assume they are env vars
            logging.info(f'Unable to find config.json, looking at env vars for configuration')
            return self.load_env_vars()

    def load_env_vars(self):
        """Gets env variables and creates a config dict instead of using a json file input"""
        # variables:
        DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
        DISCORD_CHANNEL_ID = os.environ.get('DISCORD_CHANNEL_ID')
        TIME_ZONE = os.environ.get('TIME_ZONE')
        # Channels
        CHANNEL_0 = os.environ.get('CHANNEL_0', 'Primary') # required
        CHANNEL_1 = os.environ.get('CHANNEL_1')
        CHANNEL_2 = os.environ.get('CHANNEL_2')
        CHANNEL_3 = os.environ.get('CHANNEL_3')
        CHANNEL_4 = os.environ.get('CHANNEL_4')
        CHANNEL_5 = os.environ.get('CHANNEL_5')
        CHANNEL_6 = os.environ.get('CHANNEL_6')
        CHANNEL_7 = os.environ.get('CHANNEL_7')
        CHANNEL_8 = os.environ.get('CHANNEL_8')
        CHANNEL_9 = os.environ.get('CHANNEL_9')
        # interface info
        INTERFACE_METHOD = os.environ.get('INTERFACE_METHOD', 'serial')
        INTERFACE_ADDRESS = os.environ.get('INTERFACE_ADDRESS')
        INTERACE_PORT = os.environ.get('INTERACE_PORT', '4403')
        INTERACE_BLE_NODE = os.environ.get('INTERACE_BLE_NODE')

        required_vars = {
            'DISCORD_BOT_TOKEN': DISCORD_BOT_TOKEN,
            'DISCORD_CHANNEL_ID': DISCORD_CHANNEL_ID,
            'TIME_ZONE': TIME_ZONE,
        }
        missing_env_vars = []
        for var,value in required_vars.items():
            if value is None:
                missing_env_vars.append(var)
        if missing_env_vars:
            raise EnvironmentError(f'Missing required env vars: {missing_env_vars}')

        config = {
            'discord_bot_token': DISCORD_BOT_TOKEN,
            'discord_channel_id': DISCORD_CHANNEL_ID,
            'time_zone': TIME_ZONE,
            'is_docker': IS_DOCKER,
            'channel_names':
            {
                0: CHANNEL_0
            },
            'interface_info':
            {
                'method': INTERFACE_METHOD,
                'address': INTERFACE_ADDRESS,
                'port': INTERACE_PORT,
                'ble_node': INTERACE_BLE_NODE
            }
        }
        if CHANNEL_1 is not None:
            config['channel_names'][1] = CHANNEL_1
        if CHANNEL_2 is not None:
            config['channel_names'][2] = CHANNEL_2
        if CHANNEL_3 is not None:
            config['channel_names'][3] = CHANNEL_3
        if CHANNEL_4 is not None:
            config['channel_names'][4] = CHANNEL_4
        if CHANNEL_5 is not None:
            config['channel_names'][5] = CHANNEL_5
        if CHANNEL_6 is not None:
            config['channel_names'][6] = CHANNEL_6
        if CHANNEL_7 is not None:
            config['channel_names'][7] = CHANNEL_7
        if CHANNEL_8 is not None:
            config['channel_names'][8] = CHANNEL_8
        if CHANNEL_9 is not None:
            config['channel_names'][9] = CHANNEL_9

        return config
    
    @property
    def discord_bot_token(self):
        return self._config.get('discord_bot_token')
    
    @property
    def discord_channel_id(self):
        return self._config.get('discord_channel_id')
    
    @property
    def time_zone(self):
        return self._config.get('time_zone')
    
    @property
    def is_docker(self):
        return IS_DOCKER
    
    @property
    def channel_names(self):
        return self._config.get('channel_names', {})
    
    @property
    def interface_info(self):
        return Config.InterfaceInfo(self._config.get('interface_info', {}))


class NodeDBObj(): # sqlalchemy obj
    pass

    
class NodeObj():
    def __init__(self, node_dict):
        self._node_dict = node_dict
        
    @property
    def node_id(self):
        pass
    
    # nodenum
    
    # short_name
    
    # long_name
    
    def update_db(self):
        # write it to db if it doesn't exist... if it does, update it
        # based on criteria... i.e. newest wins
        pass
    
class MeshClient():
    def __init__(self):
        self._meshqueue = queue.Queue(maxsize=20)
        self._adminqueue = queue.Queue(maxsize=20)
        
        self.config = Config()
        
        self.iface = None
        
        self.nodes = {}
        self.myNodeInfo = None
        
        self.connect()
        
        self.discord_client = None
        
        onReceiveMesh = lambda x, y: self.onConnectionMesh(x, y)
        onConnectionMesh = lambda x, y: self.onConnectionMesh(x, y)
        onNodeUpdated = lambda x: self.onNodeUpdated(x)
        
        pub.subscribe(onReceiveMesh, "meshtastic.receive")
        pub.subscribe(onConnectionMesh, "meshtastic.connection.established")
        pub.subscribe(onNodeUpdated, "meshtastic.node.updated")
        
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
            
        myinfo = self.iface.getMyUser()
        shortname = myinfo.get('shortName','???')
        longname = myinfo.get('longName','???')
        nodes = self.iface.nodes # this should take precedence
        logging.info(f'Bot connected to Mesh node: {shortname} | {longname} with connection {interface_info.interface_type}')
        
    def link_discord(self, discord_client):
        self.discord_client = discord_client
        
    def get_long_name(self, node_id):
        if node_id in self.nodes:
            return self.nodes[node_id]['user'].get('longName', 'Unknown')
        return 'Unknown'

    def get_short_name(self, node_id):
        if node_id in self.nodes:
            return self.nodes[node_id]['user'].get('shortName', 'Unknown')
        return 'Unknown'
    
    def get_node_info_from_id(self, node_id):
        if not node_id.startswith('!'):
            node_id = '!' + node_id
        return self.nodes.get(node_id, {})

    def get_node_info_from_num(self, node_num):
        node_id = '!' + hex(node_num)[2:]
        return self.get_node_info_from_id(self, node_id)

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
                'msg_type': 'send_channel',
                'nodenum': nodenum,
                'message': message
            }
        )
        
    def enqueue_send_nodeid(self, nodeid, message):
        self.enqueue_msg(
            {
                'msg_type': 'send_channel',
                'nodeid': nodeid,
                'message': message
            }
        )
        
    def enqueue_send_shortname(self, shortname, message):
        self.enqueue_msg(
            {
                'msg_type': 'send_channel',
                'shortname': shortname,
                'message': message
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
        
    def process_queue_message(self, msg):
        if isinstance(msg, dict):
            msg_type = msg.get('msg_type')
            if msg_type == 'send_channel':
                channel = msg.get('channel')
                message = msg.get('message')
            elif msg_type == 'send_nodenum':
                nodenum = msg.get('nodenum')
                message = msg.get('message')
            elif msg_type == 'send_nodeid':
                nodeid = msg.get('nodeid')
                message = msg.get('message')
                nodenum = int(nodeid, 16)
            elif msg_type == 'send_shortname':
                shortname = msg.get('shortname')
                message = msg.get('message')
            else:
                pass
            
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
        self.nodes = self.iface.nodes
        self.myNodeInfo = self.iface.getMyNodeInfo()
        
        # do this stuff every time
        meshmessage = self._meshqueue.get_nowait()
        self.process_queue_message(meshmessage)
        self._meshqueue.task_done()
        
        adminmessage = self._adminqueue.get_nowait()
        self.process_admin_queue_message(adminmessage)
        self._meshqueue.task_done()
        
    def onConnectionMesh(self, interface, topic=pub.AUTO_TOPIC):
        logging.info(interface.myInfo)
        
    def onNodeUpdated(self, node):
        # this happens when a node gets updated... we should update the database
        logging.info(str(type(node)))
        logging.info(str(dir(node)))
        
    def onReceiveMesh(self, packet, interface):  # Called when a packet arrives from mesh.
        try:
            if packet['decoded']['portnum'] == 'TEXT_MESSAGE_APP':
                logging.info("Text message packet received") # For debugging.
                logging.info(f"Packet: {packet}") # Print the entire packet for debugging.

                # Check if 'channel' is present in the top-level packet.
                if 'channel' in packet:
                    mesh_channel_index = packet['channel']
                else:
                    # Check if 'channel' is present in the decoded packet.
                    if 'channel' in packet['decoded']:
                        mesh_channel_index = packet['decoded']['channel']
                    else:
                        mesh_channel_index = 0  # Default to channel 0 if not present.
                        logging.info("Channel not found in packet, defaulting to channel 0") # For debugging.

                mesh_channel_name = self.config.channel_names.get(mesh_channel_index, f"Unknown Channel ({mesh_channel_index})")

                current_time = get_current_time_str()

                from_long_name = self.get_long_name(packet['fromId'])
                from_short_name = self.get_short_name(packet['fromId'])
                to_long_name = self.get_long_name(packet['toId']) if packet['toId'] != '^all' else 'All Nodes'
                snr = packet.get('rxSnr', '?')
                rssi = packet.get('rxRssi', '?')
                hop_limit = packet.get('hopLimit') # remaining hops?
                hop_start = packet.get('hopStart') # starting number of hops?
                if hop_limit and hop_start:
                    hops = int(hop_start) - int(hop_limit)
                else:
                    hops = "?"
                    if not hop_start:
                        hop_start = "?"
                logging.info(f'From: {from_long_name}')

                embed = discord.Embed(title="Message Received", description=packet['decoded']['text'], color=green_color)
                embed.add_field(name="From Node", value=f"{packet['fromId']} | {from_short_name} | {from_long_name}", inline=False)
                embed.add_field(name="RxSNR / RxRSSI", value=f"{snr}dB / {rssi}dB", inline=True)
                embed.add_field(name="Hops", value=f"{hops} / {hop_start}", inline=True)
                embed.set_footer(text=f"{current_time}")

                if packet['toId'] == '^all':
                    embed.add_field(name="To Channel", value=mesh_channel_name, inline=True)
                else:
                    embed.add_field(name="To Node", value=f"{to_long_name} ({packet['toId']})", inline=True)

                logging.info(f'Putting Mesh Received message on Discord queue')
                if self.discord_client:
                    self.discord_client.enqueue_msg(embed)

        except KeyError as e:  # Catch empty packet.
            pass
        except Exception as e:  # Catch any other exceptions.
            logging.info(f"Unexpected error: {e}") # For debugging.
            pass
        

class HelpView(View):
    def __init__(self):
        super().__init__(timeout=None)

        # Create buttons
        self.add_item(Button(label="Kavitate", style=ButtonStyle.link, url="https://github.com/Kavitate"))
        self.add_item(Button(label="Meshtastic", style=ButtonStyle.link, url="https://meshtastic.org"))
        self.add_item(Button(label="Meshmap", style=ButtonStyle.link, url="https://meshmap.net"))
        self.add_item(Button(label="Python Meshtastic Docs", style=ButtonStyle.link, url="https://python.meshtastic.org/index.html"))


class DiscordBot(discord.Client):
    def __init__(self, mesh_client, *args, **kwargs):
        
        self.config = Config()
        self._discordqueue = queue.Queue(maxsize=20)
        
        self.mesh_client = mesh_client
        
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        # TODO maybe move the mesh parts into a separate class or dict to not possibly conflict with discord.Client super class
        self.channel = None
        self.dis_channel_id = self.config.discord_channel_id
        

    async def setup_hook(self) -> None:  # Create the background task and run it in the background.
        self.bg_task = self.loop.create_task(self.background_task())
        await self.tree.sync()

    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')

    def check_channel_id(self, other_channel_id):
        return other_channel_id == self.dis_channel_id
    
    def enqueue_msg(self, msg):
        self._discordqueue.put(msg)

    async def background_task(self):
        await self.wait_until_ready()
        counter = 0
        self.channel = self.get_channel(self.dis_channel_id)
        
        while not self.is_closed():
            # handle messages coming from mesh to discord
            try:
                meshmessage = self._discordqueue.get_nowait()
                if isinstance(meshmessage, discord.Embed):
                    await self.channel.send(embed=meshmessage)
                else:
                    await self.channel.send(meshmessage)
                self._discordqueue.task_done()
            except queue.Empty:
                pass
            
            counter += 1
            # Approximately 1 minute (every 12th call, call every 5 seconds) to refresh the node list.
            # save nodelist to self, so its available for pulling active nodes
            if (counter % 12 == 1):
                # node stuff?
                pass
            
            # process stuff on mesh side
            await self.mesh_client.background_process()
            
            await asyncio.sleep(5)


config = Config()
mesh_client = MeshClient()
discord_client = DiscordBot(mesh_client, intents=discord.Intents.default())
mesh_client.link_discord(discord_client)


@discord_client.tree.command(name="help", description="Shows the help message.")
async def help_command(interaction: discord.Interaction):

    # Check channel_id
    if interaction.channel_id != discord_client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /help Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{discord_client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        logging.info(f'/help command recieved')
        await interaction.response.defer(ephemeral=False)

        # Base help text
        help_text = ("**Command List**\n"
                    "`/send_shortname` - Send a message to another node.\n"
                    "`/sendid` - Send a message to another node.\n"
                    "`/sendnum` - Send a message to another node.\n"
                    "`/active` - Shows all active nodes. Default is 61\n"
                    "`/all_nodes` - Shows all nodes. WARNING: Potentially a lot of messages\n"
                    "`/help` - Shows this help message.\n"
                    "`/debug` - Shows information this bot's mesh node\n")

        # Dynamically add channel commands based on mesh_channel_names
        for mesh_channel_index, channel_name in config.channel_names.items():
            help_text += f"`/{channel_name.lower()}` - Send a message in the {channel_name} channel.\n"

        embed = discord.Embed(title="Meshtastic Bot Help", description=help_text, color=green_color)
        embed.set_footer(text="Meshtastic Discord Bot by Kavitate")
        ascii_art_image_url = "https://i.imgur.com/qvo2NkW.jpeg"
        embed.set_image(url=ascii_art_image_url)

        view = HelpView()
        await interaction.followup.send(embed=embed, view=view)

@discord_client.tree.command(name="sendid", description="Send a message to a specific node.")
async def sendid(interaction: discord.Interaction, nodeid: str, message: str):
    # Check channel_id
    if interaction.channel_id != discord_client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /sendid Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        logging.info(f'/sendid command received. ID: {nodeid}. Message: {message}. Attempting to send')
        try:
            # Strip the leading '!' if present
            if nodeid.startswith('!'):
                nodeid = nodeid[1:]
            
            current_time = get_current_time_str()
            
            # craft message
            embed = discord.Embed(title="Sending Message", description=message, color=green_color)
            embed.add_field(name="To Node:", value=f'!{nodeid} | {shortname} | {longname}', inline=True)  # Add '!' in front of nodeid
            embed.set_footer(text=f"{current_time}")
            
            # send message
            await interaction.response.send_message(embed=embed, ephemeral=False)
            mesh_client.enqueue_msg(
                {
                    'msg_type': 'send_nodeid',
                    'nodeid': nodeid,
                    'msg': message
                }
            )
        except ValueError as e:
            error_embed = discord.Embed(title="Error", description="Invalid hexadecimal node ID.", color=green_color)
            logging.info(f'/sendid command failed. Invalid hexadecimal node id. Error: {e}')
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

@discord_client.tree.command(name="sendnum", description="Send a message to a specific node.")
async def sendnum(interaction: discord.Interaction, nodenum: int, message: str):
    # Check channel_id
    if interaction.channel_id != discord_client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /sendnum Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{discord_client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        logging.info(f'/sendnum command received. NodeNum: {nodenum}. Sending message: {message}')
        
        # craft message
        current_time = get_current_time_str()
        embed = discord.Embed(title="Sending Message", description=message, color=green_color)
        embed.add_field(name="To Node:", value=f'{nodenum} | {node_id} | {shortname} | {longname}', inline=True)
        embed.set_footer(text=f"{current_time}")
        # send message
        await interaction.response.send_message(embed=embed)
        mesh_client.enqueue_msg(
            {
                'msg_type': 'send_nodenum',
                'nodenum': nodenum,
                'msg': message
                
            }
        )

@discord_client.tree.command(name="send_shortname", description="Send a message to a specific node.")
async def send_shortname(interaction: discord.Interaction, node_name: str, message: str):
    # Check channel_id
    if interaction.channel_id != discord_client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /send_shortname Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        logging.info(f'/send_shortname command received. nodeName: {node_name}. Sending message: {message}')

        current_time = get_current_time_str()
        
        node = mesh_client.get_node_info_from_shortname(node_name)
        
        if isinstance(node, dict):

            # craft message
            embed = discord.Embed(title="Sending Message", description=message, color=green_color)
            embed.add_field(name="To Node:", value=f'{node_id} | {shortname} | {longname}', inline=True)
            embed.set_footer(text=f"{current_time}")
            # send message
            await interaction.response.send_message(embed=embed)
            mesh_client.enqueue_msg(
            {
                'msg_type': 'send_shortname',
                'shortname': node_name,
                'msg': message
            }
        )
        elif isinstance(node, int):
            # if node is an int, there was an error, send an error message
            if node == 0:
                embed = discord.Embed(title="Could not send message", description=f'Unable to find node with short name: {node_name}.\nMessage not sent.')
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(title="Could not send message", description=f'Found too many nodes named {node_name}. Nodes found: {node}.\nMessage not sent.')
                await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title="Could not send message", description=f"Unknown error, couldn't send the message")
            await interaction.response.send_message(embed=embed)
            # don't put anything on discordtomesh

# Dynamically create commands based on mesh_channel_names
for mesh_channel_index, mesh_channel_name in config.channel_names.items():
    @discord_client.tree.command(name=mesh_channel_name.lower(), description=f"Send a message in the {mesh_channel_name} channel.")
    async def send_channel_message(interaction: discord.Interaction, message: str, mesh_channel_index: int = mesh_channel_index):
        # Check channel_id
        if interaction.channel_id != discord_client.dis_channel_id:
            # post rejection
            logging.info(f'Rejected /<channel> Command - Sent on wrong discord channel')
            embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{discord_client.dis_channel_id}>')
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            logging.info(f'/{mesh_channel_name} command received. Sending message: {message}')
            current_time = get_current_time_str()
            
            embed = discord.Embed(title=f"Sending Message to {config.channel_names[mesh_channel_index]}:", description=message, color=green_color)
            embed.set_footer(text=f"{current_time}")
            
            await interaction.response.send_message(embed=embed)
            mesh_client.enqueue_msg(
                {
                    'msg_type': 'send_channel',
                    'channel': mesh_channel_index,
                    'msg': message
                }
                
            )

@discord_client.tree.command(name="active", description="Lists all active nodes.")
async def active(interaction: discord.Interaction, active_time: str='61'):
    # Check channel_id
    if interaction.channel_id != discord_client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /active Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{discord_client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.defer()

        logging.info(f'/active received, sending to queue with time: {active_time}')
        mesh_client.enqueue_admin_msg(
            {
                'msg_type': 'active_nodes',
                'active_time': active_time
            }
        )
        await asyncio.sleep(1)

        await interaction.delete_original_response()

@discord_client.tree.command(name="all_nodes", description="Lists all nodes.")
async def all_nodes(interaction: discord.Interaction):
    # Check channel_id
    if interaction.channel_id != discord_client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /all_nodes Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{discord_client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.defer()

        logging.info(f'/all_node received, sending to queue with value: True')
        mesh_client.enqueue_admin_msg(
            {
                'msg_type': 'all_nodes'
            }
        )
        await asyncio.sleep(1)

        await interaction.delete_original_response()

@discord_client.tree.command(name="debug", description="Gives debug info to the user")
async def debug(interaction: discord.Interaction):
    # Check channel_id
    if interaction.channel_id != discord_client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /debug Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{discord_client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        # do this command differently, just do all the logic here instead of using a queue
        logging.info(f'/debug received, printing debug info')

        # calculate last heard
        lastheard = discord_client.myNodeInfo.get('lastHeard')
        if lastheard: # ignore if doesn't have lastHeard property
            ts = int(lastheard)
            # if ts > time.time() - (time_limit * 60): # Only include if its less then time_limit
            timezone = pytz.timezone(config.time_zone)
            local_time = datetime.fromtimestamp(ts, tz=pytz.utc).astimezone(timezone)
            timestr = local_time.strftime('%d %B %Y %I:%M:%S %p')
        else:
            timestr = '???'

        debug_text = f"```lastHeard: {timestr}\n"
        for thing in ['user', 'deviceMetrics','localStats']:
            debug_text += f'{thing} items:\n'
            for key, value in discord_client.myNodeInfo.get(thing,{}).items():
                debug_text += f"  {key}: {value}\n"
        debug_text += '```'

        embed = discord.Embed(title='Debug Information', description=debug_text)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Dump nodes info to json file in log dir
        my_node_dump = os.path.join(log_dir, 'my_node_dump.json')
        try:
            default = lambda o: f'<<not serializable data: {type(o).__qualname__}>>'
            with open(my_node_dump, 'w', encoding='utf-8', errors='ignore') as f:
                json.dump(discord_client.myNodeInfo, f, indent=4, default=default)
            logging.info(f'Wrote my node info to {my_node_dump}')
        except Exception as e:
            logging.info(f'Error trying to dump my node info. \nError: {e}\n')

        # Dump nodes info to json file in log dir
        nodes_dump = os.path.join(log_dir, 'nodes_dump.json')
        try:
            default = lambda o: f'<<not serializable data: {type(o).__qualname__}>>'
            with open(nodes_dump, 'w', encoding='utf-8', errors='ignore') as f:
                json.dump(discord_client.nodes, f, indent=4, default=default)
            logging.info(f'Wrote nodes info to {nodes_dump}')
        except Exception as e:
            logging.info(f'Error trying to dump all nodes. \nError: {e}\n')

        await asyncio.sleep(1)


def run_discord_bot():
    try:
        # TODO could do ble connection BEFORE doing .run
        # could also add logic into __init__
        discord_client.run(config.discord_bot_token)
    except Exception as e:
        logging.error(f"An error occurred while running the bot: {e}")
    finally:
        if discord_client:
            asyncio.run(discord_client.close())

if __name__ == "__main__":
    run_discord_bot()
