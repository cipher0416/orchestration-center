import configparser
import os.path
import platform
import stat

from loguru import logger

from common.util import cipher_util
from common.util.conf_obj import ConfObj
from common.util.constant_param import SSL_PATH, CONFIG_FILE_PATH


def load_conf_as_dict(conf_file: str) -> dict:
    config = configparser.ConfigParser()
    try:
        with open(conf_file, "r", encoding='utf-8') as f:
            config.read_string('[DEFAULT]\n' + f.read())
            return dict(config['DEFAULT'])
    except Exception as e:
        logger.error(f"load config failed, {e}")
        return {}


def load_conf_object(conf_file: str) -> ConfObj:
    config_dict = load_conf_as_dict(conf_file)
    return ConfObj.as_object(config_dict)


def load_cert_password(password_path: str) -> bytes:
    if not os.path.exists(password_path):
        return b''
    with open(password_path, 'r', encoding='utf-8') as f:
        str_content = f.read().strip()
        return cipher_util.decrypt(str_content)


def set_ssl_folder_permissions():
    if platform.system().lower() != "linux":
        logger.info(f"current system type is: {platform.system().lower()}")
    os.chmod(SSL_PATH, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    for root, _, files in os.walk(SSL_PATH):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)

conf_singleton_obj = load_conf_object(CONFIG_FILE_PATH)
