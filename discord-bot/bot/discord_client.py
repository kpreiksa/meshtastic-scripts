import logging
import queue
import asyncio
from functools import wraps

import discord
from discord import app_commands

from config_classes import Config

import util

class DiscordBot(discord.Client):
    def __init__(self, mesh_client, config, *args, **kwargs):

        self.config = config
        self._discordqueue = queue.Queue(maxsize=20)

        self._meshresponsequeue = queue.Queue(maxsize=20)

        self.mesh_client = mesh_client
        self.mesh_client.link_discord(self)

        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        # TODO maybe move the mesh parts into a separate class or dict to not possibly conflict with discord.Client super class
        self.channel = None
        self.dis_channel_id = int(self.config.discord_channel_id)


    # async def setup_hook(self) -> None:  # Create the background task and run it in the background.
    #     self.bg_task = self.loop.create_task(self.background_task())
    #     await self.tree.sync()

    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
        self.bg_task = self.loop.create_task(self.background_task())
        self.mesh_client.connect() # once discord is ready... conncet to mesh
        await self.tree.sync()

    def check_channel_id(self, other_channel_id):
        return other_channel_id == self.dis_channel_id

    def enqueue_msg(self, msg):
        self._discordqueue.put(msg)
        
    def enqueue_ack(self, discord_message_id, ack_by_id, response_rx_rssi, response_rx_snr, response_hop_start, response_hop_limit):
        self._enqueue_mesh_response({
            'msg_type': 'ACK',
            'discord_message_id': discord_message_id,
            'response_from_id': ack_by_id,
            'response_rx_rssi': response_rx_rssi,
            'response_rx_snr': response_rx_snr,
            'response_hop_start': response_hop_start,
            'response_hop_limit': response_hop_limit,
        })
        
    def enqueue_tx_error(self, discord_message_id, error_text):
        self._enqueue_mesh_response({
            'msg_type': 'TX_ERROR',
            'discord_message_id': discord_message_id,
            'error_text': error_text,
        })
        
    def enqueue_tx_confirmation(self, discord_message_id):
        self._enqueue_mesh_response({
            'msg_type': 'TX_CONFIRMATION',
            'discord_message_id': discord_message_id,
        })

    def _enqueue_mesh_response(self, msg):
        self._meshresponsequeue.put(msg)
        
    async def process_mesh_response(self, msg):
        msg_type = msg.get('msg_type')
        
        if msg_type == 'ACK':
            
            logging.info(f'Admin message: ACK received')
        
            msg_id = msg.get('discord_message_id')
            if msg_id is None:
                logging.error('No discord_message_id found in mesh response (probably an ACK from self, on a message sent to a channel), skipping message update')
                return
            
            ack_by_id = msg.get('response_from_id')

            message = await self.channel.fetch_message(msg_id)
            
            ack_time_str = f'ACK Time: {util.get_current_time_str()}'

            e = message.embeds[0]
            
            e.set_field_at(1, name='TX State', value='Acknowledged')
            e.add_field(name='ACK Info', value=f'{self.mesh_client.get_node_descriptive_string(node_id=ack_by_id)}\n{ack_time_str}', inline=False)
            await message.edit(embed=e)
            
        elif msg_type == 'TX_CONFIRMATION':
            
            logging.info(f'Admin message: TX_CONFIRMATION received')
            
            msg_id = msg.get('discord_message_id')
            if msg_id is None:
                logging.error('No discord_message_id found in mesh response.')
                return
            
            message = await self.channel.fetch_message(msg_id)
            
            # modify the original message
            e = message.embeds[0]
            e.set_field_at(1, name='TX State', value='Sent')
            await message.edit(embed=e)
            
        elif msg_type == 'TX_ERROR':
            
            logging.info(f'Admin message: TX_ERROR received')
            
            msg_id = msg.get('discord_message_id')
            if msg_id is None:
                logging.error('No discord_message_id found in mesh response.')
                return
            
            error_text = msg.get('error_text')
            
            message = await self.channel.fetch_message(msg_id)
            
            # modify the original message
            e = message.embeds[0]
            e.color = discord.Color.red()
            e.set_field_at(1, name='TX State', value='Error')
            e.add_field(name='Error Description', value=error_text, inline=False)
            await message.edit(embed=e)
            

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
            except Exception as e:
                logging.exception('Exception processing discord queue', exc_info=e)

            try:
                meshresponse = self._meshresponsequeue.get_nowait()
                await self.process_mesh_response(meshresponse)
                self._meshresponsequeue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                logging.exception('Exception processing _meshresponsequeue', exc_info=e)

            # process stuff on mesh side
            self.mesh_client.background_process()

            await asyncio.sleep(0.5)

    @staticmethod
    def only_in_channel(allowed_channel_id: int): # must pass allowed_channel_id as argument becaues this is compiled at import time, and you cannot pass self in
        def decorator(func):
            @wraps(func)
            async def wrapper(interaction: discord.Interaction, *args, **kwargs):
                if interaction.channel_id != allowed_channel_id:
                    command_name = interaction.command.name if interaction.command else "unknown"
                    logging.error(f'Rejected /{command_name} command, sent in wrong channel: {interaction.channel_id}')
                    embed = discord.Embed(
                        title='Wrong Channel',
                        description=f'Commands for this bot are only allowed in <#{allowed_channel_id}>',
                        color=util.MeshBotColors.error()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                return await func(interaction, *args, **kwargs)
            return wrapper
        return decorator

