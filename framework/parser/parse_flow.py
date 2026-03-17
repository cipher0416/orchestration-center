import fitz
from loguru import logger
from pathlib import Path
from typing import Optional

from common.llm.config.llm_config import LLMType, get_llm_config_by_type
from common.llm.provider.llm_provider_registry import get_or_create_llm_instance


class PDFParsingError(Exception):
    pass


class ChapterNotFoundError(PDFParsingError):
    pass


class SolutionPackageParser:
    def __init__(self, llm_type: LLMType = LLMType.QWEN3_32B):
        self.llm_type = llm_type

    @staticmethod
    def find_chapter_range(doc, chapter_title: str) -> tuple:
        start = None
        end = doc.page_count
        for level, title, page in doc.get_toc():
            if title == chapter_title:
                start = page
            elif start is not None and level <= 1:
                end = page
                break
        return start, end

    @staticmethod
    def extract_text(doc, start: int, end: int) -> str:
        pages = range(start - 1, min(end, doc.page_count) - 1)
        return '\n'.join(doc[i].get_text() for i in pages)

    @staticmethod
    def build_markdown_prompt(chapter_text: str) -> str:
        return f"""
请将以下 PDF 章节文本转换为规范的 Markdown 格式。要求：
1. 保持原文的层级结构，使用适当的标题标记(# ## ###等)
2. 识别并格式化：
    - 章节标题用 # 或 ## 标记
    - 列表项用 - 或 1. 标记
    - 表格转化为 Markdown 表格格式
3. 保留所有原文内容，不要删减
保持段落结构，用空行分隔不同段落
如果遇到图表，用[图表：描述]的形式标注
忽略页眉页脚，如文档标题、版权信息、页码标记、公司 logo 或品牌文字
只输出转换后的 格式文本，不要有其他内容。
请输出翻译后的中文。注意将"Agent"翻译为智能体。

以下是需要转换的文本内容：
{chapter_text}
"""

    def get_chapter_text(self, pdf_path: str, chapter_title: str) -> str:
        path = Path(pdf_path)
        if not path.exists():
            raise PDFParsingError(f'PDF file does not exist： {pdf_path}')
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            raise PDFParsingError(f"Cannot open pdf file: {e}") from e
        try:
            start, end = self.find_chapter_range(doc, chapter_title)
            if start is None:
                raise ChapterNotFoundError(f"Chapter not found: {chapter_title}")
            return self.extract_text(doc, start, end)
        finally:
            doc.close()

    def convert_to_markdown(self, chapter_text: str) -> str:
        if not chapter_text or not chapter_text.strip():
            raise PDFParsingError(f'Chapter text is empty')
        prompt = self.build_markdown_prompt(chapter_text)
        try:
            llm = get_or_create_llm_instance(get_llm_config_by_type(self.llm_type))
            _, res = llm.ask_llm(prompt)
            return res
        except Exception as e:
            raise PDFParsingError(f"LLM conversion failed: {e}") from e

    def parse_pdf_chapter(self, pdf_path: str, chapter_title: str) -> Optional[str]:
        try:
            chapter_text = self.get_chapter_text(pdf_path, chapter_title)
            return self.convert_to_markdown(chapter_text)
        except PDFParsingError:
            return None


if __name__ == '__main__':
    parser = SolutionPackageParser()
    try:
        result = parser.parse_pdf_chapter(
            "IG1526A_AN_L4_Wireless_Energy_Efficiency_Optimization_Solution_Package_v1.0.0.pdf",
            "5. Interaction Flow"
        )
        if result:
            logger.info(result)
        else:
            logger.info("parsing failed")
    except Exception as e:
        logger.info(f"Error: {e}")
