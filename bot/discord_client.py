import logging
import queue
import asyncio
from functools import wraps

import discord
from discord import app_commands

from config_classes import Config

import util

class DiscordBot(discord.Client):
    def __init__(self, mesh_client, *args, **kwargs):

        self.config = Config()
        self._discordqueue = queue.Queue(maxsize=20)

        self._meshresponsequeue = queue.Queue(maxsize=20)

        self.mesh_client = mesh_client

        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        # TODO maybe move the mesh parts into a separate class or dict to not possibly conflict with discord.Client super class
        self.channel = None
        self.dis_channel_id = int(self.config.discord_channel_id)


    async def setup_hook(self) -> None:  # Create the background task and run it in the background.
        self.bg_task = self.loop.create_task(self.background_task())
        await self.tree.sync()

    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')

    def check_channel_id(self, other_channel_id):
        return other_channel_id == self.dis_channel_id

    def enqueue_msg(self, msg):
        self._discordqueue.put(msg)

    def enqueue_mesh_response(self, msg):
        self._meshresponsequeue.put(msg)

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

                msg_id = meshresponse.get('discord_message_id')
                if msg_id is None:
                    logging.error('No discord_message_id found in mesh response (probably an ACK from self, on a message sent to a channel), skipping message update')
                    self._meshresponsequeue.task_done()
                    continue
                ack_by_id = meshresponse.get('response_from_id')
                ack_by_shorname = meshresponse.get('response_from_shortname')
                ack_by_longname = meshresponse.get('response_from_longname')

                ack_time = meshresponse.get('response_rx_time')

                ack_time_str = util.time_from_ts(ack_time)

                message = await self.channel.fetch_message(msg_id)

                e = message.embeds[0]
                e.add_field(name='Acknowledged', value=f'{ack_by_id} | {ack_by_shorname} | {ack_by_longname}\n{ack_time_str}', inline=False)
                await message.edit(embed=e)

                self._meshresponsequeue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                logging.exception('Exception processing _meshresponsequeue', exc_info=e)

            # process stuff on mesh side
            self.mesh_client.background_process()

            await asyncio.sleep(5)

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

