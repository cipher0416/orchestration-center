import os

from loguru import logger


def get_root_path():
    current_script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(current_script_path)
    root_path = os.path.dirname(os.path.dirname(script_dir))
    return root_path

def get_conf():
    config = {}
    root_path = get_root_path()
    base_config_path = os.path.join(root_path, "etc", "conf","server.conf")
    save_config_path = os.path.join(root_path, "etc", "conf","server.properties")
    load_configs(base_config_path, config)
    load_configs(save_config_path, config)
    return config


def load_configs(config_path, config):
    if not os.path.exists(config_path):
        logger.error(f"Error:The configuration file {config_path} does not exist")
        return
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if '#' in line:
                line = line[:line.index('#')].strip()
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                config[key.lower()] = value