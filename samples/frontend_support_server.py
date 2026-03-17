import os
import tempfile

from a2a.types import AgentCard
from flask import Flask, request, jsonify
from loguru import logger

from framework.orchestration.model.preflow import PreFlow
from framework.orchestration.psop_generator import PsopGenerator
from framework.parser.parse_flow import SolutionPackageParser

app = Flask(__name__)


@app.route('/parse-pdf', methods=['POST'])
def parse_pdf():
    if 'file' not in request.files:
        return jsonify({'error': '未提供文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "文件名为空"}), 400
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "仅支持 PDF 文件"}), 400
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        file.save(tmp.name)
        tmp_file_path = tmp.name

    try:
        parser = SolutionPackageParser()
        pre_md = parser.parse_pdf_chapter(
            tmp_file_path,
            "5. Interation Flow"
        )
        preflow = PreFlow(
            name=file.filename,
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
        return jsonify({
            "status": "success",
            "data": workflow.model_dump_json()
        }), 200
    except Exception as e:
        return jsonify({"error": f"规划失败 : {str(e)}"}), 500


if __name__ == '__main__':
    logger.info("  POST /parse-pdf  -  上传 PDF 文件并解析")
    logger.info("  POST /plan        -  提交任务和步骤，获取规划结果")
    app.run(host='0.0.0.0', port=6000, debug=True)
