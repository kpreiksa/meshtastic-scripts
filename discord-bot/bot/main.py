import asyncio
import json
import logging
import os
import aiohttp
from datetime import datetime
import discord
from discord import ButtonStyle
from discord.ui import View, Button
import pytz
from pprint import pprint
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import db_base
from functools import wraps

from config_classes import Config
from mesh_client import MeshClient
from discord_client import DiscordBot
from util import get_current_time_str
from util import MeshBotColors, DiscordInteractionInfo

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
        logging.FileHandler(os.path.join(log_dir, log_file)),
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

engine = create_engine(f'sqlite:///{db_dir}/example.db')
db_base.Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()
config = Config()
mesh_client = MeshClient(db_session=session, config=config) # create the mesh client but do not connect yet
discord_client = DiscordBot(mesh_client, config, intents=discord.Intents.default())

# discord commands

@discord_client.tree.command(name="help", description="Shows the help message.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def help_command(interaction: discord.Interaction):
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
                "`/debug` - Shows information this bot's mesh node\n"
                "`/ham` - Look up callsign for ham operator\n"
                "`/map` - Shows map with marker for specific node\n")

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
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def sendid(interaction: discord.Interaction, nodeid: str, message: str):
    logging.info(f'/sendid command received. ID: {nodeid}. Message: {message}. Attempting to send')
    try:
        current_time = get_current_time_str()

        # craft message
        embed = discord.Embed(title="Sending Message", description=message, color=MeshBotColors.TX_PENDING())
        embed.add_field(name="To Node:", value=mesh_client.get_node_descriptive_string(node_id=nodeid), inline=False)  # Add '!' in front of nodeid
        embed.add_field(name='TX State', value='Pending', inline=False)
        embed.set_footer(text=f"{current_time}")

        # send message
        out = await interaction.response.send_message(embed=embed, ephemeral=False)
        discord_interaction_info = DiscordInteractionInfo(interaction.guild_id, interaction.channel_id, out.message_id, interaction.user.id, interaction.user.display_name, interaction.user.global_name, interaction.user.name, interaction.user.mention)

        mesh_client.enqueue_send_nodeid(nodeid, message, discord_interaction_info)

    except ValueError as e:
        error_embed = discord.Embed(title="Error", description="Invalid hexadecimal node ID.", color=MeshBotColors.error())
        logging.info(f'/sendid command failed. Invalid hexadecimal node id. Error: {e}')
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@discord_client.tree.command(name="sendnum", description="Send a message to a specific node.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def sendnum(interaction: discord.Interaction, nodenum: int, message: str):
    logging.info(f'/sendnum command received. NodeNum: {nodenum}. Sending message: {message}')
    # TODO add error handling for nodenum

    # craft message
    current_time = get_current_time_str()
    embed = discord.Embed(title="Sending Message", description=message, color=MeshBotColors.TX_PENDING())
    embed.add_field(name="To Node:", value=f'{mesh_client.get_node_descriptive_string(nodenum=nodenum)}', inline=False)
    embed.add_field(name='TX State', value='Pending', inline=False)
    embed.set_footer(text=f"{current_time}")
    # send message
    out = await interaction.response.send_message(embed=embed)
    discord_interaction_info = DiscordInteractionInfo(interaction.guild_id, interaction.channel_id, out.message_id, interaction.user.id, interaction.user.display_name, interaction.user.global_name, interaction.user.name, interaction.user.mention)

    mesh_client.enqueue_send_nodenum(nodenum, message, discord_interaction_info)


@discord_client.tree.command(name="send_shortname", description="Send a message to a specific node.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def send_shortname(interaction: discord.Interaction, node_name: str, message: str):
    logging.info(f'/send_shortname command received. nodeName: {node_name}. Sending message: {message}')

    current_time = get_current_time_str()

    # craft message

    embed = discord.Embed(title="Sending Message", description=message, color=MeshBotColors.TX_PENDING())
    try:
        node_descriptor = mesh_client.get_node_descriptive_string(shortname=node_name)
        embed.add_field(name="To Node:", value=f'{mesh_client.get_node_descriptive_string(shortname=node_name)}', inline=False)
        embed.add_field(name='TX State', value='Pending', inline=False)
    except:
        embed.color = MeshBotColors.error()
        embed.add_field(name="To Node:", value='?', inline=False)
        embed.add_field(name='TX State', value='Error', inline=False)
        embed.add_field(name='Error Description', value=f'Node with short name: {node_name} not found.', inline=False)

    embed.set_footer(text=f"{current_time}")
    # send message to discord
    out = await interaction.response.send_message(embed=embed)

    # queue message to be sent on mesh
    discord_interaction_info = DiscordInteractionInfo(interaction.guild_id, interaction.channel_id, out.message_id, interaction.user.id, interaction.user.display_name, interaction.user.global_name, interaction.user.name, interaction.user.mention)
    mesh_client.enqueue_send_shortname(node_name, message, discord_interaction_info)

# Dynamically create commands based on mesh_channel_names
for mesh_channel_index, mesh_channel_name in config.channel_names.items():
    @discord_client.tree.command(name=mesh_channel_name.lower(), description=f"Send a message in the {mesh_channel_name} channel.")
    @discord_client.only_in_channel(discord_client.dis_channel_id)
    async def send_channel_message(interaction: discord.Interaction, message: str, mesh_channel_index: int = mesh_channel_index):
        logging.info(f'/{interaction.command.name} command received. Sending message: {message}')
        current_time = get_current_time_str()

        embed = discord.Embed(title=f"Sending Message", description=message, color=MeshBotColors.TX_PENDING())
        embed.add_field(name="To Channel:", value=config.channel_names[mesh_channel_index], inline=False)
        embed.add_field(name='TX State', value='Pending', inline=False)
        embed.set_footer(text=f"{current_time}")

        out = await interaction.response.send_message(embed=embed)

        discord_interaction_info = DiscordInteractionInfo(interaction.guild_id, interaction.channel_id, out.message_id, interaction.user.id, interaction.user.display_name, interaction.user.global_name, interaction.user.name, interaction.user.mention)
        mesh_client.enqueue_send_channel(mesh_channel_index, message, discord_interaction_info=discord_interaction_info)


@discord_client.tree.command(name="traceroute", description="Traceroute a node.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def run_traceroute(interaction: discord.Interaction, node_id: str):
    await interaction.response.defer()

    logging.info(f'/traceroute received.')
    mesh_client.enqueue_traceroute(node_id)
    await asyncio.sleep(0.1)

    await interaction.delete_original_response()

@discord_client.tree.command(name="active", description="Lists all active nodes.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def active(interaction: discord.Interaction, active_time: str='61'):
    await interaction.response.defer()

    logging.info(f'/active received, sending to queue with time: {active_time}')
    mesh_client.enqueue_active_nodes(active_time=active_time)
    await asyncio.sleep(0.1)

    await interaction.delete_original_response()

@discord_client.tree.command(name="telemetry_exchange", description="Request telemetry exchange.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def telemetry_exchange(interaction: discord.Interaction, node_num: str = None, node_id: str = None, node_shortname: str = None):
    logging.info(f'/telemetry command received. node_num: {node_num}. node_id: {node_id}. node_shortname: {node_shortname}.')

    current_time = get_current_time_str()

    embed = discord.Embed(title="Sending Telemetry Request", color=MeshBotColors.TX_PENDING())
    embed.set_footer(text=f"{current_time}")

    if not node_id and not node_num and not node_shortname:
        embed.add_field(name='Error Description', value=f'One of node_num, node_id, or node_shortname must be specified.', inline=False)
        return

    try:
        node_descriptor = mesh_client.get_node_descriptive_string(node_id=node_id, nodenum=node_num, shortname=node_shortname)
        embed.add_field(name="To Node:", value=f'{node_descriptor}', inline=False)
        embed.add_field(name='TX State', value='Error', inline=False)
    except Exception as e:

        embed.add_field(name='Error Description', value=f'Node with short name: {node_shortname} not found.', inline=False)
        embed.color = MeshBotColors.error()

    # send message to discord
    out = await interaction.response.send_message(embed=embed)

    discord_interaction_info = DiscordInteractionInfo(interaction.guild_id, interaction.channel_id, out.message_id, interaction.user.id, interaction.user.display_name, interaction.user.global_name, interaction.user.name, interaction.user.mention)
    if node_num:
        logging.info(f'Sending telemetry request to nodenum: {node_num}')
        mesh_client.enqueue_telemetry_nodenum(node_num, discord_interaction_info)
    elif node_id:
        logging.info(f'Sending telemetry request to node_id: {node_id}')
        mesh_client.enqueue_telemetry_nodeid(node_id, discord_interaction_info)
    elif node_shortname:
        logging.info(f'Sending telemetry request to shortname: {node_shortname}')
        mesh_client.enqueue_telemetry_shortname(node_shortname, discord_interaction_info)
    # else:
    #     logging.info(f'Sending telemetry request to broadcast.')
    #     mesh_client.enqueue_telemetry_broadcast(discord_interaction_info)


@discord_client.tree.command(name="self", description="Lists info about directly connected node.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def describe_self(interaction: discord.Interaction):
    logging.info(f'/self received.')

    text = [
        f'**Node ID:** {mesh_client.my_node_info.user_info.user_id}',
        f'**Short Name:** {mesh_client.my_node_info.user_info.short_name}',
        f'**Long Name:** {mesh_client.my_node_info.user_info.long_name}',
        f'**MAC Address:** {mesh_client.my_node_info.user_info.mac_address}',
        f'**HW Model:** {mesh_client.my_node_info.user_info.hw_model}',
    ]

    embed = discord.Embed(title='Local Node Information', description='\n'.join(text))
    await interaction.response.send_message(embed=embed)


@discord_client.tree.command(name="all_nodes", description="Lists all nodes.")
@discord_client.only_in_channel(discord_client.dis_channel_id)
async def all_nodes(interaction: discord.Interaction):
    await interaction.response.defer()

    logging.info(f'/all_node received.')
    mesh_client.enqueue_all_nodes()
    await asyncio.sleep(0.1)

    await interaction.delete_original_response()

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
        local_time = datetime.fromtimestamp(ts, tz=pytz.utc).astimezone(timezone)
        timestr = local_time.strftime('%d %B %Y %I:%M:%S %p')
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
