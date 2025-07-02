import asyncio
import json
import logging
import queue
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

def load_config():
    try:
        with open("config.json", "r") as config_file:
            config = json.load(config_file)
            config["channel_names"] = {int(k): v for k, v in config["channel_names"].items()}
            return config
    except FileNotFoundError:
        logging.critical("The config.json file was not found.")
        raise
    except json.JSONDecodeError:
        logging.critical("config.json is not a valid JSON file.")
        raise
    except Exception as e:
        logging.critical(f"An unexpected error occurred while loading config.json: {e}")
        raise

config = load_config()

color = 0x67ea94  # Meshtastic Green
red_color = 0xed4245

token = config["discord_bot_token"]
dis_channel_id = int(config["discord_channel_id"])
mesh_channel_names = config["channel_names"]
time_zone = config["time_zone"]
interface_info = config.get("interface_info", {})
interface_type = interface_info.get("method", "serial")

meshtodiscord = queue.Queue(maxsize=20) # queue for sending info to discord (when message received on mesh, process then throw in this queue for discord)
discordtomesh = queue.Queue(maxsize=20) # queue for all send-message types (sendid, sendnum or to a specific channel)
nodelistq = queue.Queue(maxsize=20) # queue for /active command

battery_warning = 15

def onConnectionMesh(interface, topic=pub.AUTO_TOPIC):
    logging.info(interface.myInfo) # TODO log more info about my node here

def get_long_name(node_id, nodes):
    if node_id in nodes:
        return nodes[node_id]['user'].get('longName', 'Unknown')
    return 'Unknown'

def onReceiveMesh(packet, interface):  # Called when a packet arrives from mesh.
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

            mesh_channel_name = mesh_channel_names.get(mesh_channel_index, f"Unknown Channel ({mesh_channel_index})")

            current_time = datetime.now().strftime('%d %B %Y %I:%M:%S %p')

            nodes = interface.nodes
            from_long_name = get_long_name(packet['fromId'], nodes)
            to_long_name = get_long_name(packet['toId'], nodes) if packet['toId'] != '^all' else 'All Nodes'
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

            embed = discord.Embed(title="Message Received", description=packet['decoded']['text'], color=0x67ea94)
            embed.add_field(name="From Node", value=f"{from_long_name} ({packet['fromId']})", inline=True)
            embed.add_field(name="RxSNR / RxRSSI", value=f"{snr}dB / {rssi}dB", inline=True)
            embed.add_field(name="Hops", value=f"{hops} / {hop_start}", inline=True)
            embed.set_footer(text=f"{current_time}")

            if packet['toId'] == '^all':
                embed.add_field(name="To Channel", value=mesh_channel_name, inline=True)
            else:
                embed.add_field(name="To Node", value=f"{to_long_name} ({packet['toId']})", inline=True)

            logging.info(f'Putting Mesh Received message on Discord queue')
            meshtodiscord.put(embed)

    except KeyError as e:  # Catch empty packet.
        pass
    except Exception as e:  # Catch any other exceptions.
        logging.info(f"Unexpected error: {e}") # For debugging.
        pass

class MeshBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.iface = None  # Initialize iface as None.
        self.nodes = {}  # Init nodes list as empty dict
        self.battery_warning_sent = False # only send battery warning once
        self.node_id_map = {}  # offline node map from id (hex) to everything else
        self.channel = None
        self.dis_channel_id = dis_channel_id

    async def setup_hook(self) -> None:  # Create the background task and run it in the background.
        self.bg_task = self.loop.create_task(self.background_task())
        await self.tree.sync()

    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')

