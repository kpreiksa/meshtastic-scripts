import asyncio
from version import __version__
import json
import logging
import os
import aiohttp
import datetime
import discord
from discord import ButtonStyle
from discord.ui import View, Button
import pytz
from pprint import pprint
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import db_base
import db_classes
from functools import wraps
from config_classes import Config
from mesh_client import MeshClient
from discord_client import DiscordBot
from util import get_current_time_str, uptime_str, time_from_ts, time_str_from_dt, get_current_time_discord_str, convert_secs_to_pretty
from util import MeshBotColors, DiscordInteractionInfo, embed_field, get_discord_ts_from_dt
import time

# other params?
log_file = 'meshtastic-discord-bot.log'

# env var params - ie from docker, default is discord-bot/logs or discord-bot/db
log_dir = os.environ.get('LOG_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)),'logs'))
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
db_dir = os.environ.get('DB_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)),'db'))
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, log_file), encoding="utf-8"),
        logging.StreamHandler()
    ]
)

class HelpView(View):
    def __init__(self):
        super().__init__(timeout=None)

        # Create buttons
        self.add_item(Button(label="Original Bot", style=ButtonStyle.link, url="https://github.com/Kavitate"))
        self.add_item(Button(label="Preiksa Meshtastic", style=ButtonStyle.link, url="https://github.com/kpreiksa/meshtastic-scripts"))
        self.add_item(Button(label="Meshtastic", style=ButtonStyle.link, url="https://meshtastic.org"))
        self.add_item(Button(label="Meshmap", style=ButtonStyle.link, url="https://meshmap.net"))
        self.add_item(Button(label="Python Meshtastic Docs", style=ButtonStyle.link, url="https://python.meshtastic.org/index.html"))

config = Config()
db_info = config.database_info

# Setup database connection using DatabaseClient
from db_client import DatabaseClient
db_client = DatabaseClient(db_info._db_connection_string)
session = db_client.get_session()

# Create the mesh client and discord client
mesh_client = MeshClient(db_session=session, db_client=db_client, config=config) # create the mesh client but do not connect yet
discord_client = DiscordBot(mesh_client, config, intents=discord.Intents.default())

