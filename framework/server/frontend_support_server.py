import os
import ssl
import sys
import tempfile
import json

import uvicorn
from a2a.types import AgentCard
from flask import Flask, request, jsonify, Response, stream_with_context
from loguru import logger
from flask_cors import CORS
from uvicorn import config

from common.cert.cert_validater import CertValidator
from common.util.cipher_converter import CipherConverter
from common.util.cipher_util import DEFAULT_ENCODING
from common.util.conf_util import conf_singleton_obj, set_ssl_folder_permissions, load_cert_password
from common.util.config_util import get_conf
from framework.orchestration.model.preflow import PreFlow
from framework.orchestration.model.psop import PSOP
from framework.orchestration.psop_generator import PsopGenerator
from framework.orchestration.intent_psop_generator import IntentPsopGenerator
from framework.orchestration.persistence import WorkflowStorage
from framework.orchestration.retrieval import WorkflowRetrieval
from framework.solution_package.parse_flow import SolutionPackageParser
from framework.agentcard_lib import AgentCardLib
from framework.runtime.exec_engine import DynamicWorkflowEngine

app = Flask(__name__)
CORS(app)

storage = WorkflowStorage()
retrieval = WorkflowRetrieval(storage)
agent_lib = AgentCardLib()


@app.route('/parse-pdf', methods=['POST'])
def parse_pdf():
    if 'file' not in request.files:
        return jsonify({'error': '未提供文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "文件名为空"}), 400
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "仅支持 PDF 文件"}), 400
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        file.save(tmp.name)
        tmp_file_path = tmp.name

    try:
        parser = SolutionPackageParser()
        pre_md = parser.parse_pdf_chapter(
            tmp_file_path,
            "5. Interaction Flow"
        )
        if not pre_md:
            return jsonify({"error": "PDF解析失败，未找到指定章节"}), 400

        preflow = PreFlow(
            name=file.filename,
            description=f"从PDF文件 {file.filename} 解析的工作流",
            steps_md=pre_md
        )
        return {
            "status": "success",
            "message": "PDF文件解析成功",
            "content": preflow.model_dump_json()
        }, 200
    except Exception as e:
        return jsonify({"error": f"解析失败：{str(e)}"}), 500
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


@app.route('/plan', methods=['POST'])
def plan():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体为空"}), 400
        preflow_dict = data.get("preflow")
        agent_cards_list = data.get("agent_cards")

        if not preflow_dict or not agent_cards_list:
            return jsonify({
                "error": "缺少必要字段: task 和 steps 必须提供"
            }), 400
        generator = PsopGenerator()
        workflow = generator.generate_psop_workflow(PreFlow.model_validate(preflow_dict),
                                                    [AgentCard.model_validate(card) for card in agent_cards_list])
        storage.save_psop(workflow)

        return jsonify({
            "status": "success",
            "data": workflow.model_dump_json()
        }), 200
    except Exception as e:
        return jsonify({"error": f"规划失败 : {str(e)}"}), 500


@app.route('/psops', methods=['GET'])
def get_all_psops():
    try:
        limit = request.args.get('limit', default=10, type=int)
        workflow_type = request.args.get('workflow_type', default='psop', type=str)

        recent_workflows = retrieval.list_recent_workflows(limit=limit, workflow_type=workflow_type)

        return jsonify({
            "status": "success",
            "count": len(recent_workflows),
            "data": [wf.to_dict() for wf in recent_workflows]
        }), 200
    except Exception as e:
        return jsonify({"error": f"获取PSOP列表失败: {str(e)}"}), 500


@app.route('/psops/<workflow_id>', methods=['GET'])
def get_psop_by_id(workflow_id):
    try:
        psop = retrieval.get_psop_by_id(workflow_id)
        if not psop:
            return jsonify({"error": f"未找到ID为 {workflow_id} 的PSOP"}), 404

        return jsonify({
            "status": "success",
            "data": psop.model_dump()
        }), 200
    except Exception as e:
        return jsonify({"error": f"获取PSOP详情失败: {str(e)}"}), 500


