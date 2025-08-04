class NodeUserInfo():
    def __init__(self, user_dict):
        self._user_dict = user_dict
        
    def __repr__(self):
        return f'<Class {self.__class__.__name__}>.'
        
    @property
    def user_id(self):
        return self._user_dict.get('id')
    
    @property
    def short_name(self):
        return self._user_dict.get('shortName')
    
    @property
    def long_name(self):
        return self._user_dict.get('longName')
    
    @property
    def mac_address(self):
        return self._user_dict.get('macaddr')
    
    @property
    def hw_model(self):
        return self._user_dict.get('hwModel')
    
class NodePositionInfo():
    def __init__(self, position_dict):
        self._position_dict = position_dict
        
    def __repr__(self):
        return f'<Class {self.__class__.__name__}>.'
        
    @property
    def latitude(self):
        return self._position_dict.get('latitude')
    
    @property
    def longitude(self):
        return self._position_dict.get('longitude')
    
class NodeDeviceMetrics():
    def __init__(self, device_metrics_dict):
        self._device_metrics_dict = device_metrics_dict
        
    def __repr__(self):
        return f'<Class {self.__class__.__name__}>.'
        
    @property
    def battery_level(self):
        return self._device_metrics_dict.get('batteryLevel')
    
    @property
    def voltage(self):
        return self._device_metrics_dict.get('voltage')
    
class MeshNode():
    def __init__(self, node_dict):
        self._node_dict = node_dict
    
    def __repr__(self):
        return f'<Class {self.__class__.__name__}>.'
        
    @property
    def user_info(self):
        return NodeUserInfo(self._node_dict.get('user', {}))
    
    @property
    def position_info(self):
        return NodePositionInfo(self._node_dict.get('position', {}))
    
    @property
    def device_metrics(self):
        return NodeDeviceMetrics(self._node_dict.get('deviceMetrics', {}))
        
    @property
    def node_num(self):
        return self._node_dict.get('num')
    
    @property
    def node_num_str(self):
        return str(self._node_dict.get('num'))
    
    @property
    def last_heard(self):
        return self._node_dict.get('lastHeard')
    
    # nodenum
    
    # short_name
    
    # long_name
    
    def update_db(self):
        # write it to db if it doesn't exist... if it does, update it
        # based on criteria... i.e. newest wins
        pass
 
