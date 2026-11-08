"""
统一文档解析服务
自动选择百度教育OCR、MinerU、视觉模型进行文档解析

策略:
- PDF文档 → MinerU优先
- 图片/试卷/答题卡 → 百度教育OCR优先，失败降级视觉模型
- 混合内容 → OCR + MinerU组合
"""
import os
import sys
import base64
import tempfile
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))



class DocumentParseService:
    """
    统一文档解析服务 - 自动选择OCR/MinerU/视觉模型
    """

    def __init__(self):
        from app.services.ocr_service import OCRService
        from app.services.llm_service import LLMService

        self.ocr_service = OCRService()
        self.llm_service = LLMService()
        self.mineru_client = self._try_init_mineru()

    def _try_init_mineru(self):
        """尝试初始化MinerU客户端"""
        try:
            from chem_skills.chemistry_parser.mineru_client import get_mineru_client
            return get_mineru_client()
        except Exception as e:
            print(f"[MinerU] Init failed: {e}")
            return None

    def _is_mineru_actually_available(self) -> bool:
        """检测 MinerU 是否真正可用（不仅仅是代码存在）"""
        if self.mineru_client is None:
            return False
        # 简单检查：模型目录是否有内容
        import os as _os
        home = _os.path.expanduser("~")
        cache_dirs = [
            _os.path.join(home, ".cache", "modelscope", "hub"),
            _os.path.join(home, ".cache", "huggingface", "hub"),
            _os.path.join(home, ".mineru", "models"),
        ]
        for d in cache_dirs:
            if _os.path.exists(d) and any(_os.scandir(d)):
                return True
        # 模型未下载，标记为不可用
        print("[MinerU] Models not downloaded — MinerU unavailable")
        return False

    def check_services_status(self) -> Dict[str, Any]:
        """
        检测所有解析服务可用性
        """
        baidu_key = os.getenv("BAIDU_OCR_API_KEY", "")
        baidu_secret = os.getenv("BAIDU_OCR_SECRET_KEY", "")
        mineru_available = self._is_mineru_actually_available()
        vision_available = bool(os.getenv("ZHIPU_API_KEY", "") or os.getenv("XIAOMI_API_KEY", ""))

        return {
            "ocr": {
                "available": bool(baidu_key and baidu_secret),
                "provider": "baidu",
                "note": "百度教育产品OCR" if (baidu_key and baidu_secret) else "未配置百度OCR密钥",
            },
            "mineru": {
                "available": mineru_available,
                "note": "MinerU CLI 就绪" if mineru_available else "MinerU 模型未下载，需先下载模型",
            },
            "vision": {
                "available": vision_available,
                "provider": "glm-4v/mimo",
                "note": "多模态Vision降级" if vision_available else "未配置Vision模型",
            },
        }

    def parse_document(
        self,
        file_data: bytes,
        file_type: str,
        source: str = "auto"
    ) -> Dict[str, Any]:
        """
        自动选择解析方式

        Args:
            file_data: 文件内容(字节)
            file_type: 文件类型 ("pdf", "image", "auto")
            source: 解析源 ("ocr", "mineru", "vision", "auto")

        Returns:
            {
                "success": bool,
                "provider": str,  # "ocr", "vision", "mineru", "none"
                "result": dict,
                "fallback_used": bool,
                "error": str (如果有)
            }
        """
        # 判定文件类型
        if file_type == "auto":
            file_type = self._detect_file_type(file_data)

        # 根据source参数选择解析方式
        if source == "auto":
            if file_type == "pdf":
                return self._parse_pdf(file_data)
            elif file_type == "docx":
                return self._parse_docx(file_data)
            elif file_type == "pptx":
                return self._parse_pptx(file_data)
            else:
                return self._parse_image(file_data)
        elif source == "ocr":
            return self._parse_image_with_ocr(file_data)
        elif source == "mineru":
            if file_type == "docx":
                return self._parse_docx(file_data)
            elif file_type == "pptx":
                return self._parse_pptx(file_data)
            return self._parse_pdf(file_data)
        elif source == "vision":
            return self._parse_image_with_vision(file_data)
        else:
            return {
                "success": False,
                "provider": "none",
                "error": f"未知的解析源: {source}",
                "fallback_used": False
            }

    def _detect_file_type(self, file_data: bytes) -> str:
        """通过文件头检测文件类型"""
        # PDF 文件头: 25 50 44 46 (%PDF)
        if file_data[:4] == b'%PDF':
            return "pdf"

        # JPEG: FF D8 FF
        if file_data[:3] == b'\xFF\xD8\xFF':
            return "image"

        # PNG: 89 50 4E 47
        if file_data[:4] == b'\x89PNG':
            return "image"

        # GIF: 47 49 46 38
        if file_data[:4] == b'GIF8':
            return "image"

        # Word (.docx) / PPTX (.pptx) / Excel (.xlsx) 都是ZIP格式: 50 4B 03 04
        # 需要进一步检测子类型
        if file_data[:4] == b'PK\x03\x04':
            # 检测是否为DOCX (Word文档)
            # DOCX本质上是一个ZIP，包含 word/document.xml
            try:
                import zipfile
                import io
                with zipfile.ZipFile(io.BytesIO(file_data[:1024])) as zf:
                    names = zf.namelist()
                    if 'word/document.xml' in names:
                        return "docx"
                    elif 'ppt/presentation.xml' in names:
                        return "pptx"
                    elif 'xl/workbook.xml' in names:
                        return "xlsx"
            except Exception:
                pass

        # 默认按图片处理
        return "image"

    def _parse_image(self, image_data: bytes) -> Dict[str, Any]:
        """
        图片解析: OCR → 视觉模型降级

        流程:
        1. 尝试OCR识别
        2. 如果OCR失败或置信度低，尝试视觉模型
        3. 返回最佳结果
        """
        # Step 1: 尝试OCR
        ocr_result = self.ocr_service.recognize_answer_sheet(image_data)

        # OCR成功且置信度高，直接返回
        if ocr_result.get("success") and not ocr_result.get("is_partial"):
            confidence = ocr_result.get("confidence", 0)
            if confidence >= 0.85:
                return {
                    "success": True,
                    "provider": "ocr",
                    "result": ocr_result,
                    "fallback_used": False
                }

        # Step 2: OCR失败或置信度低，尝试视觉模型
        vision_result = self._try_vision_parse(image_data)

        if vision_result.get("success"):
            return {
                "success": True,
                "provider": "vision",
                "result": vision_result.get("result"),
                "fallback_used": True,
                "original_ocr": ocr_result if not ocr_result.get("success") else None
            }

        # Step 3: 视觉模型也失败，返回OCR原始结果（可能是部分识别）
        return {
            "success": ocr_result.get("success", False),
            "provider": "ocr-partial" if ocr_result.get("is_partial") else "ocr",
            "result": ocr_result,
            "fallback_used": False,
            "warning": "识别置信度较低，请老师在预览页面确认"
        }

    def _parse_image_with_ocr(self, image_data: bytes) -> Dict[str, Any]:
        """仅使用OCR解析图片"""
        result = self.ocr_service.recognize_answer_sheet(image_data)
        return {
            "success": result.get("success", False),
            "provider": "ocr",
            "result": result,
            "fallback_used": False
        }

    def _try_vision_parse(self, image_data: bytes) -> Dict[str, Any]:
        """尝试使用视觉模型解析"""
        try:
            b64_image = base64.b64encode(image_data).decode('utf-8')
            result = self.llm_service.analyze_paper_with_vision(
                image_data=b64_image,
                paper_type="mixed"
            )
            return {"success": result.get("success", False), "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _parse_image_with_vision(self, image_data: bytes) -> Dict[str, Any]:
        """仅使用视觉模型解析图片"""
        vision_result = self._try_vision_parse(image_data)
        return {
            "success": vision_result.get("success", False),
            "provider": "vision",
            "result": vision_result.get("result", {}),
            "fallback_used": False,
            "error": vision_result.get("error")
        }

    def _parse_pdf(self, file_data: bytes) -> Dict[str, Any]:
        """
        PDF解析: MinerU优先，失败则返回错误（模型未下载）
        """
        if not self._is_mineru_actually_available():
            return {
                "success": False,
                "provider": "none",
                "error": "MinerU 模型未下载，无法解析PDF。请先下载模型或使用图片模式。",
                "fallback_used": False,
                "mineru_available": False,
            }

        # 保存临时文件
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            result = self.mineru_client.parse_by_cli(
                file_path=tmp_path,
                lang="ch",
                backend="hybrid-auto-engine"
            )

            return {
                "success": result.success,
                "provider": "mineru",
                "result": {
                    "success": result.success,
                    "md_content": result.md_content,
                    "questions": result.questions or [],
                    "question_count": result.question_count,
                    "formulas": result.formulas or [],
                    "images": result.images or [],
                    "output_dir": result.output_dir,
                    "error": result.error,
                },
                "fallback_used": False,
                "error": result.error if not result.success else None,
            }
        except Exception as e:
            return {
                "success": False,
                "provider": "mineru",
                "error": f"MinerU解析失败: {str(e)}",
                "fallback_used": False
            }
        finally:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _parse_docx(self, file_data: bytes) -> Dict[str, Any]:
        """
        Word文档解析: MinerU

        支持 .docx 格式
        """
        if not self.mineru_client:
            return {
                "success": False,
                "provider": "none",
                "error": "MinerU不可用，无法解析Word文档",
                "fallback_used": False,
                "mineru_available": False
            }

        # 保存临时文件
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            result = self.mineru_client.parse_by_cli(
                file_path=tmp_path,
                lang="ch",
                backend="hybrid-auto-engine"
            )

            return {
                "success": result.success,
                "provider": "mineru",
                "result": {
                    "success": result.success,
                    "md_content": result.md_content,
                    "questions": result.questions or [],
                    "question_count": result.question_count,
                    "formulas": result.formulas or [],
                    "images": result.images or [],
                    "output_dir": result.output_dir,
                    "error": result.error
                },
                "fallback_used": False
            }
        except Exception as e:
            return {
                "success": False,
                "provider": "mineru",
                "error": f"MinerU解析失败: {str(e)}",
                "fallback_used": False
            }
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _parse_pptx(self, file_data: bytes) -> Dict[str, Any]:
        """
        PowerPoint文档解析: MinerU

        支持 .pptx 格式
        """
        if not self.mineru_client:
            return {
                "success": False,
                "provider": "none",
                "error": "MinerU不可用，无法解析PPT文档",
                "fallback_used": False,
                "mineru_available": False
            }

        # 保存临时文件
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            result = self.mineru_client.parse_by_cli(
                file_path=tmp_path,
                lang="ch",
                backend="hybrid-auto-engine"
            )

            return {
                "success": result.success,
                "provider": "mineru",
                "result": {
                    "success": result.success,
                    "md_content": result.md_content,
                    "questions": result.questions or [],
                    "question_count": result.question_count,
                    "formulas": result.formulas or [],
                    "images": result.images or [],
                    "output_dir": result.output_dir,
                    "error": result.error
                },
                "fallback_used": False
            }
        except Exception as e:
            return {
                "success": False,
                "provider": "mineru",
                "error": f"MinerU解析失败: {str(e)}",
                "fallback_used": False
            }
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def parse_image_chemical(self, image_data: bytes) -> Dict[str, Any]:
        """
        解析图片中的化学式和反应方程式

        使用MinerU的化学式提取能力
        """
        if not self.mineru_client:
            # 降级到OCR
            return self._parse_image_with_ocr(image_data)

        # 保存临时文件
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name

        try:
            result = self.mineru_client.parse_by_cli(
                file_path=tmp_path,
                lang="ch",
                backend="hybrid-auto-engine",
                formula_enable=True,
                table_enable=False
            )

            return {
                "success": result.success,
                "provider": "mineru",
                "formulas": result.formulas or [],
                "content": result.md_content,
                "questions": result.questions or []
            }
        except Exception as e:
            return {
                "success": False,
                "provider": "none",
                "error": str(e)
            }
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# 全局单例
_document_parse_service = None


def get_document_parse_service() -> DocumentParseService:
    """获取全局统一文档解析服务实例"""
    global _document_parse_service
    if _document_parse_service is None:
        _document_parse_service = DocumentParseService()
    return _document_parse_service


def check_all_services_status() -> Dict[str, Any]:
    """快捷函数：检查所有服务可用性"""
    service = get_document_parse_service()
    return service.check_services_status()