@app.route('/psops', methods=['POST'])
def save_psop():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体为空"}), 400

        psop = PSOP.model_validate(data)
        saved_id = storage.save_psop(psop)

        return jsonify({
            "status": "success",
            "message": "PSOP保存成功",
            "workflow_id": saved_id
        }), 201
    except Exception as e:
        return jsonify({"error": f"保存PSOP失败: {str(e)}"}), 500


@app.route('/psops/<workflow_id>', methods=['DELETE'])
def delete_psop(workflow_id):
    """
    删除指定ID的PSOP工作流。
    
    路径参数:
        workflow_id: PSOP的唯一标识符
    
    返回:
        成功: 200 OK
        失败: 404 Not Found 或 500 Internal Server Error
    """
    try:
        # 先检查PSOP是否存在
        psop = retrieval.get_psop_by_id(workflow_id)
        if not psop:
            return jsonify({"error": f"未找到ID为 {workflow_id} 的PSOP"}), 404

        # 删除PSOP
        deleted = storage.delete_psop(workflow_id)
        if not deleted:
            return jsonify({"error": f"删除PSOP失败: 文件可能不存在"}), 500

        return jsonify({
            "status": "success",
            "message": f"PSOP {workflow_id} 删除成功"
        }), 200
    except Exception as e:
        return jsonify({"error": f"删除PSOP失败: {str(e)}"}), 500


@app.route('/agent-cards', methods=['GET'])
def get_all_agent_cards():
    """
    获取全量AgentCard列表。
    
    逻辑：
    1. 读取配置文件 config/agent_cards.yaml
    2. 如果配置文件中包含 source_url 字段，则从该URL获取AgentCard
    3. 否则，使用配置文件中的 agents 字段
    
    Returns:
        JSON响应，包含AgentCard列表和来源信息
    """
    try:
        # 获取所有AgentCard
        agent_cards = agent_lib.get_all_agent_cards()

        # 将AgentCard转换为字典格式
        agent_cards_data = []
        for card in agent_cards:
            card_dict = card.model_dump()
            agent_cards_data.append(card_dict)

        return jsonify({
            "status": "success",
            "count": len(agent_cards_data),
            "data": agent_cards_data
        }), 200

    except FileNotFoundError as e:
        return jsonify({
            "error": f"配置文件不存在: {str(e)}"
        }), 404
    except ValueError as e:
        return jsonify({
            "error": f"数据格式错误: {str(e)}"
        }), 400
    except Exception as e:
        return jsonify({
            "error": f"获取AgentCard失败: {str(e)}"
        }), 500


@app.route('/generate-from-intent', methods=['POST'])
def generate_psop_from_intent():
    """
    根据自然语言意图生成PSOP工作流。
    
    请求体格式:
    {
        "user_intent": "自然语言描述的业务意图",
        "workflow_name": "可选的工作流名称"
    }
    
    返回:
        JSON响应，包含生成的PSOP工作流
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体为空"}), 400

        user_intent = data.get("user_intent")
        workflow_name = data.get("workflow_name")

        if not user_intent:
            return jsonify({"error": "缺少必要字段: user_intent"}), 400

        # 获取AgentCards（复用agent-cards接口的逻辑）
        agent_cards = agent_lib.get_all_agent_cards()
        if not agent_cards:
            return jsonify({"error": "未找到可用的AgentCard"}), 404

        # 使用IntentPsopGenerator生成PSOP
        generator = IntentPsopGenerator()
        psop = generator.generate_psop_from_intent(
            user_intent=user_intent,
            agent_cards=agent_cards,
            workflow_name=workflow_name
        )

        # 可选：自动保存生成的PSOP
        try:
            storage.save_psop(psop)
        except Exception as save_error:
            logger.warning(f"PSOP保存失败（不影响返回）: {save_error}")

        return jsonify({
            "status": "success",
            "message": "PSOP生成成功",
            "data": psop.model_dump()
        }), 200

    except Exception as e:
        logger.error(f"根据意图生成PSOP失败: {e}")
        return jsonify({"error": f"生成PSOP失败: {str(e)}"}), 500


@app.route('/retrieve-by-intent', methods=['POST'])
def retrieve_psop_by_intent():
    """
    根据自然语言意图检索最合适的PSOP工作流。
    
    请求体格式:
    {
        "user_intent": "自然语言描述的业务意图"
    }
    
    返回:
        JSON响应，包含检索到的PSOP工作流或错误信息
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体为空"}), 400

        user_intent = data.get("user_intent")

        if not user_intent:
            return jsonify({"error": "缺少必要字段: user_intent"}), 400

        logger.info(f"开始根据意图检索PSOP: {user_intent}")

        # 使用WorkflowRetrieval的retrieve_psop_by_intent方法
        psop = retrieval.retrieve_psop_by_intent(user_intent)

        if not psop:
            return jsonify({
                "status": "success",
                "message": "未找到匹配的PSOP",
                "data": None
            }), 200

        logger.info(f"成功检索到PSOP: {psop.name} (ID: {psop.id})")

        return jsonify({
            "status": "success",
            "message": "PSOP检索成功",
            "data": psop.model_dump()
        }), 200

    except Exception as e:
        logger.error(f"根据意图检索PSOP失败: {e}")
        return jsonify({"error": f"检索PSOP失败: {str(e)}"}), 500


