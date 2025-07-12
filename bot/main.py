import asyncio
import json
import logging
import os
from datetime import datetime
import discord
from discord import ButtonStyle
from discord.ui import View, Button
import pytz
from pprint import pprint
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import db_base

from config_classes import Config
from mesh_client import MeshClient
from discord_client import DiscordBot
from util import get_current_time_str
from util import MeshBotColors

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

class HelpView(View):
    def __init__(self):
        super().__init__(timeout=None)

        # Create buttons
        self.add_item(Button(label="Kavitate", style=ButtonStyle.link, url="https://github.com/Kavitate"))
        self.add_item(Button(label="Meshtastic", style=ButtonStyle.link, url="https://meshtastic.org"))
        self.add_item(Button(label="Meshmap", style=ButtonStyle.link, url="https://meshmap.net"))
        self.add_item(Button(label="Python Meshtastic Docs", style=ButtonStyle.link, url="https://python.meshtastic.org/index.html"))



engine = create_engine('sqlite:///example.db')
db_base.Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()
config = Config()
mesh_client = MeshClient(db_session=session)
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

        embed = discord.Embed(title="Meshtastic Bot Help", description=help_text, color=MeshBotColors.green())
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
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{discord_client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        logging.info(f'/sendid command received. ID: {nodeid}. Message: {message}. Attempting to send')
        try:
            # Strip the leading '!' if present
            if nodeid.startswith('!'):
                nodeid = nodeid[1:]

            shortname = mesh_client.get_short_name(nodeid)
            longname = mesh_client.get_long_name(nodeid)

            current_time = get_current_time_str()

            # craft message
            embed = discord.Embed(title="Sending Message", description=message, color=MeshBotColors.TX())
            embed.add_field(name="To Node:", value=f'!{nodeid} | {shortname} | {longname}', inline=True)  # Add '!' in front of nodeid
            embed.set_footer(text=f"{current_time}")

            # send message
            await interaction.response.send_message(embed=embed, ephemeral=False)
            mesh_client.enqueue_send_nodeid(nodeid, message)

        except ValueError as e:
            error_embed = discord.Embed(title="Error", description="Invalid hexadecimal node ID.", color=MeshBotColors.error())
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

        node_id = mesh_client.get_node_id_from_num(nodenum)
        shortname = mesh_client.get_short_name(node_id)
        longname = mesh_client.get_long_name(node_id)

        # craft message
        current_time = get_current_time_str()
        embed = discord.Embed(title="Sending Message", description=message, color=MeshBotColors.TX())
        embed.add_field(name="To Node:", value=f'{nodenum} | {node_id} | {shortname} | {longname}', inline=True)
        embed.set_footer(text=f"{current_time}")
        # send message
        await interaction.response.send_message(embed=embed)
        mesh_client.enqueue_send_nodenum(nodenum, message)


@discord_client.tree.command(name="send_shortname", description="Send a message to a specific node.")
async def send_shortname(interaction: discord.Interaction, node_name: str, message: str):
    # Check channel_id
    if interaction.channel_id != discord_client.dis_channel_id:
        # post rejection
        logging.info(f'Rejected /send_shortname Command - Sent on wrong discord channel')
        embed = discord.Embed(title='Wrong Channel', description=f'Commands for this bot are only allowed in <#{discord_client.dis_channel_id}>')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        logging.info(f'/send_shortname command received. nodeName: {node_name}. Sending message: {message}')

        current_time = get_current_time_str()

        node = mesh_client.get_node_info_from_shortname(node_name)

        if isinstance(node, dict):

            node_id = node.get('user', {}).get('id')
            shortname = mesh_client.get_short_name(node_id)
            longname = mesh_client.get_long_name(node_id)

            # craft message
            embed = discord.Embed(title="Sending Message", description=message, color=MeshBotColors.TX())
            embed.add_field(name="To Node:", value=f'{node_id} | {shortname} | {longname}', inline=True)
            embed.set_footer(text=f"{current_time}")
            # send message
            out = await interaction.response.send_message(embed=embed)
            discord_message_id = out.message_id
            channel_id = interaction.channel_id
            guild_id = interaction.guild_id

            mesh_client.enqueue_send_shortname(node_name, message, guild_id, channel_id, discord_message_id)

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

            embed = discord.Embed(title=f"Sending Message to {config.channel_names[mesh_channel_index]}:", description=message, color=MeshBotColors.TX())
            embed.set_footer(text=f"{current_time}")

            await interaction.response.send_message(embed=embed)
            mesh_client.enqueue_send_channel(mesh_channel_index, message)


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
