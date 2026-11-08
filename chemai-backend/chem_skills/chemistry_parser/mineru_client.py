"""
MinerU API 客户端封装
提供同步/异步两种方式调用 MinerU 文档解析服务
"""
import os
import sys
import tempfile
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass


# 默认 MinerU 安装路径
# 项目内的 MinerU 源码统一放在 third_party/mineru；优先按项目根相对定位，换机器/盘符不失效
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MINERU_PATHS = [
    str(_PROJECT_ROOT / "third_party" / "mineru"),
    r"D:\MinerU-master\MinerU-master",
    r"C:\MinerU-master\MinerU-master",
    os.path.expanduser("~/MinerU-master/MinerU-master"),
]


def find_mineru_root() -> Optional[str]:
    """自动查找 MinerU 安装路径"""
    for path in DEFAULT_MINERU_PATHS:
        if os.path.exists(os.path.join(path, "mineru", "cli", "api_client.py")):
            return path
    return None


@dataclass
class ParseResult:
    """解析结果"""
    success: bool
    output_dir: Optional[str] = None
    md_content: Optional[str] = None
    middle_json: Optional[str] = None
    images: Optional[List[str]] = None
    formulas: Optional[List[str]] = None
    error: Optional[str] = None
    question_count: int = 0
    questions: Optional[List[Dict]] = None