# TODO add debuging function that dumps self.nodes into a json file on a hidden command?

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

    def check_channel_id(self, other_channel_id):
        return other_channel_id == self.dis_channel_id

    def get_active_nodes(self, time_limit=15): # must NOT be async or printing info takes forever (or never happens?)
        # If time_limit is True, gets all nodes - BIG print
        if time_limit == True:
            logging.info(f'get_active_nodes has been called with: True (all nodes)')
        else:
            logging.info(f'get_active_nodes has been called with: {time_limit} mins')

        # use self.nodes that was pulled 1m ago
        nodelist = []

        if time_limit == True:
            # return ALL nodes
            nodelist_start = f"**All Nodes Seen:**\n"
        else:
            # don't return all nodes, only active, and convert str:time_limit into int
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
                    timezone = pytz.timezone(time_zone)
                    local_time = datetime.fromtimestamp(ts, tz=pytz.utc).astimezone(timezone)
                    timestr = local_time.strftime('%d %B %Y %I:%M:%S %p')
                else:
                    timestr = '???'
                    ts = 0

                if time_limit == True:
                    # list all nodes
                    nodelist.append([f"\n {id} | {shortname} | {longname} | **Hops:** {hopsaway} | **SNR:** {snr} | **Last Heard:** {timestr}",ts])
                else:
                    # check if they are greater then the time limit
                    if ts > time.time() - (time_limit * 60):
                        nodelist.append([f"\n {id} | {shortname} | {longname} | **Hops:** {hopsaway} | **SNR:** {snr} | **Last Heard:** {timestr}",ts])

            except KeyError as e:
                logging.error(e)
                pass

        if len(nodelist) == 0 and time_limit != True:
            # no nodes found, change response
            nodelist_start = f'**No Nodes seen in the last {time_limit} minutes**'
        # sort nodelist and remove ts from it
        nodelist_sorted = sorted(nodelist, key=lambda x: x[1], reverse=True)
        nodelist_sorted = [x[0] for x in nodelist_sorted]
        nodelist_sorted.insert(0, nodelist_start)


        # Split node list into chunks of 10 rows.
        nodelist_chunks = ["".join(nodelist_sorted[i:i + 10]) for i in range(0, len(nodelist_sorted), 10)]
        return nodelist_chunks

    async def check_battery(self, channel, battery_warning=battery_warning):
        # runs every minute, not eff but idk what else to do

        myNodeInfo = self.iface.getMyNodeInfo()
        shortname = myNodeInfo.get('user',{}).get('shortName','???')
        longname = myNodeInfo.get('user',{}).get('longName','???')
        battery_level = myNodeInfo.get('deviceMetrics',{}).get('batteryLevel',100)
        if battery_level > battery_warning:
            self.battery_warning_sent = False
        elif self.battery_warning_sent is False:
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
            await channel.send(embed=embed)

    async def background_task(self):
        await self.wait_until_ready()
        counter = 0
        self.channel = self.get_channel(self.dis_channel_id)
        pub.subscribe(onReceiveMesh, "meshtastic.receive")
        pub.subscribe(onConnectionMesh, "meshtastic.connection.established")
        logging.info(f'Connecting with interface: {interface_type}')
        if interface_type == 'serial':
            try:
                self.iface = meshtastic.serial_interface.SerialInterface()
            except Exception as ex:
                logging.info(f"Error: Could not connect {ex}")
                sys.exit(1)
        elif interface_type == 'tcp':
            addr = interface_info.get("address") # TODO Add in port option
            if not addr:
                logging.info(f'interface.address required for tcp connection')
            try:
                self.iface = meshtastic.tcp_interface.TCPInterface(addr)
            except Exception as ex:
                logging.info(f"Error: Could not connect {ex}")
                sys.exit(1)
        elif interface_type == 'ble':
            try:
                ble_node = interface_info.get("ble_node")
                self.iface = meshtastic.ble_interface.BLEInterface(address=ble_node)
            except Exception as ex:
                logging.info(f'Error: Could not connect {ex}')
                sys.exit(1)
        else:
            logging.info(f'Unsupported interface: {interface_type}')

        myinfo = self.iface.getMyUser()
        shortname = myinfo.get('shortName','???')
        longname = myinfo.get('longName','???')
        logging.info(f'Bot connected to Mesh node: {shortname} | {longname} with connection {interface_type}')

        while not self.is_closed():
            counter += 1
            # Approximately 1 minute (every 12th call, call every 5 seconds) to refresh the node list.
            # save nodelist to self, so its available for pulling active nodes
            if (counter % 12 == 1):
                self.nodes = self.iface.nodes

            try:
                meshmessage = meshtodiscord.get_nowait()
                if isinstance(meshmessage, discord.Embed):
                    await self.channel.send(embed=meshmessage)
                else:
                    await self.channel.send(meshmessage)
                meshtodiscord.task_done()
            except queue.Empty:
                pass
            try:
                meshmessage = discordtomesh.get_nowait()
                if meshmessage.startswith('channel='):
                    mesh_channel_index = int(meshmessage[8:meshmessage.find(' ')])
                    message = meshmessage[meshmessage.find(' ') + 1:]
                    self.iface.sendText(message, channelIndex=mesh_channel_index)
                elif meshmessage.startswith('nodenum='):
                    nodenum = int(meshmessage[8:meshmessage.find(' ')])
                    message = meshmessage[meshmessage.find(' ') + 1:]
                    # message = f'{message}\n-bot'
                    self.iface.sendText(message, destinationId=nodenum)
                else:
                    self.iface.sendText(meshmessage)
                discordtomesh.task_done()
            except:
                pass
            try:
                active_time = nodelistq.get_nowait()
                nodelist_chunks = self.get_active_nodes(active_time)
                # Sends node list if there are any.
                for chunk in nodelist_chunks:
                    await self.channel.send(chunk)
                nodelistq.task_done()
            except queue.Empty:
                pass
            try:
                await self.check_battery(self.channel)
            except:
                pass
            await asyncio.sleep(5)

