import sys
import os
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import datetime
import pprint


sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot'))

from db_classes import TXPacket, RXPacket, ACK, MeshNodeDB, discord_bot_id
from config_classes import Config
import db_base

config = Config()
db_info = config.database_info

# Setup database connection
DATABASE_URL = db_info._db_connection_string
engine = create_engine(DATABASE_URL)
db_base.Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# get the unique publisher_mesh_node_nums

all_nodes = session.query(RXPacket.publisher_mesh_node_num).distinct().all()

node_list = [x[0] for x in all_nodes]

# for node in node_list:
#     print(f'Performing query for node: {node}')
    
#     # get unique src_nums
#     src_nodes = session.query(MeshNodeDB).filter(MeshNodeDB.publisher_mesh_node_num == node).all()
    
#     for src_node in src_nodes:
#         hr_ago_24 = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
#         cnt_packets_24_hr = session.query(RXPacket.id).filter(RXPacket.src_num == src_node.node_num).filter(RXPacket.ts >= hr_ago_24).filter(RXPacket.publisher_mesh_node_num == node).count()
#         cnt_packets = session.query(RXPacket.id).filter(RXPacket.src_num == src_node.node_num).filter(RXPacket.publisher_mesh_node_num == node).count()
#         print(f'{src_node.short_name} ({src_node.user_id}) - {cnt_packets} packets ({cnt_packets_24_hr} in past 24 hours)')
#     print('')
    
for node in node_list:
    print(f'Performing query for node: {node}')
    
    # get all RXPackets
    hr_ago_24 = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    
    node_db = session.query(MeshNodeDB).filter(MeshNodeDB.publisher_mesh_node_num == node).all()
    
    rx_by_node = session.query(RXPacket.src_num, func.count(RXPacket.id)).filter(RXPacket.publisher_mesh_node_num == node).group_by(RXPacket.src_num).all()
    rx_by_node_past_24_hr = session.query(RXPacket.src_num, func.count(RXPacket.id)).filter(RXPacket.publisher_mesh_node_num == node).filter(RXPacket.ts >= hr_ago_24).group_by(RXPacket.src_num).all()
    
    all_src_nodes = [x[0] for x in rx_by_node]
    node_dict = {}
    for src_node in all_src_nodes:
        node_obj = [x for x in node_db if x.node_num == src_node]
        cnt_rx_by_node = [x[1] for x in rx_by_node if x[0] == src_node][0]
        match_rx_by_node_past_24_hr = [x[1] for x in rx_by_node_past_24_hr if x[0] == src_node]
        if len(match_rx_by_node_past_24_hr) == 1:
            cnt_rx_by_node_past_24_hr = match_rx_by_node_past_24_hr[0]
        elif len(match_rx_by_node_past_24_hr) == 0:
            cnt_rx_by_node_past_24_hr = 0
        else:
            print('ERROR')
        node_dict[src_node] = {
            'node_obj': node_obj,
            'cnt': cnt_rx_by_node,
            'cnt_24_hr': cnt_rx_by_node_past_24_hr,
        }
        

    pprint.pprint(node_dict)
            