class MinerUClient:
    """
    MinerU 文档解析客户端

    支持两种调用方式：
    1. 命令行模式：通过 subprocess 调用 mineru.cli.client
    2. API 模式：启动本地 API 服务进行解析
    """

    def __init__(self, mineru_root: Optional[str] = None):
        """
        初始化 MinerU 客户端

        Args:
            mineru_root: MinerU 安装路径，如果为 None 则自动查找
        """
        if mineru_root is None:
            mineru_root = find_mineru_root()

        if mineru_root is None or not os.path.exists(mineru_root):
            raise MinerUNotFoundError(
                f"MinerU not found. Please install MinerU v3.0.0. "
                f"Searched paths: {DEFAULT_MINERU_PATHS}"
            )

        self.mineru_root = Path(mineru_root)
        self.mineru_cli = self.mineru_root / "mineru" / "cli"

        # 验证必要文件存在
        api_client = self.mineru_cli / "api_client.py"
        client_py = self.mineru_cli / "client.py"

        if not api_client.exists():
            raise MinerUNotFoundError(f"MinerU api_client.py not found at {api_client}")
        if not client_py.exists():
            raise MinerUNotFoundError(f"MinerU client.py not found at {client_py}")

    def _import_api_modules(self):
        """动态导入 MinerU API 模块"""
        if str(self.mineru_root) not in sys.path:
            sys.path.insert(0, str(self.mineru_root))

        from mineru.cli.api_client import (
            LocalAPIServer,
            UploadAsset,
            build_parse_request_form_data,
            submit_parse_task,
            wait_for_task_result,
            download_result_zip,
            safe_extract_zip,
            find_free_port,
            build_http_timeout,
        )
        from mineru.cli.client import (
            collect_input_documents,
            plan_tasks,
        )

        return {
            "LocalAPIServer": LocalAPIServer,
            "UploadAsset": UploadAsset,
            "build_parse_request_form_data": build_parse_request_form_data,
            "submit_parse_task": submit_parse_task,
            "wait_for_task_result": wait_for_task_result,
            "download_result_zip": download_result_zip,
            "safe_extract_zip": safe_extract_zip,
            "find_free_port": find_free_port,
            "build_http_timeout": build_http_timeout,
            "collect_input_documents": collect_input_documents,
            "plan_tasks": plan_tasks,
        }

    def parse_by_cli(
        self,
        file_path: str,
        output_dir: Optional[str] = None,
        lang: str = "ch",
        backend: str = "hybrid-auto-engine",
        start_page: int = 0,
        end_page: Optional[int] = None,
        formula_enable: bool = True,
        table_enable: bool = True,
        timeout: int = 3600,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> ParseResult:
        """
        通过命令行方式解析文档（推荐）

        Args:
            file_path: 文档路径
            output_dir: 输出目录，默认使用临时目录
            lang: 语言代码，默认中文
            backend: 解析后端，默认 hybrid-auto-engine
            start_page: 起始页
            end_page: 结束页
            formula_enable: 是否解析公式
            table_enable: 是否解析表格
            timeout: 超时时间（秒）
            progress_callback: 进度回调函数

        Returns:
            ParseResult: 解析结果
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return ParseResult(success=False, error=f"文件不存在: {file_path}")

        # Always use absolute path (subprocess runs in mineru_root, not project root)
        file_path_abs = str(file_path_obj.resolve())

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="mineru_parse_")

        cmd = [
            sys.executable,
            "-m",
            "mineru.cli.client",
            "-p", file_path_abs,
            "-o", output_dir,
            "-b", backend,
            "-l", lang,
            "-f", str(formula_enable).lower(),
            "-t", str(table_enable).lower(),
        ]

        if start_page > 0:
            cmd.extend(["-s", str(start_page)])
        if end_page is not None:
            cmd.extend(["-e", str(end_page)])

        try:
            if progress_callback:
                progress_callback(f"正在解析: {file_path_obj.name}")

            result = subprocess.run(
                cmd,
                cwd=str(self.mineru_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "解析失败"
                return ParseResult(success=False, error=error_msg)

            # 读取解析结果
            return self._read_parse_output(output_dir, ParseResult(success=True, output_dir=output_dir))

        except subprocess.TimeoutExpired:
            return ParseResult(success=False, error="解析超时")
        except Exception as e:
            return ParseResult(success=False, error=f"解析失败: {str(e)}")

    async def parse_by_api(
        self,
        file_path: str,
        output_dir: Optional[str] = None,
        lang: str = "ch",
        backend: str = "hybrid-auto-engine",
        start_page: int = 0,
        end_page: Optional[int] = None,
        parse_method: str = "auto",
        timeout: int = 3600,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> ParseResult:
        """
        通过 API 方式解析文档（异步）

        Args:
            同 parse_by_cli

        Returns:
            ParseResult: 解析结果
        """
        modules = self._import_api_modules()
        LocalAPIServer = modules["LocalAPIServer"]
        collect_input_documents = modules["collect_input_documents"]
        plan_tasks = modules["plan_tasks"]

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return ParseResult(success=False, error=f"文件不存在: {file_path}")

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="mineru_parse_")

        async def run_parse():
            documents = collect_input_documents(
                input_path=file_path_obj,
                start_page_id=start_page,
                end_page_id=end_page,
            )
            planned_tasks = plan_tasks(
                documents=documents,
                backend=backend,
                processing_window_size=64,
            )

            if not planned_tasks:
                return ParseResult(success=False, error="无法创建解析任务")

            planned_task = planned_tasks[0]

            local_server = LocalAPIServer()
            base_url = local_server.start()

            try:
                async with asyncio.timeout(timeout):
                    async with asyncio.get_event_loop().create_task(
                        self._api_parse(
                            client=None,
                            base_url=base_url,
                            planned_task=planned_task,
                            lang=lang,
                            backend=backend,
                            parse_method=parse_method,
                            start_page=start_page,
                            end_page=end_page,
                            modules=modules,
                            progress_callback=progress_callback,
                            file_stem=file_path_obj.stem,
                        )
                    ) as task:
                        result = await task
                        return result
            finally:
                local_server.stop()

        try:
            return await run_parse()
        except Exception as e:
            return ParseResult(success=False, error=f"API解析失败: {str(e)}")

    async def _api_parse(
        self,
        client,
        base_url: str,
        planned_task,
        lang: str,
        backend: str,
        parse_method: str,
        start_page: int,
        end_page: int,
        modules: dict,
        progress_callback: Optional[Callable[[str], None]],
        file_stem: str,
    ) -> ParseResult:
        """内部：执行 API 解析"""
        import httpx

        UploadAsset = modules["UploadAsset"]
        build_request_form_data = modules["build_request_form_data"]
        submit_parse_task = modules["submit_parse_task"]
        wait_for_task_result = modules["wait_for_task_result"]
        download_result_zip = modules["download_result_zip"]
        safe_extract_zip = modules["safe_extract_zip"]
        build_http_timeout = modules["build_http_timeout"]

        timeout = build_http_timeout()
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http_client:
            # Wait for server ready
            for _ in range(60):
                try:
                    response = await http_client.get(f"{base_url}/health")
                    if response.status_code == 200:
                        break
                except Exception:
                    pass
                await asyncio.sleep(1)

            form_data = build_request_form_data(
                lang=lang,
                backend=backend,
                method=parse_method,
                formula_enable=True,
                table_enable=True,
                server_url=None,
                start_page_id=start_page,
                end_page_id=end_page,
            )

            upload_assets = [
                UploadAsset(
                    path=document.path,
                    upload_name=f"{document.stem}{document.path.suffix}",
                )
                for document in planned_task.documents
            ]

            if progress_callback:
                progress_callback(f"正在上传: {file_stem}")

            submit_response = await submit_parse_task(
                base_url=base_url,
                upload_assets=upload_assets,
                form_data=form_data,
            )

            if progress_callback:
                progress_callback(f"正在解析: {file_stem}")

            await wait_for_task_result(
                client=http_client,
                submit_response=submit_response,
                task_label=f"parse_{file_stem}",
                timeout_seconds=3600,
            )

            zip_path = await download_result_zip(
                client=http_client,
                submit_response=submit_response,
                task_label=f"parse_{file_stem}",
            )

            output_dir = tempfile.mkdtemp(prefix="mineru_parse_")
            safe_extract_zip(zip_path, Path(output_dir))
            zip_path.unlink(missing_ok=True)

        return self._read_parse_output(output_dir, ParseResult(success=True, output_dir=output_dir))

    def _read_parse_output(self, output_dir: str, base_result: ParseResult) -> ParseResult:
        """读取解析输出"""
        output_path = Path(output_dir)

        # 读取 md 文件
        md_files = list(output_path.glob("**/*.md"))
        md_content = None
        if md_files:
            try:
                md_content = md_files[0].read_text(encoding="utf-8")
            except Exception:
                pass

        # 读取 middle_json
        json_files = list(output_path.glob("**/*_middle.json"))
        middle_json = None
        if json_files:
            try:
                middle_json = json_files[0].read_text(encoding="utf-8")
            except Exception:
                pass

        # 收集图片
        images = []
        for ext in ["*.png", "*.jpg", "*.jpeg", "*.gif"]:
            images.extend([str(f) for f in output_path.glob(f"**/{ext}")])

        # 提取化学式
        formulas = self._extract_formulas(md_content) if md_content else []

        # LaTeX 标准化
        try:
            from chem_skills.chemistry_parser.engine.latex_standardizer import standardize_latex_chemical
            formulas = [standardize_latex_chemical(f) for f in formulas]
        except ImportError:
            pass

        # 提取题目
        questions = self._extract_questions(md_content) if md_content else []

        base_result.md_content = md_content
        base_result.middle_json = middle_json
        base_result.images = images
        base_result.formulas = formulas
        base_result.questions = questions
        base_result.question_count = len(questions)

        return base_result

    def _extract_formulas(self, md_content: str) -> List[str]:
        """从 Markdown 内容中提取化学式（含 LaTeX 和文本式）"""
        import re

        formulas = []

        # LaTeX 公式
        latex_patterns = [
            r'\$([^\$]+)\$',  # $...$
            r'\$\$([^\$]+)\$\$',  # $$...$$
            r'\\\(([^\)]+)\\\)',  # \(...\)
            r'\\\[([^\]]+)\\\]',  # \[...\]
        ]
        for pattern in latex_patterns:
            for match in re.finditer(pattern, md_content):
                formulas.append(match.group(1))

        # 化学式模式（如 H2O, Ca(OH)2, Fe2(SO4)3, Na2CO3·10H2O 等）
        chem_patterns = [
            # 带括号的复杂化学式: Ca(OH)2, Fe2(SO4)3, [Ag(NH3)2]+
            r'\b[A-Z][a-z]?\d*(?:\((?:[A-Z][a-z]?\d*)+\)\d*)+\+?',
            # 水合物: Na2CO3·10H2O, CuSO4·5H2O
            r'\b[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*·\d+H2O',
            # 简单化学式: H2O, CO2, Fe3O4
            r'\b[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*){1,}',
        ]
        for pattern in chem_patterns:
            for match in re.findall(pattern, md_content):
                formula = match.group(0) if hasattr(match, 'group') else match
                if len(formula) > 1 and formula not in formulas:
                    formulas.append(formula)

        return list(set(formulas))

    def _extract_questions(self, md_content: str) -> List[Dict[str, Any]]:
        """从 Markdown 内容中提取题目"""
        questions = []
        lines = md_content.split("\n")
        current_question = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测题目开始
            if line[0].isdigit() and "." in line[:5]:
                if current_question:
                    questions.append(current_question)
                current_question = {"type": "unknown", "content": line, "answer": None}
            elif "____" in line or "______" in line:
                if current_question:
                    questions.append(current_question)
                current_question = {"type": "fill-blank", "content": line, "answer": None}
            elif line.startswith("问") or "解释" in line or "说明" in line:
                if current_question:
                    questions.append(current_question)
                current_question = {"type": "short-answer", "content": line, "answer": None}
            elif any(kw in line for kw in ["计算", "求", "证明"]):
                if current_question:
                    questions.append(current_question)
                current_question = {"type": "calculation", "content": line, "answer": None}
            elif line.startswith(("A.", "B.", "C.", "D.", "A、", "B、")):
                if current_question:
                    current_question["content"] += "\n" + line
                    if line.startswith(("A.", "A、")) and "answer" not in current_question:
                        current_question["type"] = "choice"
            elif current_question:
                current_question["content"] += "\n" + line

        if current_question:
            questions.append(current_question)

        return questions


class MinerUNotFoundError(Exception):
    """MinerU 未找到异常"""
    pass


# 全局单例
_client_instance: Optional[MinerUClient] = None


def get_mineru_client() -> MinerUClient:
    """获取全局 MinerU 客户端实例"""
    global _client_instance
    if _client_instance is None:
        _client_instance = MinerUClient()
    return _client_instance


def reset_mineru_client() -> None:
    """重置全局客户端实例"""
    global _client_instance
    _client_instance = None
