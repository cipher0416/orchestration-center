import json
import os


def read_config_as_json(file_name):
    current_dir = os.path.dirname(__file__)
    grandparent_path = os.path.dirname(current_dir)
    dir_path = os.path.join(grandparent_path, '')
    file_path = os.path.join(dir_path, file_name)
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
