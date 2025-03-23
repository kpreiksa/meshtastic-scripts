import meshtastic
import meshtastic.serial_interface
import meshtastic.ble_interface
import datetime
import pandas as pd

# example node info

# ex = {
#     'num': 1128073664,
#     'user': {
#         'id': '!433d09c0',
#         'longName': 'Meshtastic 09c0',
#         'shortName': '09c0',
#         'hwModel': 'UNSET'
#     },
#     'position': {
#         'latitudeI': 425383066,
#         'longitudeI': -834888696,
#         'altitude': 285,
#         'locationSource': 'LOC_EXTERNAL',
#         'latitude': 42.5383066,
#         'longitude': -83.4888696
#     },
#     'snr': 6.25,
#     'lastHeard': 1742758283,
#     'hopsAway': 1
# }


def get_flat_nodeinfo(nodeinfo, update_timestamp):
    last_heard_ts = nodeinfo.get('lastHeard', 0)
    last_heard_time = datetime.datetime.fromtimestamp(last_heard_ts)
    last_heard_time_str = str(last_heard_time)
    
    update_time = datetime.datetime.fromtimestamp(update_timestamp)
    update_time_str = str(update_time)
    # these are in order of Google Sheet containing this info
    out = {
        'short_name': nodeinfo.get('user', {}).get('shortName', None),
        'long_name': nodeinfo.get('user', {}).get('longName', None),
        'node_num': nodeinfo.get('num', None),
        'user_id': nodeinfo.get('user', {}).get('id', None),
        'hwModel': nodeinfo.get('user', {}).get('hwModel', None),
        'approx_loc': '',
        'last_heard_time': last_heard_time_str,
        'last_heard_snr': nodeinfo.get('snr', 0),
        'last_heard_hops_away': nodeinfo.get('hopsAway', 1),
        'cur_pos_lat': nodeinfo.get('position', {}).get('latitude', None),
        'cur_pos_lon': nodeinfo.get('position', {}).get('longitude', None),
        'cur_pos_alt_m': nodeinfo.get('position', {}).get('altitude', None),
        'update_time': update_time_str,
        'update_cnt': 0,
    }
    
    return out

if __name__ == '__main__':

    # Automatically find device
    node_list = []
    
    dev = '␀_5777'
    
    # for serial:
    # interface = meshtastic.serial_interface.SerialInterface()
    
    print(f'Connecting to {dev}')
    with meshtastic.ble_interface.BLEInterface(address=dev) as interface:
        print(f'Retrieving Node List')
        node_list = interface.nodes
        print(f'Disconnecting from: {dev}')
        
    print(f'Disconnected from {dev}')
        
    nodes_flat = []
    update_ts = datetime.datetime.now().timestamp()
    
    for node_id, node in node_list.items():
        print(f'Processing Node: {node_id}')
        nodes_flat.append(get_flat_nodeinfo(node, update_ts))
        
    # TODO: Implement logic to update existing CSV
    
    # TODO: Integrate to google sheets
        
    # nodes_flat_dict = {x['user_id']: x for x in nodes_flat}
    # # read existing node_info.csv
    # old_node_list_df = pd.read_csv('node_info.csv')
    # old_node_list_records = old_node_list_df.to_dict('records')
    # old_node_list_dict = {x['user_id']: x for x in old_node_list_records}
    
    # for id, item in nodes_flat_dict.items():
    #     if id in old_node_list_dict:
    #         print('Found an existing node')
        
    node_list_df = pd.DataFrame(nodes_flat)
    node_list_df.to_csv('node_info.csv')
    