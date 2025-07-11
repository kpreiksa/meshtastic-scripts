from datetime import datetime

def get_current_time_str():
    return datetime.now().strftime('%d %B %Y %I:%M:%S %p')

def time_from_ts(ts):
    return datetime.fromtimestamp(ts).strftime('%d %B %Y %I:%M:%S %p')
