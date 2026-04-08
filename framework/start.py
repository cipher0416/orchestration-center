import os
import ssl
import sys

import uvicorn
from loguru import logger
from uvicorn import config

from common.cert.cert_validater import CertValidator
from common.log.audit_logger import audit_logger, OperationObject, OperationName, LogLevel, OperationResult
from common.util.cipher_converter import CipherConverter
from common.util.cipher_util import DEFAULT_ENCODING
from common.util.conf_util import conf_singleton_obj, set_ssl_folder_permissions, load_cert_password
from common.util.config_util import get_conf
from framework.server.frontend_support_server import app


def customized_create_ssl_context(certfile: str | os.PathLike[str],
                                  keyfile: str | os.PathLike[str] | None,
                                  password: str | None,
                                  ssl_version: int,
                                  cert_reqs: int,
                                  ca_certs: str | os.PathLike[str] | None,
                                  ciphers: str | None) -> ssl.SSLContext:
    try:
        ctx = ssl.SSLContext(ssl_version)
        get_password = (lambda: password) if password else None
        ctx.load_cert_chain(certfile, keyfile, get_password)
        ctx.verify_mode = ssl.VerifyMode(cert_reqs)
        if ca_certs:
            ctx.load_verify_locations(ca_certs)
            if len(conf_singleton_obj.get_crl_list()) > 0:
                ctx.load_verify_locations(conf_singleton_obj.ssl_crl_file)
                ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
        if ciphers:
            ctx.set_ciphers(ciphers)
        return  ctx
    except BaseException as e:
        logger.error(f"customized_create_ssl_context error: {e}")
        raise e

def get_user_info_from_env():
    user_info = {
        "username":os.environ.get("APP_USER", "unknown"),
        "uid":os.environ.get("APP_UID", "unknown"),
        "gid":os.environ.get("APP_GID", "unknown"),
    }
    return user_info


def record_startup_log():
    server_config = get_conf()
    audit_logger.audit({
        'object_name': OperationObject.SERVER,
        'operation_name': OperationName.START_SERVER,
        'level': LogLevel.DANGER,
        'result': OperationResult.SUCCESS,
        'details': {"ip": server_config.get('ip', ""), "port": server_config.get('port', "")},
        'user_name': get_user_info_from_env().get('username'),
    })


config.create_ssl_context = customized_create_ssl_context


class CustomUvicornServer:
    def __init__(self, server_config, conf_obj):
        self.server_config = server_config
        self.conf_obj = conf_obj

    def run(self):
        os.environ.setdefault("FORWARDED_ALLOW_IPS", self.server_config.get("forwarded_allow_ips"))
        server_config = uvicorn.Config(
            app=app,
            host=self.server_config.get('ip', "127.0.0.1"),
            port=int(self.server_config.get('port', 60000)),
            ssl_certfile=self.conf_obj.ssl_certfile,
            ssl_keyfile=self.conf_obj.ssl_keyfile,
            ssl_keyfile_password=load_cert_password(self.conf_obj.ssl_keyfile_password).decode(DEFAULT_ENCODING),
            ssl_ca_certs=self.conf_obj.ssl_ca_certs,
            ssl_cert_reqs=self.conf_obj.verify_client,
            ssl_ciphers=CipherConverter.convert(self.server_config.get("tls.cipher")),
            timeout_keep_alive=0,
            timeout_graceful_shutdown=int(self.server_config.get("connection.timeout", 30)),
            log_level="info",
            proxy_headers=True
        )
        server = uvicorn.Server(server_config)
        record_startup_log()
        server.run()


def main():
    server_config = get_conf()
    try:
        conf_obj = conf_singleton_obj
        result = CertValidator(conf_obj).validate()
        if not result.is_valid:
            sys.exit(result.message)
        set_ssl_folder_permissions()
        server = CustomUvicornServer(server_config, conf_obj)
        server.run()
    except Exception as e:
        logger.error(f"server start failed {e}")
        audit_logger.audit({
            'object_name':OperationObject.SERVER,
            'operation_name':OperationName.START_SERVER,
            'level':LogLevel.DANGER,
            'result':OperationResult.FAILURE,
            'details':{"ip": server_config.get('ip', ""), "port": server_config.get('port', "")},
            'user_name':get_user_info_from_env().get('username'),
        })
        sys.exit(f"server start failed {e}")


if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("  PSOP 服务器接口")
    logger.info("=" * 50)
    logger.info("  POST /parse-pdf     -  上传 PDF 文件并解析")
    logger.info("  POST /plan          -  提交任务和步骤，获取规划结果")
    logger.info("")
    logger.info("  PSOP 管理接口:")
    logger.info("  GET  /psops         -  获取PSOP列表")
    logger.info("  GET  /psops/<id>    -  根据ID获取PSOP详情")
    logger.info("  POST /psops         -  保存PSOP")
    logger.info("  DELETE /psops/<id>  -  删除PSOP")
    logger.info("")
    logger.info("  AgentCard 管理接口:")
    logger.info("  GET  /agent-cards   -  获取全量AgentCard列表")
    logger.info("")
    logger.info("  意图生成接口:")
    logger.info("  POST /generate-from-intent - 根据自然语言意图生成PSOP")
    logger.info("  POST /retrieve-by-intent   - 根据自然语言意图检索PSOP")
    logger.info("")
    logger.info("  SSE执行接口:")
    logger.info("  GET  /rest/start_process_stream?psop_id=<id> - 启动PSOP执行并推送实时进展")
    logger.info("")
    logger.info("  详细文档请参考: PSOP_API_DOCUMENTATION.md")
    logger.info("=" * 50)
    main()