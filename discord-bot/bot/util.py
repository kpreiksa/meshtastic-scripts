from datetime import datetime
import discord

class DiscordInteractionInfo():
    """
    Everything needed to uniquely identify a message for purposes of responding to it
    """
    def __init__(self, guild_id, channel_id, message_id):
        self._guild_id = guild_id
        self._channel_id = channel_id
        self._message_id = message_id
        
    @property
    def guild_id(self):
        return self._guild_id
    
    @property
    def channel_id(self):
        return self._channel_id
    
    @property
    def message_id(self):
        return self._message_id

def get_current_time_str():
    return datetime.now().strftime('%d %B %Y %I:%M:%S %p')

def time_from_ts(ts):
    return datetime.fromtimestamp(ts).strftime('%d %B %Y %I:%M:%S %p')

class MeshBotColors():
    _item_dict = {
        'green': 0x67ea94,
        'red': discord.Color.red(),
        'peach': 0xEA9467,
        'yellow': 0xFFCB61,
        'violet': 0x9467EA,
        'magenta': 0xEA67AD,
        'blue': 0x77BEF0
    }

    @classmethod
    def _item_list(cls):
        return list(cls._item_dict.values())

    @classmethod
    def green(cls):
        return cls._item_dict['green']

    @classmethod
    def red(cls):
        return cls._item_dict['red']

    @classmethod
    def peach(cls):
        return cls._item_dict['peach']

    @classmethod
    def violet(cls):
        return cls._item_dict['violet']

    @classmethod
    def magenta(cls):
        return cls._item_dict['magenta']

    @classmethod
    def available_colors(cls):
        return list(cls._item_dict.keys())

    @classmethod
    def RX(cls):
        return cls._item_dict['blue']

    @classmethod
    def error(cls):
        return cls._item_dict['red']
    
    @classmethod
    def TX_PENDING(cls):
        return cls._item_dict['peach']
    
    @classmethod
    def TX_SENT(cls):
        return cls._item_dict['yellow']
    
    @classmethod
    def TX_ACK(cls):
        return cls._item_dict['green']
