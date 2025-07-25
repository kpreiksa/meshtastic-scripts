


nodes_pos = {key:value for key,value in nodes.items() if value.get('position')}
longnames = ['cf - Ryo B','cf - Supreme','raktenna-b','cf - Ryobi 2.0','Cali Node G','rak-city-b']

def get_id_from_longname(longname, nodes_pos):
    nodes = [key for key, value in nodes_pos.items() if value.get('user').get('longName') == longname]
    return nodes[0] if nodes else None

coords = []

for longname in longnames:
    node_id = get_id_from_longname(longname, nodes_pos)
    if node_id:
        coords.append({'name': longname, 'lat': nodes_pos[node_id]['position']['latitude'], 'lon': nodes_pos[node_id]['position']['longitude']})
    else:
        print(f"Node with long name '{longname}' not found.")


m = folium.Map(location=map_center, zoom_start=12)

for point in coords:
    folium.Marker(location=[point['lat'],point['lon']], popup=point['name'], tooltip=point['name']).add_to(m)

m.save('map.html')
