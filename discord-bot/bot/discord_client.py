import logging
import queue
import asyncio
from functools import wraps

import discord
from discord import app_commands

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

    def enqueue_ack(self, ack_obj):
        self._enqueue_mesh_response({
            'msg_type': 'ACK',
            'discord_message_id': ack_obj.tx_packet.discord_message_id,
            'response_from_id': ack_obj.ack_packet.src_id,
            'response_rx_rssi': ack_obj.ack_packet.rx_rssi_str,
            'response_rx_snr': ack_obj.ack_packet.rx_snr_str,
            'response_hop_start': ack_obj.ack_packet.hop_start,
            'response_hop_limit': ack_obj.ack_packet.hop_limit,
            'is_implicit': ack_obj.implicit_ack,
            'ack_error_reason': ack_obj.ack_packet.error_reason
        })

    def enqueue_mesh_text_msg_received(self, packet):

        mesh_channel_index = packet.channel
        if mesh_channel_index is None:
            mesh_channel_index = 0
        mesh_channel_name = self.config.channel_names.get(mesh_channel_index, f"Unknown Channel ({mesh_channel_index})")

        current_time = util.get_current_time_str()

        hop_start = packet.hop_start

        if packet.hop_limit and packet.hop_start:
            hops = int(packet.hop_limit) - int(packet.hop_limit)
        else:
            hops = "?"
            if not packet.hop_limit:
                hop_start = "?"

        embed = discord.Embed(title="Message Received", description=packet.text, color=util.MeshBotColors.RX())
        embed.add_field(name="From Node", value=packet.src_descriptive, inline=False)
        embed.add_field(name="RxSNR / RxRSSI", value=f"{packet.rx_snr_str} / {packet.rx_rssi_str}", inline=True)
        embed.add_field(name="Hops", value=f"{hops} / {hop_start}", inline=True)
        embed.set_footer(text=f"{current_time}")

        if packet.to_all:
            embed.add_field(name="To Channel", value=mesh_channel_name, inline=True)
        else:
            embed.add_field(name="To Node", value=packet.dst_descriptive, inline=True)

        logging.info(f'Putting Mesh Received message on Discord queue')
        self.enqueue_msg(embed)

    def enqueue_mesh_ready(self, node_descriptor, modem_preset):
        # TODO: Check if this is enabled in config
        embed = discord.Embed(title="Mesh Ready", description=f'Subscribed to mesh.', color=util.MeshBotColors.green())
        embed.add_field(name='Host Node', value=node_descriptor, inline=False)
        embed.add_field(name='LoRa Preset', value=modem_preset)
        current_time = util.get_current_time_str()
        embed.set_footer(text=f"{current_time}")
        self.enqueue_msg(embed)

    def enqueue_battery_low_alert(self, text):
        embed = discord.Embed(
            title='Node Battery Low!',
            description=text,
            color=util.MeshBotColors.error()
        )
        self.enqueue_msg(embed)

    def enqueue_lost_comm(self, exception_obj):
        embed = discord.Embed(title="Lost Comm", description=f'Lost Comm: {str(exception_obj)}', color=util.MeshBotColors.error())
        current_time = util.get_current_time_str()
        embed.set_footer(text=f"{current_time}")
        self.enqueue_msg(embed)

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

    def enqueue_tx_confirmation_dm(self, discord_message_id, node_descriptor):
        self._enqueue_mesh_response({
            'msg_type': 'TX_CONFIRMATION_DM',
            'discord_message_id': discord_message_id,
            'node_descriptive_name': node_descriptor,
        })

    def _enqueue_mesh_response(self, msg):
        self._meshresponsequeue.put(msg)

    async def process_mesh_response(self, msg):
        msg_type = msg.get('msg_type')

        if msg_type == 'ACK':

            logging.info(f'Response message: ACK received')

            msg_id = msg.get('discord_message_id')
            if msg_id is None:
                logging.error('No discord_message_id found in mesh response (probably an ACK from self, on a message sent to a channel), skipping message update')
                return

            ack_by_id = msg.get('response_from_id')

            message = await self.channel.fetch_message(msg_id)

            ack_time_str = f'ACK Time: {util.get_current_time_str()}'

            is_implicit = msg.get('is_implicit', True)

            # TODO: Figure out what the different ACK errors mean
            ack_error = msg.get('ack_error_reason')
            # ack_error = ack_error if ack_error != 'NONE' else None

            ack_str = f'Acknowledged - Error Reason: {ack_error}' if ack_error else 'Acknowledged'

            ack_text = f'{ack_str} (Implicit)' if is_implicit else f'{ack_str} (Explicit)'

            rx_rssi = msg.get('response_rx_rssi')
            rx_snr = msg.get('response_rx_snr')
            signal_metrics_available = rx_rssi is not None and rx_snr is not None
            hop_start = msg.get('response_hop_start')
            hop_limit = msg.get('response_hop_limit')

            ack_text_2 = []


            if is_implicit:
                ack_text_2.append('**ACK Type:**: Implicit')
                # if ack_error:
                ack_text_2.append(f'**Error Reason:** {ack_error}')
            else:
                ack_text_2.append('**ACK Type:**: Explicit')
                # if ack_error:
                ack_text_2.append(f'**Error Reason:** {ack_error}')
                ack_text_2.append(f'**Node:**: {self.mesh_client.get_node_descriptive_string(node_id=ack_by_id)}')

            if signal_metrics_available:
                ack_text_2.append(f'**RSSI/SNR:** {rx_rssi}/{rx_snr}')

            ack_text_2.append(f'**Hop Start/Limit:** {hop_start}/{hop_limit}')


            e = message.embeds[0]
            e.color = util.MeshBotColors.TX_ACK()
            e.set_field_at(1, name='TX State', value=ack_text)
            e.add_field(name='ACK Info', value='\n'.join(ack_text_2), inline=False)
            await message.edit(embed=e)

        elif msg_type == 'TX_CONFIRMATION':

            logging.info(f'Response message: TX_CONFIRMATION received')

            msg_id = msg.get('discord_message_id')
            if msg_id is None:
                logging.error('No discord_message_id found in mesh response.')
                return

            message = await self.channel.fetch_message(msg_id)

            # modify the original message
            e = message.embeds[0]
            e.color = util.MeshBotColors.TX_SENT()
            e.set_field_at(1, name='TX State', value='Sent')
            await message.edit(embed=e)

        elif msg_type == 'TX_CONFIRMATION_DM':

            logging.info(f'Successful TX message: TX_CONFIRMATION_DM received')

            msg_id = msg.get('discord_message_id')
            if msg_id is None:
                logging.error('No discord_message_id found in mesh response.')
                return

            node_descriptor = msg.get('node_descriptive_name')

            message = await self.channel.fetch_message(msg_id)

            # modify the original message
            e = message.embeds[0]
            e.color = util.MeshBotColors.TX_SENT()
            e.set_field_at(0, name='To Node', value=node_descriptor, inline=False)
            e.set_field_at(1, name='TX State', value='Sent', inline=False)
            await message.edit(embed=e)

        elif msg_type == 'TX_ERROR':

            logging.info(f'Response message: TX_ERROR received')

            msg_id = msg.get('discord_message_id')
            if msg_id is None:
                logging.error('No discord_message_id found in mesh response.')
                return

            error_text = msg.get('error_text')

            message = await self.channel.fetch_message(msg_id)

            # modify the original message
            e = message.embeds[0]
            e.color = util.MeshBotColors.error()
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
        logging.info('Discord client background task finished.')

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

    @staticmethod
    def deprecated_command(error_msg: str): # must pass allowed_channel_id as argument becaues this is compiled at import time, and you cannot pass self in
        def decorator(func):
            @wraps(func)
            async def wrapper(interaction: discord.Interaction, *args, **kwargs):
                logging.error(f'Deprecated command called: {interaction.command.name} in channel {interaction.channel_id}')
                desc = error_msg + f'\n\nOriginal command: `/{interaction.command.name} '
                if interaction.data.get('options'):
                    desc += ' '.join(str(option.get('value', '')) for option in interaction.data['options']) + '`'
                else:
                    desc += '`'
                embed = discord.Embed(
                    title='Deprecated Command',
                    description=desc,
                    color=util.MeshBotColors.error()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return await func(interaction, *args, **kwargs)
            return wrapper
        return decorator