class HelpView(View):
    def __init__(self):
        super().__init__(timeout=None)

        # Create buttons
        self.add_item(Button(label="Kavitate", style=ButtonStyle.link, url="https://github.com/Kavitate"))
        self.add_item(Button(label="Meshtastic", style=ButtonStyle.link, url="https://meshtastic.org"))
        self.add_item(Button(label="Meshmap", style=ButtonStyle.link, url="https://meshmap.net"))
        self.add_item(Button(label="Python Meshtastic Docs", style=ButtonStyle.link, url="https://python.meshtastic.org/index.html"))

client = MeshBot(intents=discord.Intents.default())

@client.tree.command(name="help", description="Shows the help message.")
async def help_command(interaction: discord.Interaction):

    # Check channel_id
    if interaction.channel_id != client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /help Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{client.dis_channel_id}>')
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
                    "`/help` - Shows this help message.\n")

        # Dynamically add channel commands based on mesh_channel_names
        for mesh_channel_index, channel_name in mesh_channel_names.items():
            help_text += f"`/{channel_name.lower()}` - Send a message in the {channel_name} channel.\n"

        color = 0x67ea94

        embed = discord.Embed(title="Meshtastic Bot Help", description=help_text, color=color)
        embed.set_footer(text="Meshtastic Discord Bot by Kavitate")
        ascii_art_image_url = "https://i.imgur.com/qvo2NkW.jpeg"
        embed.set_image(url=ascii_art_image_url)

        view = HelpView()
        await interaction.followup.send(embed=embed, view=view)

@client.tree.command(name="sendid", description="Send a message to a specific node.")
async def sendid(interaction: discord.Interaction, nodeid: str, message: str):
    # Check channel_id
    if interaction.channel_id != client.dis_channel_id:
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
            # get additional node info
            node = client.get_node_info_from_id(nodeid)
            shortname = node.get('user',{}).get('shortName','???')
            longname = node.get('user',{}).get('longName','???')

            # Convert hexadecimal node ID to decimal
            nodenum = int(nodeid, 16)
            current_time = datetime.now().strftime('%d %B %Y %I:%M:%S %p')
            # craft message
            embed = discord.Embed(title="Sending Message", description=message, color=0x67ea94)
            embed.add_field(name="To Node:", value=f'!{nodeid} | {shortname} | {longname}', inline=True)  # Add '!' in front of nodeid
            embed.set_footer(text=f"{current_time}")
            # send message
            await interaction.response.send_message(embed=embed, ephemeral=False)
            discordtomesh.put(f"nodenum={nodenum} {message}")
        except ValueError as e:
            error_embed = discord.Embed(title="Error", description="Invalid hexadecimal node ID.", color=0x67ea94)
            logging.info(f'/sendid command failed. Invalid hexadecimal node id. Error: {e}')
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

