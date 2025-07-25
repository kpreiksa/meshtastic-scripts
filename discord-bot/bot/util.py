from datetime import datetime
import discord

def uptime_str(sec):
    if sec is None:
        return 'Not Available'
    
    days = sec // 86400
    sec_rem = sec - (days * 86400)
    hours = sec_rem // 3600
    sec_rem = sec_rem - (hours * 3600)
    min = sec_rem // 60
    sec_rem = sec_rem - (min * 60)
    
    out = ''
    
    if days > 0:
        out += f'{days} days, '
        
    if hours > 0:
        out += f'{hours} hours, '
        
    if min > 0:
        out += f'{min} minutes, '
        
    out += f'{sec_rem} seconds.'
    return out
        

class DiscordInteractionInfo():
    """
    Everything needed to uniquely identify a message for purposes of responding to it
    """
    def __init__(self, guild_id, channel_id, message_id, user_id=None, user_display_name=None, user_global_name=None, user_name=None, user_mention=None):
        self._guild_id = guild_id
        self._channel_id = channel_id
        self._message_id = message_id
        self._user_id = user_id
        self._user_display_name = user_display_name
        self._user_global_name = user_global_name
        self._user_name = user_name
        self._user_mention = user_mention
        
    @property
    def guild_id(self):
        return self._guild_id

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def message_id(self):
        return self._message_id
    
    @property
    def user_id(self):
        return self._user_id
    
    @property
    def user_display_name(self):
        return self._user_display_name
    
    @property
    def user_global_name(self):
        return self._user_global_name
    
    @property
    def user_name(self):
        return self._user_name
    
    @property
    def user_mention(self):
        return self._user_mention
    

def get_current_time_str():
    return datetime.now().strftime('%d %B %Y %I:%M:%S %p')

def time_from_ts(ts):
    return datetime.fromtimestamp(ts).strftime('%d %B %Y %I:%M:%S %p')

def time_str_from_dt(dt):
    return dt.strftime('%d %B %Y %I:%M:%S %p')
    
class MeshBotColors():
    _item_dict = {
        'green': 0x67ea94,
        'red': discord.Color.red(),
        'peach': 0xEA9467,
        'yellow': 0xFFCB61,
        'violet': 0x9467EA,
        'magenta': 0xEA67AD,
        'blue': 0x77BEF0,
        'white': 0xFFFFFF,
        'black': 0x000000,
    }

    @classmethod
    def _item_list(cls):
        return list(cls._item_dict.values())

    @classmethod
    def white(cls):
        return cls._item_dict['white']

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