# discord commands
@discord_client.tree.command(name="help", description="Shows the help message.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def help_command(interaction: discord.Interaction):
    logging.info(f'/help command recieved')
    await interaction.response.defer(ephemeral=False)

    # Base help text
    help_text = ("**Command List**\n"
                "`/dm` - Send a message to another node - input a shortname, node id (hex, starting with !) or node num (dec).\n"
                "`/active` - Shows all active nodes. Default is 61\n"
                "`/all_nodes` - Shows all nodes. WARNING: Potentially a lot of messages\n"
                "`/nodeinfo` - Get detailed nodeinfo from DB for node.\n"
                "`/help` - Shows this help message.\n"
                "`/debug` - Shows information this bot's mesh node\n"
                "`/ham` - Look up callsign for ham operator\n"
                "`/map` - Shows map with marker for specific node\n"
                "`/reconnect` - Force reconnection to the mesh network\n")

    # Dynamically add channel commands based on mesh_channel_names
    for mesh_channel_index, channel_name in config.channel_names.items():
        help_text += f"`/{channel_name.lower()}` - Send a message in the {channel_name} channel.\n"

    embed = discord.Embed(title="Meshtastic Bot Help", description=help_text, color=MeshBotColors.green())
    embed.set_footer(text="Meshtastic Discord Bot by Kavitate")
    ascii_art_image_url = "https://i.imgur.com/qvo2NkW.jpeg"
    embed.set_image(url=ascii_art_image_url)

    view = HelpView()
    await interaction.followup.send(embed=embed, view=view)

@discord_client.tree.command(name="sendid", description="Send a message to a specific node.")
@discord_client.deprecated_command('This command is deprecated, use /dm instead: /dm <node> <message>')
async def sendid(interaction: discord.Interaction, nodeid: str, message: str):
    logging.info(f'/sendid command received. Deprecated')

@discord_client.tree.command(name="sendnum", description="Send a message to a specific node.")
@discord_client.deprecated_command('This command is deprecated, use /dm instead: /dm <node> <message>')
async def sendnum(interaction: discord.Interaction, nodenum: int, message: str):
    logging.info(f'/sendnum command received. Deprecated')

@discord_client.tree.command(name="send_shortname", description="Send a message to a specific node.")
@discord_client.deprecated_command(f'This command is deprecated, use /dm instead: /dm <node> <message>')
async def send_shortname(interaction: discord.Interaction, node_name: str, message: str):
    logging.info(f'/send_shortname command received. Deprecated')

@discord_client.tree.command(name="dm", description="Send a message to a specific node.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def dm(interaction: discord.Interaction, node: str, message: str):
    logging.info(f'/dm command received. Node Input: {node}. Sending message: {message}')

    current_time = get_current_time_str()

    # craft message
    embed = discord.Embed(title="Sending Message", description=message, color=MeshBotColors.TX_PENDING())
    embed.add_field(name="To Node", value=f'{node}', inline=False)
    embed.add_field(name='TX State', value='Pending', inline=False)
    embed.set_footer(text=f"{current_time}")
    # send message to discord
    out = await interaction.response.send_message(embed=embed)

    # queue message to be sent on mesh
    discord_interaction_info = DiscordInteractionInfo(interaction.guild_id, interaction.channel_id, out.message_id)
    mesh_client.enqueue_send_dm(node, message, discord_interaction_info)

# Dynamically create commands based on mesh_channel_names
for mesh_channel_index, mesh_channel_name in config.channel_names.items():
    @discord_client.tree.command(name=mesh_channel_name.lower(), description=f"Send a message in the {mesh_channel_name} channel.")
    @discord_client.only_in_channel(discord_client.dis_channel_id)
    async def send_channel_message(interaction: discord.Interaction, message: str, mesh_channel_index: int = mesh_channel_index):
        logging.info(f'/{interaction.command.name} command received. Sending message: {message}')
        current_time = get_current_time_str()

        embed = discord.Embed(title=f"Sending Message", description=message, color=MeshBotColors.TX_PENDING())
        embed.add_field(name="To Channel", value=config.channel_names[mesh_channel_index], inline=False)
        embed.add_field(name='TX State', value='Pending', inline=False)
        embed.set_footer(text=f"{current_time}")

        out = await interaction.response.send_message(embed=embed)

        discord_interaction_info = DiscordInteractionInfo(interaction.guild_id, interaction.channel_id, out.message_id, interaction.user.id, interaction.user.display_name, interaction.user.global_name, interaction.user.name, interaction.user.mention)
        mesh_client.enqueue_send_channel(mesh_channel_index, message, discord_interaction_info=discord_interaction_info)


# @discord_client.tree.command(name="traceroute", description="Traceroute a node.")
# @discord_client.only_in_channel(discord_client.dis_channel_id)
# async def run_traceroute(interaction: discord.Interaction, node_id: str):
#     await interaction.response.defer()

#     logging.info(f'/traceroute received.')
#     mesh_client.enqueue_traceroute(node_id)
#     await asyncio.sleep(0.1)

#     await interaction.delete_original_response()

@discord_client.tree.command(name="active", description="Lists all active nodes.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def active(interaction: discord.Interaction, active_time: str='61'):
    # await interaction.response.defer()

    logging.info(f'/active received, sending to queue with time: {active_time}')

    await asyncio.sleep(0.1)

    embed = discord.Embed(title="Active Nodes", description=f"Listing all active nodes for the last {active_time} minutes.", color=MeshBotColors.green())
    embed.add_field(name='Request Info', value=f"Requested by {interaction.user.mention} at {get_current_time_discord_str()}")

    # Send first message
    out = await interaction.response.send_message(embed=embed)

    tic = time.time()
    # Get message to reference later
    msg_id = out.message_id
    message = await discord_client.channel.fetch_message(msg_id)

    thread = await message.create_thread(name='/active cmd', auto_archive_duration=60)
    chunks = mesh_client.get_nodes_from_db(time_limit=active_time)
    thread_id = thread.id

    if len(chunks) == 0:
        final_text = f'No nodes seen in the last {active_time} minutes.'
    elif active_time:
        final_text = f'Finished listing active nodes for the last {active_time} minutes.'
    else:
        final_text = None

    final_msg = discord.Embed(
        title='End Thread',
        description=final_text,
        color=MeshBotColors.white()
    )

    toc = time.time() - tic
    original_msg_field = embed_field(name="Processing Time", value=f'Took {convert_secs_to_pretty(toc)}', inline=False)
    original_msg_id = out.message_id
    original_message_edit = None # None means add, 1 means replace first field

    packet = {
        'content': chunks,
        'thread_id': thread_id,
        'final_msg': final_msg,
        'original_msg_field': original_msg_field,
        'original_msg_id': original_msg_id,
        'original_message_edit': original_message_edit
    }
    logging.info(f'Got nodes, formatted data, sending to enqueue_msg_thread. Total of {len(chunks)} chunks (of up to 10).')
    discord_client.enqueue_msg_thread(packet)

@discord_client.tree.command(name="nodeinfo", description="Gets info for a node from the database")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def nodeinfo(interaction: discord.Interaction, node_id: str):

    logging.info(f'/nodeinfo received, doing query for node ID: {node_id}')
    current_time = get_current_time_str()

    await interaction.response.defer()

    embeds = []

    n = mesh_client.get_node_num(node_id=node_id)

    # convert id to num to look up node
    matching_nodes = mesh_client._db_session.query(db_classes.MeshNodeDB).filter(db_classes.MeshNodeDB.node_num == n).filter(db_classes.MeshNodeDB.publisher_mesh_node_num == mesh_client.my_node_info.node_num_str).all()
    if len(matching_nodes) > 1:
        error_embed = discord.Embed(title=f"Error", description=f'More than 1 node matching ID: {node_id}', color=MeshBotColors.error())
        embeds.append(error_embed)
    elif len(matching_nodes) == 0:
        error_embed = discord.Embed(title=f"Error", description=f'No node matching ID: {node_id}', color=MeshBotColors.error())
        embeds.append(error_embed)
    else:
        matching_node = matching_nodes[0]
        matching_packets = mesh_client._db_session.query(db_classes.RXPacket).filter(db_classes.RXPacket.src_num == matching_node.node_num).filter(db_classes.RXPacket.publisher_mesh_node_num == mesh_client.my_node_info.node_num_str).order_by(db_classes.RXPacket.ts.desc()).all()
        portnums = list(set([x.portnum for x in matching_packets]))

        ni_embed = discord.Embed(title=f"Node Info", description=f'From DB for Node: {node_id}', color=MeshBotColors.violet())
        ni_embed.add_field(name='Node ID/Name', value=matching_node.descriptive_name, inline=False)

        # get first packet
        first_matching_packet = matching_packets[0]
        first_packet_type = first_matching_packet.portnum
        first_packet_discord_ts = get_discord_ts_from_dt(first_matching_packet.ts)
        ni_embed.add_field(name="Last Packet", value=f'{first_packet_type}\nReceived at: {first_packet_discord_ts}', inline=False)

        ni_embed.add_field(name="Cnt Packets RX'd", value=f'{len(matching_packets)}', inline=False)

        for portnum in portnums:
            portnum_packets = [x for x in matching_packets if x.portnum == portnum]
            latest_packet_for_portnum = portnum_packets[0]
            discord_ts = get_discord_ts_from_dt(latest_packet_for_portnum.ts)
            ni_embed.add_field(name=f"{portnum}", value=f'Count: {len(portnum_packets)}\nLatest: {discord_ts}', inline=False)

        if matching_node.hw_model is not None:
            ni_embed.add_field(name=f"HW Model", value=matching_node.hw_model, inline=False)

        if matching_node.upd_ts_nodedb is not None:
            discord_ts = get_discord_ts_from_dt(matching_node.upd_ts_nodedb)
            ni_embed.add_field(name=f"Node Info updated via Device NodeDB", value=discord_ts, inline=False)

        if matching_node.upd_ts_nodeinfo is not None:
            discord_ts = get_discord_ts_from_dt(matching_node.upd_ts_nodeinfo)
            ni_embed.add_field(name=f"Node Info updated via NODEINFO_APP Packet", value=discord_ts, inline=False)

        # get most recent position packet
        latest_position_packet = mesh_client._db_session.query(db_classes.RXPacket).filter(db_classes.RXPacket.src_num == matching_node.node_num).filter(db_classes.RXPacket.portnum == 'POSITION_APP').filter(db_classes.RXPacket.publisher_mesh_node_num == mesh_client.my_node_info.node_num_str).order_by(db_classes.RXPacket.ts.desc()).first()
        if latest_position_packet:
            lat = latest_position_packet.latitude
            lon = latest_position_packet.longitude
            alt_m = latest_position_packet.altitude
            alt_ft = round(alt_m * 3.281, 0)

            location_source = latest_position_packet.location_source
            pdop = latest_position_packet.pdop
            ground_speed = latest_position_packet.ground_speed
            sats_in_view = latest_position_packet.sats_in_view
            precision_bits = latest_position_packet.precision_bits

            url = f'https://www.google.com/maps/search/?api=1&query={lat},{lon}'
            position_embed = discord.Embed(title=f"Position Info", color=MeshBotColors.violet())

            position_embed.add_field(name='Position', value = f'[{round(lat,3)},{round(lon,3)}]({url})', inline=False)
            position_embed.add_field(name='Altitude', value=f'{alt_m}m ({alt_ft}ft)', inline=False)
            position_embed.add_field(name='Location Source', value=f'{location_source}', inline=False)
            position_embed.add_field(name='PDOP', value=f'{pdop}', inline=False)
            position_embed.add_field(name='Ground Speed', value=f'{ground_speed}', inline=False)
            position_embed.add_field(name='Sats in View', value=f'{sats_in_view}', inline=False)
            position_embed.add_field(name='Precision Bits', value=f'{precision_bits}', inline=False)

            discord_ts = get_discord_ts_from_dt(latest_position_packet.ts)
            position_embed.add_field(name='Updated via POSITION_APP Packet', value=discord_ts, inline=False)


            embeds.append((position_embed, latest_position_packet.ts))


        # get most recent position packet
        latest_device_metrics_packet = mesh_client._db_session.query(db_classes.RXPacket).filter(db_classes.RXPacket.src_num == matching_node.node_num).filter(db_classes.RXPacket.publisher_mesh_node_num == mesh_client.my_node_info.node_num_str).filter(db_classes.RXPacket.portnum == 'TELEMETRY_APP').filter(db_classes.RXPacket.has_device_metrics == True).order_by(db_classes.RXPacket.ts.desc()).first()
        if latest_device_metrics_packet:
            device_metrics = latest_device_metrics_packet.telemetry_device_metrics
            # this will be JSON
            if device_metrics:
                battery = device_metrics.get('batteryLevel')
                voltage = device_metrics.get('voltage')
                chan_util = device_metrics.get('channelUtilization')
                air_util = device_metrics.get('airUtilTx')
                uptime_sec = device_metrics.get('uptimeSeconds')
                device_info_embed = discord.Embed(title=f"Device Info", color=MeshBotColors.violet())

                device_info_embed.add_field(name='Battery Level', value=f'{battery}% ({voltage}v)', inline=False)
                device_info_embed.add_field(name='Channel Utilization', value=f'{round(chan_util, 2)}%', inline=False)
                device_info_embed.add_field(name='TX Duty Cycle', value=f'{round(air_util, 2)}%', inline=False)
                device_info_embed.add_field(name='Uptime', value=f'{uptime_str(uptime_sec)} ({uptime_sec}s)', inline=False)
                discord_ts = get_discord_ts_from_dt(latest_device_metrics_packet.ts)
                device_info_embed.add_field(name='Updated via TELEMETRY_APP Packet', value=discord_ts, inline=False)
                embeds.append((device_info_embed, latest_device_metrics_packet.ts))

        latest_environment_metrics_packet = mesh_client._db_session.query(db_classes.RXPacket).filter(db_classes.RXPacket.src_num == matching_node.node_num).filter(db_classes.RXPacket.publisher_mesh_node_num == mesh_client.my_node_info.node_num_str).filter(db_classes.RXPacket.portnum == 'TELEMETRY_APP').filter(db_classes.RXPacket.has_environment_metrics == True).order_by(db_classes.RXPacket.ts.desc()).first()
        if latest_environment_metrics_packet:
            env_metrics = latest_environment_metrics_packet.telemetry_environment_metrics
            # this will be JSON
            if env_metrics:
                temp = env_metrics.get('temperature') # celsius
                temp_f = (temp * (9/5)) + 32
                rel_hum = env_metrics.get('relativeHumidity') # %
                baro = env_metrics.get('barometricPressure') # hPa
                baro_mmhg = baro * 0.7500637554192
                baro_inhg = baro * 0.02953
                baro_psi = baro * 0.014503768078

                dew_point = temp - ((100 - rel_hum)/5) # celsius
                dew_point_f = (dew_point * (9/5)) + 32

                env_info_embed = discord.Embed(title=f"Environmental Info", color=MeshBotColors.violet())

                env_info_embed.add_field(name='Temperature', value=f'{round(temp, 1)}C ({round(temp_f, 1)}F)', inline=False)
                env_info_embed.add_field(name='Relative Humidity', value=f'{round(rel_hum, 1)}%', inline=False)
                env_info_embed.add_field(name='Dew Point', value=f'{round(dew_point, 1)}C ({round(dew_point_f, 1)}F)', inline=False)
                env_info_embed.add_field(name='Barometric Pressure', value=f'{round(baro, 1)}hPa ({round(baro_inhg, 2)}inHg/{round(baro_psi,1)}psi)', inline=False)
                discord_ts = get_discord_ts_from_dt(latest_environment_metrics_packet.ts)
                env_info_embed.add_field(name='Updated via TELEMETRY_APP Packet', value=discord_ts, inline=False)
                embeds.append((env_info_embed, latest_environment_metrics_packet.ts))

        # sort the embeds by timestamp, but add nodeinfo first always
        embeds = sorted(embeds, key=lambda x: x[1], reverse=True)
        embeds = [x[0] for x in embeds]
        embeds.insert(0, ni_embed)

    out = await interaction.followup.send(embeds=embeds)


@discord_client.tree.command(name="self", description="Lists info about directly connected node.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def describe_self(interaction: discord.Interaction):
    logging.info(f'/self received.')

    text = [
        f'**MeshBot Version:** {__version__}',
        f'**Node ID:** {mesh_client.my_node_info.user_info.user_id}',
        f'**Short Name:** {mesh_client.my_node_info.user_info.short_name}',
        f'**Long Name:** {mesh_client.my_node_info.user_info.long_name}',
        f'**MAC Address:** {mesh_client.my_node_info.user_info.mac_address}',
        f'**HW Model:** {mesh_client.my_node_info.user_info.hw_model}',
        f'**Battery Level:** {mesh_client.my_node_info.device_metrics.battery_level}%',
        f'**Battery Voltage:** {mesh_client.my_node_info.device_metrics.voltage}V',
    ]

    embed = discord.Embed(title='Local Node Information', description='\n'.join(text))
    await interaction.response.send_message(embed=embed)

@discord_client.tree.command(name="all_nodes", description="Lists all nodes.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def all_nodes(interaction: discord.Interaction):
    # await interaction.response.defer()

    logging.info(f'/all_nodes received.')

    await asyncio.sleep(0.1)

    embed = discord.Embed(title="All Nodes", description=f"Listing all nodes in DB.", color=MeshBotColors.green())
    embed.add_field(name='Request Info', value=f"Requested by {interaction.user.mention} at {get_current_time_discord_str()}")

    # Send first message
    out = await interaction.response.send_message(embed=embed)

    tic = time.time()
    # Get message to reference later
    msg_id = out.message_id
    message = await discord_client.channel.fetch_message(msg_id)

    thread = await message.create_thread(name='/all_nodes cmd', auto_archive_duration=60)
    chunks = mesh_client.get_nodes_from_db()
    thread_id = thread.id

    if len(chunks) == 0:
        final_text = f'No nodes in DB.'
    else:
        final_text = f'Finished listing all nodes from DB.'

    final_msg = discord.Embed(
        title='End Thread',
        description=final_text,
        color=MeshBotColors.white()
    )

    toc = time.time() - tic
    original_msg_field = embed_field(name="Processing Time", value=f'Took {convert_secs_to_pretty(toc)}', inline=False)
    original_msg_id = out.message_id
    original_message_edit = None # None means add, 1 means replace first field

    packet = {
        'content': chunks,
        'thread_id': thread_id,
        'final_msg': final_msg,
        'original_msg_field': original_msg_field,
        'original_msg_id': original_msg_id,
        'original_message_edit': original_message_edit
    }
    logging.info(f'Got nodes, formatted data, sending to enqueue_msg_thread. Total of {len(chunks)} chunks (of up to 10).')
    discord_client.enqueue_msg_thread(packet)


@discord_client.tree.command(name="debug", description="Gives debug info to the user")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def debug(interaction: discord.Interaction):
    # do this command differently, just do all the logic here instead of using a queue
    logging.info(f'/debug received, printing debug info')

    # calculate last heard
    lastheard = mesh_client.myNodeInfo.get('lastHeard') # TODO Need to fix this (replace myNodeInfo with soemthing else)
    if lastheard: # ignore if doesn't have lastHeard property
        ts = int(lastheard)
        # if ts > time.time() - (time_limit * 60): # Only include if its less then time_limit
        timezone = pytz.timezone(config.time_zone)
        local_time = datetime.datetime.fromtimestamp(ts, tz=pytz.utc).astimezone(timezone)
        timestr = time_str_from_dt(local_time)
    else:
        timestr = '???'

    debug_text = f"```lastHeard: {timestr}\n"
    for thing in ['user', 'deviceMetrics','localStats']:
        debug_text += f'{thing} items:\n'
        for key, value in mesh_client.myNodeInfo.get(thing,{}).items():
            debug_text += f"  {key}: {value}\n"
    debug_text += '```'

    embed = discord.Embed(title='Debug Information', description=debug_text)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # Dump nodes info to json file in log dir
    my_node_dump = os.path.join(log_dir, 'my_node_dump.json')
    try:
        default = lambda o: f'<<not serializable data: {type(o).__qualname__}>>'
        with open(my_node_dump, 'w', encoding='utf-8', errors='ignore') as f:
            json.dump(mesh_client.myNodeInfo, f, indent=4, default=default)
        logging.info(f'Wrote my node info to {my_node_dump}')
    except Exception as e:
        logging.info(f'Error trying to dump my node info. \nError: {e}\n')

    # Dump nodes info to json file in log dir
    nodes_dump = os.path.join(log_dir, 'nodes_dump.json')
    try:
        default = lambda o: f'<<not serializable data: {type(o).__qualname__}>>'
        with open(nodes_dump, 'w', encoding='utf-8', errors='ignore') as f:
            json.dump(mesh_client.nodes, f, indent=4, default=default)
        logging.info(f'Wrote nodes info to {nodes_dump}')
    except Exception as e:
        logging.info(f'Error trying to dump all nodes. \nError: {e}\n')

    await asyncio.sleep(0.1)

# Callsign Search Command
@discord_client.tree.command(name="ham", description="Search for a callsign.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def ham(interaction: discord.Interaction, callsign: str):
    url = f"https://callook.info/{callsign}/json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()

    # Check if the 'current' key exists in the data
    if 'current' not in data:
        await interaction.response.send_message(f"Callsign '{callsign}' not found.", ephemeral=True)
        return


    embed = discord.Embed(title="🎙️ Callsign Information 🎙️", color=0xFFC0CB)
    embed.add_field(name="Callsign", value=data['current']['callsign'], inline=False)
    embed.add_field(name="Operator Class", value=data['current']['operClass'], inline=False)
    embed.add_field(name="Name", value=data['name'], inline=False)
    embed.add_field(name="Address", value=f"{data['address']['line1']}, {data['address']['line2']}", inline=False)
    embed.add_field(name="Grant Date", value=data['otherInfo']['grantDate'], inline=False)
    embed.add_field(name="Expiration Date", value=data['otherInfo']['expiryDate'], inline=False)
    embed.add_field(name="Gridsquare", value=data['location']['gridsquare'], inline=False)

    # Create a hyperlink to Google Maps using the coordinates
    latitude = data['location']['latitude']
    longitude = data['location']['longitude']
    google_maps_url = f"http://maps.google.com/maps?q={latitude},{longitude}"
    embed.add_field(name="Coordinates", value=f"[{latitude}, {longitude}]({google_maps_url})", inline=False)

    embed.add_field(name="FCC Registration Number (FRN)", value=data['otherInfo']['frn'], inline=False)
    embed.add_field(name="FCC URL", value=data['otherInfo']['ulsUrl'], inline=False)

    await interaction.response.send_message(embed=embed)

# returns a map with a marker of a specific node location
@discord_client.tree.command(name='map', description=f"Lookup node location and display map.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def get_node_map(interaction: discord.Interaction, node_name: str, map_zoom_level: int = 12):
    logging.info(f'/map command received.')

    node = mesh_client.get_node_info(shortname=node_name)
    current_time = get_current_time_str()

    if not config.gmaps_api_key:
        embed = discord.Embed(title=f"Error: This command requires a google maps API key in config.json.", color=MeshBotColors.red())

    if node:
        # get the lat/long
        if isinstance(node, dict) and 'position' in node:
            embed = discord.Embed(title=f"Location for Node: {node_name}:", color=MeshBotColors.green())
            embed.add_field(name='Lat/Lon', value=f'{lat},{lon}')
            pos_data = node['position']
            lat = pos_data.get('latitude')
            lon = pos_data.get('longitude')
            url = f'https://maps.googleapis.com/maps/api/staticmap?center={lat},{lon}&zoom={map_zoom_level}&size=400x400&key={config.gmaps_api_key}&markers=color:green|label:{node_name}|{lat},{lon}'
            embed.set_image(url=url)
        else:
            embed = discord.Embed(title=f"Location data unavailable for Node: {node_name}.", color=MeshBotColors.red())

    else:
        embed = discord.Embed(title=f"Error: Node with shotname {node_name} not found.", color=MeshBotColors.red())


    embed.set_footer(text=f"{current_time}")

    await interaction.response.send_message(embed=embed)


@discord_client.tree.command(name="kms", description="Search for a callsign.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def kms(interaction: discord.Interaction):
    logging.info(f'/kms command received.')
    embed = discord.Embed(title=f"Killing Myself", description=f'Cause {interaction.user.mention} told me to', color=MeshBotColors.white())
    await interaction.response.send_message(embed=embed)
    logging.info(f'Killing myself as requested by {interaction.user.name} ({interaction.user.id})')
    await discord_client.close()
    mesh_client.iface.close()

@discord_client.tree.command(name="reconnect", description="Force reconnection to the mesh network.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def reconnect(interaction: discord.Interaction):
    logging.info(f'/reconnect command received from {interaction.user.name} ({interaction.user.id})')
    await interaction.response.defer(ephemeral=False)

    embed = discord.Embed(
        title="Reconnecting",
        description="Attempting to reconnect to the mesh network...",
        color=MeshBotColors.warning()
    )
    await interaction.followup.send(embed=embed)

    # Attempt to reconnect using the connection manager
    if hasattr(mesh_client, 'connection_manager'):
        success = mesh_client.connection_manager.force_reconnect()

        if success:
            success_embed = discord.Embed(
                title="Reconnection Successful",
                description="Successfully reconnected to the mesh network!",
                color=MeshBotColors.green()
            )
            await interaction.followup.send(embed=success_embed)
        else:
            failure_embed = discord.Embed(
                title="Reconnection Failed",
                description="Failed to reconnect to the mesh network. Check logs for details.",
                color=MeshBotColors.error()
            )
            await interaction.followup.send(embed=failure_embed)
    else:
        error_embed = discord.Embed(
            title="Error",
            description="Connection manager is not initialized.",
            color=MeshBotColors.error()
        )
        await interaction.followup.send(embed=error_embed)

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
        if mesh_client:
            if mesh_client.iface:
                mesh_client.iface.close()

if __name__ == "__main__":
    run_discord_bot()
