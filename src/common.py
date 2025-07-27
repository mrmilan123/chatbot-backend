from json import loads

def get_config(key):
    try:
        return loads(open("./config/config.json").read())[key]
    except KeyError as e:
        return None