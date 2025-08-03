import os
import logging
import json


class Config():

    class InterfaceInfo():
        def __init__(self, d):
            self._d = d

        def __repr__(self):
            return f'<class {self.__class__.__name__} {self.connection_descriptor}>.'

        @property
        def connection_descriptor(self):
            if self.interface_type == 'serial':
                return f'{self.interface_type}'
            elif self.interface_type == 'tcp':
                return f'{self.interface_type} Address:{self.interface_address} Port:{self.interface_port}'
            elif self.interface_type == 'ble':
                return f'{self.interface_type} Node:{self.interface_ble_node}'

        @property
        def interface_type(self):
            return self._d.get('method', 'serial')

        @property
        def interface_address(self):
            if self.interface_type == 'tcp':
                return self._d.get('address')
            else:
                logging.debug(f'interface_address is invalid for interface_type: {self.interface_type}')
                return None

        @property
        def interface_port(self):
            if self.interface_type == 'tcp':
                return self._d.get('port')
            else:
                logging.debug(f'interface_port is invalid for interface_type: {self.interface_type}')
                return None

        @property
        def interface_ble_node(self):
            if self.interface_type == 'ble':
                return self._d.get('ble_node')
            else:
                logging.debug(f'interface_ble_node is invalid for interface_type: {self.interface_type}')
                return None

    class DatabaseInfo():
        def __init__(self, d):
            self._d = d

        @property
        def db_type(self):
            return self._d.get('type', 'sqlite')

        @property
        def db_host(self):
            return self._d.get('host')

        @property
        def db_port(self):
            return self._d.get('port', '5432')

        @property
        def _db_username(self):
            return self._d.get('username')

        @property
        def _db_password(self):
            return self._d.get('password')

        @property
        def db_name(self):
            return self._d.get('db_name', 'mydatabase')

        @property
        def _db_connection_string(self):
            if self.db_type == 'sqlite':
                return f'sqlite:///{self.db_name}'
            elif self.db_type == 'postgres' or self.db_type == 'postgresql':
                return f'postgresql+psycopg2://{self._db_username}:{self._db_password}@{self.db_host}:{self.db_port}/{self.db_name}'
            else:
                raise ValueError(f'Unsupported database type: {self.db_type}')

    def __init__(self):
        self._config = self.load_config()

    def load_config(self, config_filepath=None):
        config = {}
        if not config_filepath:
            config_filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
        if os.path.exists(config_filepath):
            try:
                logging.info(f'Found config.json, attempting to load configuration.')
                with open(config_filepath, "r") as config_file:
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
        # database info
        DATABASE_TYPE = os.environ.get('DB_TYPE', 'sqlite')  # sqlite or postgresql/postgres
        DB_HOST = os.environ.get('DB_HOST')
        DB_PORT = os.environ.get('DB_PORT', '5432')  # Default is 5432
        DB_USERNAME = os.environ.get('DB_USERNAME')
        DB_PASSWORD = os.environ.get('DB_PASSWORD')
        DB_NAME = os.environ.get('DB_NAME', 'mydatabase')  # Default is mydatabase

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
            },
            'database_info':
            {
                'type': DATABASE_TYPE,
                'host': DB_HOST,
                'port': DB_PORT,
                'user': DB_USERNAME,
                'password': DB_PASSWORD,
                'db_name': DB_NAME
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
    def gmaps_api_key(self):
        return self._config.get('gmaps_api_key')

    @property
    def discord_channel_id(self):
        return self._config.get('discord_channel_id')

    @property
    def time_zone(self):
        return self._config.get('time_zone')

    @property
    def channel_names(self):
        return self._config.get('channel_names', {})

    @property
    def interface_info(self):
        return Config.InterfaceInfo(self._config.get('interface_info', {}))

    @property
    def database_info(self):
        return Config.DatabaseInfo(self._config.get('database_info', {}))
