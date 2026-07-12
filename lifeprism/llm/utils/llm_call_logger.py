"""LLM 调用记录器

用于记录 LLM 调用的输入输出，支持：
1. 查看系统运行状态
2. 收集 LLM 测试数据

使用示例：
    from lifeprism.utils.llm_call_logger import llm_call_logger

    # 记录调用
    msg = InboundMessage(...)
    response = await bus.send(msg)

    llm_call_logger.log_call(
        inbound_msg=msg,
        outbound_msg=response,
        prompt_module="schedule",
        prompt_name="screenshot_analysis",
        prompt_version="v1",
    )

    # 导出数据集
    dataset = llm_call_logger.export_by_prompt(
        prompt_module="schedule",
        prompt_name="screenshot_analysis",
    )
"""

import base64
import inspect
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lifeprism.config import settings
from lifeprism.llm.bus.events import MessageContent
from lifeprism.utils.lazy_singleton import LazySingleton
from lifeprism.utils.logger import DEBUG, get_logger

logger = get_logger(__name__)
logger.setLevel(DEBUG)


class LLMCallLogger:
    """LLM 调用记录器

    记录每次 LLM 调用的输入输出，包括文本、图片、tokens 等信息。
    支持按 prompt 或 workflow 导出数据集。
    """

    def __init__(self, log_dir: Path | None = None):
        """初始化 LLM 调用记录器

        Args:
            log_dir: 日志目录，默认为 lifeprism_data_path/debug_log/llm_logs
        """
        if log_dir is None:
            log_dir = settings.lifeprism_data_path / "debug_logs" / "llm_logs"
            logger.info("llm_call_输出目录：%s", log_dir)

        self.log_dir = Path(log_dir)
        self.image_dir = self.log_dir / "images"

        # 确保目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)

        # 从配置读取记录标志位
        self._enabled = settings.get("llm_call_logger_enabled", False)

        logger.debug(
            "LLM 调用记录器初始化完成，日志目录: %s, 启用状态: %s", self.log_dir, self._enabled
        )

    @property
    def enabled(self) -> bool:
        """获取记录标志位"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """设置记录标志位"""
        self._enabled = value
        logger.info("LLM 调用记录器已%s", "启用" if value else "禁用")

    def log_call(
        self,
        inbound_msg: Any,
        outbound_msg: Any,
        prompt_module: str | None = None,
        prompt_name: str | None = None,
        prompt_version: str | None = None,
        model: str | None = None,
        workflow_id: str | None = None,
        score: float | None = None,
        system_prompt: str | None = None,
    ) -> str | None:
        """记录一次 LLM 调用

        Args:
            inbound_msg: 输入消息 (InboundMessage)
            outbound_msg: 输出消息 (OutboundMessage)
            prompt_module: prompt 模块名（可选）
            prompt_name: prompt 名称（可选）
            prompt_version: prompt 版本（可选）
            model: 使用的模型（可选，未传时自动从 settings 获取）
            workflow_id: workflow ID（可选）
            score: 评分（可选，默认 None，由后续 update_score 设置）
            system_prompt: system prompt（可选，优先使用此值，未传则从 inbound_msg.extra 读取）

        Returns:
            记录 ID，如果未启用则返回 None
        """
        # 检查标志位，如果未启用则直接返回
        if not self._enabled:
            return None

        try:
            # 1. 提取文本和图片
            text_content, image_filenames = self._process_content(
                inbound_msg.content, inbound_msg.extra
            )

            # 2. 获取调用位置
            caller = self._get_caller_info()

            # 3. 提取 system prompt（优先使用传入值，否则从 extra 读取）
            if system_prompt is not None:
                system_prompt_content = system_prompt
            elif inbound_msg.extra and "system_prompt" in inbound_msg.extra:
                system_prompt_content = inbound_msg.extra["system_prompt"]
            else:
                system_prompt_content = ""

            # 4. 提取输出内容
            output_content = None
            tokens = None
            if outbound_msg and outbound_msg.response:
                output_content = outbound_msg.response.content
                tokens = outbound_msg.response.usage

            # 5. 提取工具调用链
            tool_call_chain = None
            if outbound_msg and outbound_msg.extra and "tool_call_chain" in outbound_msg.extra:
                tool_call_chain = outbound_msg.extra["tool_call_chain"]

            # 6. model 自动兜底：未传时从 settings 获取默认模型
            if model is None:
                model = settings.get("model", None) or getattr(settings, "model", None)

            # 7. 构建记录
            record = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "caller": caller,
                "message_type": inbound_msg.type,
                "session_id": inbound_msg.session_id,
                "channel": inbound_msg.channel,
                "workflow_id": workflow_id,
                "prompt": {
                    "module": prompt_module,
                    "name": prompt_name,
                    "version": prompt_version,
                    "content": system_prompt_content,
                },
                "input": {
                    "content_type": "multimodal" if image_filenames else "text",
                    "text": text_content,
                    "images": image_filenames,
                },
                "output": {"content": output_content},
                "tool_call_chain": tool_call_chain,
                "model": model,
                "tokens": tokens,
                "error": None,
                "score": score,  # 评分，默认为 null，由后续 agent 通过 update_score 赋值
            }

            # 8. 写入文件
            self._write_record(record)

            logger.debug("成功记录 LLM 调用: %s", record["id"])
            return record["id"]

        except Exception as e:
            logger.warning("记录 LLM 调用失败: %s", e, exc_info=True)
            return None

    def _process_content(
        self, content: MessageContent, extra: dict[str, Any] | None
    ) -> tuple[str, list[str]]:
        """处理 content 和 extra，提取文本和图片

        Args:
            content: 消息内容（MessageContent，已归一化的多模态列表）
            extra: 额外数据

        Returns:
            (text_content, image_filenames)
        """
        text_parts = []
        image_filenames = []

        # 1. 处理 content（MessageContent 始终是 list）
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    # Base64 图片
                    image_url = part.get("image_url", {})
                    base64_url = image_url.get("url", "")
                    if base64_url:
                        try:
                            filename = self._save_base64_image(base64_url)
                            image_filenames.append(filename)
                        except Exception as e:
                            logger.warning("保存 base64 图片失败: %s", e)
        text_content = "\n".join(text_parts)

        # 2. 处理 extra["media"]（文件路径）
        if extra and "media" in extra:
            media_list = extra["media"]
            if isinstance(media_list, list):
                for media_path in media_list:
                    try:
                        filename = self._copy_media_file(media_path)
                        image_filenames.append(filename)
                    except Exception as e:
                        logger.warning("拷贝媒体文件失败 %s: %s", media_path, e)

        return text_content, image_filenames

    def _save_base64_image(self, base64_url: str) -> str:
        """从 base64 解码并保存图片

        Args:
            base64_url: data:image/png;base64,xxxxx

        Returns:
            保存的文件名（不含路径）
        """
        # 解析 MIME 类型和数据
        match = re.match(r"data:image/(\w+);base64,(.+)", base64_url)
        if not match:
            raise ValueError("Invalid base64 image URL")

        ext = match.group(1)
        b64_data = match.group(2)

        # 解码
        image_data = base64.b64decode(b64_data)

        # 生成文件名：img_YYYYMMdd_HHMMSSfff.ext
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S%f")[:-3]
        filename = f"img_{timestamp}.{ext}"

        # 保存
        image_path = self.image_dir / filename
        with open(image_path, "wb") as f:
            f.write(image_data)

        logger.debug("保存 base64 图片: %s", filename)
        return filename

    def _copy_media_file(self, media_path: str) -> str:
        """拷贝媒体文件到 images 文件夹

        Args:
            media_path: 相对于 lifeprism_data_path 的路径

        Returns:
            保存的文件名（不含路径）
        """
        # 原始文件路径
        source_path = settings.lifeprism_data_path / media_path

        if not source_path.exists():
            raise FileNotFoundError(f"Media file not found: {media_path}")

        # 生成新文件名（保留原始扩展名）
        ext = source_path.suffix
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S%f")[:-3]
        filename = f"media_{timestamp}{ext}"

        # 拷贝
        target_path = self.image_dir / filename
        shutil.copy2(source_path, target_path)

        logger.debug("拷贝媒体文件: %s -> %s", media_path, filename)
        return filename

    def _get_caller_info(self) -> str:
        """获取调用位置

        Returns:
            调用位置字符串（文件:函数:行号）
        """
        # 向上追溯栈帧，跳过 logger 内部调用
        frame = inspect.currentframe()
        for _ in range(5):  # 向上追溯 5 层
            if frame is None:
                break
            frame = frame.f_back

        if frame:
            filename = frame.f_code.co_filename
            function = frame.f_code.co_name
            lineno = frame.f_lineno

            # 转换为相对路径（相对于项目根目录）
            try:
                # 获取项目根目录（lifeprism 包的上一级）
                project_root = Path(__file__).resolve().parent.parent.parent
                rel_path = Path(filename).relative_to(project_root)
                return f"{rel_path}:{function}:{lineno}"
            except ValueError:
                # 如果无法转换为相对路径，使用文件名
                return f"{Path(filename).name}:{function}:{lineno}"

        return "unknown"

    def _write_record(self, record: dict[str, Any]):
        """写入记录到日志文件

        Args:
            record: 调用记录
        """
        # 按日期分文件
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.log_dir / f"llm_calls_{date_str}.json"

        # 读取现有数据
        if log_file.exists():
            try:
                with open(log_file, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning("读取日志文件失败 %s: %s", log_file, e)
                data = {"version": "1.0", "date": date_str, "calls": []}
        else:
            data = {"version": "1.0", "date": date_str, "calls": []}

        # 添加新记录
        data["calls"].append(record)

        # 写入
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("写入日志文件失败 %s: %s", log_file, e)
            raise

    def export_by_prompt(
        self,
        prompt_module: str,
        prompt_name: str,
        prompt_version: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """按 prompt 导出数据集

        Args:
            prompt_module: prompt 模块名
            prompt_name: prompt 名称
            prompt_version: prompt 版本（可选，None 表示所有版本）
            start_date: 开始日期 YYYY-MM-DD（可选）
            end_date: 结束日期 YYYY-MM-DD（可选）

        Returns:
            数据集列表，每项包含 id, timestamp, input, output, tokens
        """
        dataset = []

        # 获取日期范围内的所有日志文件
        log_files = self._get_log_files(start_date, end_date)

        for log_file in log_files:
            try:
                with open(log_file, encoding="utf-8") as f:
                    data = json.load(f)

                for call in data.get("calls", []):
                    prompt = call.get("prompt", {})

                    # 匹配 prompt
                    if prompt.get("module") == prompt_module and prompt.get("name") == prompt_name:
                        # 如果指定了版本，检查版本
                        if prompt_version is not None and prompt.get("version") != prompt_version:
                            continue

                        # 提取数据
                        dataset.append(
                            {
                                "id": call.get("id"),
                                "timestamp": call.get("timestamp"),
                                "model": call.get("model"),
                                "input": call.get("input"),
                                "output": call.get("output"),
                                "tokens": call.get("tokens"),
                                "score": call.get("score"),
                            }
                        )
            except Exception as e:
                logger.warning("读取日志文件失败 %s: %s", log_file, e)

        logger.info("导出 %s.%s 数据集，共 %s 条记录", prompt_module, prompt_name, len(dataset))
        return dataset

    def export_by_workflow(
        self,
        workflow_id: str,
    ) -> list[dict[str, Any]]:
        """按 workflow_id 导出完整 workflow 数据

        Args:
            workflow_id: workflow ID

        Returns:
            该 workflow 的所有调用记录
        """
        records = []

        # 遍历所有日志文件
        log_files = self._get_log_files()

        for log_file in log_files:
            try:
                with open(log_file, encoding="utf-8") as f:
                    data = json.load(f)

                for call in data.get("calls", []):
                    if call.get("workflow_id") == workflow_id:
                        records.append(call)
            except Exception as e:
                logger.warning("读取日志文件失败 %s: %s", log_file, e)

        # 按时间戳排序
        records.sort(key=lambda x: x.get("timestamp", ""))

        logger.info("导出 workflow %s 数据，共 %s 条记录", workflow_id, len(records))
        return records

    def _get_log_files(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Path]:
        """获取日期范围内的所有日志文件

        Args:
            start_date: 开始日期 YYYY-MM-DD（可选）
            end_date: 结束日期 YYYY-MM-DD（可选）

        Returns:
            日志文件路径列表
        """
        all_files = sorted(self.log_dir.glob("llm_calls_*.json"))

        if start_date is None and end_date is None:
            return all_files

        # 过滤日期范围
        filtered_files = []
        for file in all_files:
            # 从文件名提取日期：llm_calls_YYYY-MM-DD.json
            match = re.match(r"llm_calls_(\d{4}-\d{2}-\d{2})\.json", file.name)
            if match:
                file_date = match.group(1)

                if start_date and file_date < start_date:
                    continue
                if end_date and file_date > end_date:
                    continue

                filtered_files.append(file)

        return filtered_files


# 全局单例
llm_call_logger: LLMCallLogger = LazySingleton(LLMCallLogger)