@client.tree.command(name="sendnum", description="Send a message to a specific node.")
async def sendnum(interaction: discord.Interaction, nodenum: int, message: str):
    # Check channel_id
    if interaction.channel_id != client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /sendnum Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        logging.info(f'/sendnum command received. NodeNum: {nodenum}. Sending message: {message}')
        # get additional node info
        node = client.get_node_info_from_num(nodenum)
        shortname = node.get('user',{}).get('shortName','???')
        longname = node.get('user',{}).get('longName','???')
        node_id = node.get('user',{}).get('id','???')
        # craft message
        current_time = datetime.now().strftime('%d %B %Y %I:%M:%S %p')
        embed = discord.Embed(title="Sending Message", description=message, color=0x67ea94)
        embed.add_field(name="To Node:", value=f'{nodenum} | {node_id} | {shortname} | {longname}', inline=True)
        embed.set_footer(text=f"{current_time}")
        # send message
        await interaction.response.send_message(embed=embed)
        discordtomesh.put(f"nodenum={nodenum} {message}")

@client.tree.command(name="send_shortname", description="Send a message to a specific node.")
async def send_shortname(interaction: discord.Interaction, node_name: str, message: str):
    # Check channel_id
    if interaction.channel_id != client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /send_shortname Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        logging.info(f'/send_shortname command received. nodeName: {node_name}. Sending message: {message}')

        current_time = datetime.now().strftime('%d %B %Y %I:%M:%S %p')
        node = client.get_node_info_from_shortname(node_name)
        if isinstance(node, dict):
            # get additional node info
            shortname = node.get('user',{}).get('shortName','???')
            longname = node.get('user',{}).get('longName','???')
            node_id = node.get('user',{}).get('id','???')
            nodenum = node.get('num')
            # craft message
            embed = discord.Embed(title="Sending Message", description=message, color=0x67ea94)
            embed.add_field(name="To Node:", value=f'{node_id} | {shortname} | {longname}', inline=True)
            embed.set_footer(text=f"{current_time}")
            # send message
            await interaction.response.send_message(embed=embed)
            discordtomesh.put(f"nodenum={nodenum} {message}")
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
for mesh_channel_index, mesh_channel_name in mesh_channel_names.items():
    @client.tree.command(name=mesh_channel_name.lower(), description=f"Send a message in the {mesh_channel_name} channel.")
    async def send_channel_message(interaction: discord.Interaction, message: str, mesh_channel_index: int = mesh_channel_index):
        # Check channel_id
        if interaction.channel_id != client.dis_channel_id:
            # post rejection
            logging.info(f'Rejected /<channel> Command - Sent on wrong discord channel')
            embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{client.dis_channel_id}>')
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            logging.info(f'/{mesh_channel_name} command received. Sending message: {message}')
            current_time = datetime.now().strftime('%d %B %Y %I:%M:%S %p')
            embed = discord.Embed(title=f"Sending Message to {mesh_channel_names[mesh_channel_index]}:", description=message, color=0x67ea94)
            embed.set_footer(text=f"{current_time}")
            await interaction.response.send_message(embed=embed)
            discordtomesh.put(f"channel={mesh_channel_index} {message}")

@client.tree.command(name="active", description="Lists all active nodes.")
async def active(interaction: discord.Interaction, active_time: str='61'):
    # Check channel_id
    if interaction.channel_id != client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /active Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.defer()

        logging.info(f'/active received, sending to queue with time: {active_time}')
        nodelistq.put(active_time) # sets queue to the time, background task then executes - this should prob be changed

        await asyncio.sleep(1)

        await interaction.delete_original_response()

@client.tree.command(name="all_nodes", description="Lists all nodes.")
async def all_nodes(interaction: discord.Interaction):
    # Check channel_id
    if interaction.channel_id != client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /all_nodes Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.defer()

        logging.info(f'/all_node received, sending to queue with value: True')
        nodelistq.put(True) # sets queue to true, background task then executes - this should prob be changed

        await asyncio.sleep(1)

        await interaction.delete_original_response()

def run_discord_bot():
    try:
        client.run(token)
    except Exception as e:
        logging.error(f"An error occurred while running the bot: {e}")
    finally:
        if client:
            asyncio.run(client.close())

if __name__ == "__main__":
    run_discord_bot()