# SSE事件队列用于存储推送事件
sse_events = {}


@app.route('/rest/start_process_stream', methods=['GET'])
def start_process_stream():
    psop_id = request.args.get('psop_id')
    if not psop_id:
        return jsonify({"error": "缺少psop_id参数"}), 400

    psop = retrieval.get_psop_by_id(psop_id)
    if not psop:
        return jsonify({"error": f"未找到ID为 {psop_id} 的PSOP"}), 404

    agent_cards = agent_lib.get_all_agent_cards()
    if not agent_cards:
        return jsonify({"error": "未找到可用的AgentCard"}), 404

    def generate():
        import asyncio
        import threading
        import queue

        event_queue = queue.Queue()

        def push_callback(event_type: str, data: dict):
            try:
                # 序列化数据，处理无法JSON序列化的对象
                serializable_data = {}
                for key, value in data.items():
                    if hasattr(value, 'model_dump'):
                        # 如果是Pydantic模型，使用model_dump()
                        serializable_data[key] = value.model_dump()
                    elif hasattr(value, '__dict__'):
                        # 如果是普通对象，尝试转换为字典
                        try:
                            serializable_data[key] = value.__dict__
                        except:
                            serializable_data[key] = str(value)
                    elif isinstance(value, (tuple, list)):
                        # 处理列表和元组
                        serializable_data[key] = []
                        for item in value:
                            if hasattr(item, 'model_dump'):
                                serializable_data[key].append(item.model_dump())
                            elif hasattr(item, '__dict__'):
                                try:
                                    serializable_data[key].append(item.__dict__)
                                except:
                                    serializable_data[key].append(str(item))
                            else:
                                serializable_data[key].append(item)
                    else:
                        serializable_data[key] = value

                event_data = {
                    "type": event_type,
                    "data": serializable_data,
                    "timestamp": asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
                }
                event_queue.put(event_data)
            except Exception as e:
                logger.error(f"推送事件到队列失败: {e}")

        async def run_workflow_async():
            try:
                engine = DynamicWorkflowEngine(psop, agent_cards)
                engine.set_push_callback(push_callback)

                event_queue.put({
                    "type": "start",
                    "data": {"psop_id": psop_id, "message": "开始执行工作流"}
                })

                execution_history = await engine.run()

                event_queue.put({
                    "type": "complete",
                    "data": {"psop_id": psop_id, "execution_history": execution_history}
                })

            except Exception as e:
                logger.error(f"工作流执行失败: {e}")
                event_queue.put({
                    "type": "error",
                    "data": {"psop_id": psop_id, "error": str(e)}
                })

        def run_workflow():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(run_workflow_async())
            finally:
                loop.close()

        workflow_thread = threading.Thread(target=run_workflow)
        workflow_thread.daemon = True
        workflow_thread.start()

        yield f"data: {json.dumps({'type': 'init', 'data': {'psop_id': psop_id, 'message': '初始化执行引擎'}})}\n\n"

        while workflow_thread.is_alive() or not event_queue.empty():
            try:
                event = event_queue.get(timeout=1)
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"处理事件失败: {e}")

        yield "event: close\ndata: {}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


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
