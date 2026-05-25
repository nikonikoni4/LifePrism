"""
Prompt 加载器模块

提供统一的 prompt 加载、版本管理和使用统计功能。
"""

from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import shutil
import sys
import yaml

from lifeprism.config import settings
from lifeprism.utils import get_logger
from lifeprism.llm.utils.md_os import prompts_md_load

logger = get_logger(__name__)


@dataclass(frozen=True)
class PromptRef:
    """
    Prompt 引用，包含 module 和 prompt_name

    Attributes:
        module: 模块名称（对应 {module}_prompts.md 文件）
        name: prompt 名称
    """
    module: str
    name: str


class Prompts:
    """
    所有可用的 prompts，按 module 分组

    使用示例:
        loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)
    """

    class Schedule:
        """定时任务相关 prompts (schedule_prompts.md)"""
        ACTIVITY_SUMMARY = PromptRef("schedule", "activity_summary")
        MOOD_SUMMARY = PromptRef("schedule", "mood_summary")
        UPDATE_MEMORY = PromptRef("schedule", "update_memory")
        EXTRACT_CHAT = PromptRef("schedule", "extract_chat")
        CREATE_DIARY_SUMMARY = PromptRef("schedule", "create_diary_summary")
        UPDATE_DIARY_SUMMARY = PromptRef("schedule", "update_diary_summary")
        SCREENSHOT_ANALYSIS = PromptRef("schedule", "screenshot_analysis")
        SCREEN_BEHAVIOR_SUMMARY = PromptRef("schedule", "screen_behavior_summary")
class PromptLoader:
    """
    Prompt 加载器类

    负责从 Markdown 文件加载 prompts，管理版本，记录使用统计。

    Attributes:
        prompts_dir: prompts 文件所在目录
        usage_stats_file: 使用统计文件路径
        _cache: 已加载的 prompt 文件缓存
        _usage_stats: 使用统计数据
    """

    def __init__(self, prompts_dir: Path | str = settings.lifeprism_data_path / "prompts", usage_stats_file: Optional[Path | str] = None):
        """
        初始化 PromptLoader

        Args:
            prompts_dir: prompts 文件所在目录
            usage_stats_file: 使用统计文件路径，如果为 None 则使用 prompts_dir/usage_stats.yaml
        """
        if isinstance(prompts_dir, str):
            prompts_dir = Path(prompts_dir)
        self.prompts_dir = prompts_dir

        if usage_stats_file is None:
            self.usage_stats_file = prompts_dir / "usage_stats.yaml"
        else:
            if isinstance(usage_stats_file, str):
                usage_stats_file = Path(usage_stats_file)
            self.usage_stats_file = usage_stats_file

        # 开发环境：用 templates/prompts 覆盖 localData/prompts
        if not getattr(sys, 'frozen', False):
            self._sync_dev_prompts(prompts_dir)

        # 缓存已加载的 prompt 文件
        self._cache: Dict[str, Dict[str, Any]] = {}

        # 使用统计数据
        self._usage_stats: Dict[str, Dict[str, Any]] = {}
        self._load_usage_stats()

    def _sync_dev_prompts(self,target_dir: Path) -> None:
        """开发环境：将 templates/prompts 同步到目标目录"""
        # 项目根目录 = lifeprism 包的上两级
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        source_dir = project_root / "templates" / "prompts"

        if not source_dir.exists():
            return

        # 确保目标目录父目录存在
        target_dir.parent.mkdir(parents=True, exist_ok=True)

        # 确保目标目录存在
        target_dir.mkdir(parents=True, exist_ok=True)

        # 只同步 .md 文件
        for md_file in source_dir.glob("**/*.md"):
            relative_path = md_file.relative_to(source_dir)
            target_file = target_dir / relative_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md_file, target_file)
        
        logger.debug(f"开发环境已同步 .md prompts: {source_dir} -> {target_dir}")

    def _load_usage_stats(self) -> None:
        """加载使用统计数据"""
        if self.usage_stats_file.exists():
            try:
                with open(self.usage_stats_file, 'r', encoding='utf-8') as f:
                    self._usage_stats = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"加载使用统计文件失败: {e}")
                self._usage_stats = {}
        else:
            self._usage_stats = {}

    def _save_usage_stats(self) -> None:
        """保存使用统计数据"""
        try:
            # 确保目录存在
            self.usage_stats_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.usage_stats_file, 'w', encoding='utf-8') as f:
                yaml.dump(self._usage_stats, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            logger.error(f"保存使用统计文件失败: {e}")

    def _update_usage_stats(self, prompt_name: str, version: str) -> None:
        """
        更新使用统计

        Args:
            prompt_name: prompt 名称
            version: 使用的版本
        """
        if prompt_name not in self._usage_stats:
            self._usage_stats[prompt_name] = {
                "total_count": 0,
                "version_stats": {},
                "last_used": None
            }

        # 更新总计数
        self._usage_stats[prompt_name]["total_count"] += 1

        # 更新版本计数
        version_stats = self._usage_stats[prompt_name]["version_stats"]
        if version not in version_stats:
            version_stats[version] = 0
        version_stats[version] += 1

        # 更新最后使用时间
        self._usage_stats[prompt_name]["last_used"] = datetime.now().isoformat()

        # 保存统计数据
        self._save_usage_stats()

    def _load_prompt_file(self, module: str) -> Dict[str, Any]:
        """
        加载 prompt 文件

        Args:
            module: 模块名称（如 'schedule'）

        Returns:
            解析后的 prompt 文件数据

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误
        """
        # 检查缓存
        if module in self._cache:
            return self._cache[module]

        # 构造文件路径
        file_path = self.prompts_dir / f"{module}_prompts.md"

        if not file_path.exists():
            raise FileNotFoundError(f"Prompt 文件不存在: {file_path}")

        # 加载文件
        try:
            data = prompts_md_load(file_path)
            self._cache[module] = data
            logger.debug(f"成功加载 prompt 文件: {file_path}")
            return data
        except Exception as e:
            logger.error(f"加载 prompt 文件失败 {file_path}: {e}")
            raise

    def _validate_params(
        self,
        prompt_name: str,
        version: str,
        version_history: Dict[str, Any],
        params: Dict[str, Any]
    ) -> None:
        """
        验证参数是否符合声明

        Args:
            prompt_name: prompt 名称
            version: 版本号
            version_history: 版本历史数据
            params: 调用方传入的参数

        Raises:
            ValueError: 存在未知参数或缺少必需参数
        """
        # 获取当前版本的历史信息
        version_meta = version_history.get(version, {})
        declared_params = version_meta.get("params")

        # 无 params 声明则跳过校验（向后兼容）
        if declared_params is None:
            return

        declared_set = set(declared_params)
        provided_set = set(params.keys())

        # 1. 检查未知参数
        unknown = provided_set - declared_set
        if unknown:
            raise ValueError(
                f"Prompt '{prompt_name}' (version: {version}) 存在未知参数: {unknown}。"
                f"已声明参数: {declared_set}"
            )

        # 2. 检查缺少必需参数
        missing = declared_set - provided_set
        if missing:
            raise ValueError(
                f"Prompt '{prompt_name}' (version: {version}) 缺少必需参数: {missing}。"
                f"必需参数: {declared_set}"
            )

    def load_prompt(
        self,
        prompt: PromptRef | str,
        module: Optional[str] = None,
        version: Optional[str] = None,
        **params
    ) -> str:
        """
        加载指定的 prompt

        支持两种调用方式：
        1. 使用 PromptRef（推荐）：
           loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)
        2. 使用字符串（向后兼容）：
           loader.load_prompt("activity_summary", module="schedule")

        Args:
            prompt: PromptRef 对象或 prompt 名称字符串
            module: 模块名称（使用字符串 prompt 时必需）
            version: 版本号（如 'v1', 'v2'），如果为 None 则使用 active_version
            **params: 用于参数注入的额外参数

        Returns:
            prompt 内容字符串

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: prompt 不存在或版本不存在，或参数错误
        """
        # 解析 prompt 参数
        if isinstance(prompt, PromptRef):
            module = prompt.module
            prompt_name = prompt.name
        elif isinstance(prompt, str):
            if module is None:
                raise ValueError("使用字符串 prompt 时必须提供 module 参数")
            prompt_name = prompt
        else:
            raise TypeError(f"prompt 参数类型错误: {type(prompt)}，应为 PromptRef 或 str")

        # 加载文件
        data = self._load_prompt_file(module)

        # 检查 prompt 是否存在
        if prompt_name not in data["prompts"]:
            raise ValueError(f"Prompt '{prompt_name}' 不存在于模块 '{module}'")

        prompt_data = data["prompts"][prompt_name]

        # 确定使用的版本
        if version is None:
            version = prompt_data["metadata"]["active_version"]

        # 检查版本是否存在
        if version not in prompt_data["versions"]:
            available_versions = list(prompt_data["versions"].keys())
            raise ValueError(
                f"版本 '{version}' 不存在于 prompt '{prompt_name}'，"
                f"可用版本: {available_versions}"
            )

        # 获取 prompt 内容
        prompt_content = prompt_data["versions"][version]

        # 参数校验（在参数注入之前）
        # 获取当前版本的参数声明
        version_meta = prompt_data["metadata"]["version_history"].get(version, {})
        declared_params = version_meta.get("params")

        # 如果版本声明了参数，则进行校验
        if declared_params is not None:
            self._validate_params(
                prompt_name,
                version,
                prompt_data["metadata"]["version_history"],
                params
            )

        # 参数注入（如果有参数）
        if params:
            try:
                prompt_content = prompt_content.format(**params)
            except KeyError as e:
                logger.warning(f"参数注入失败，缺少参数: {e}")

        # 更新使用统计
        self._update_usage_stats(prompt_name, version)

        logger.debug(f"成功加载 prompt: {module}.{prompt_name} (version: {version})")

        return prompt_content

    def get_prompt_metadata(self, module: str, prompt_name: str) -> Dict[str, Any]:
        """
        获取 prompt 的元数据

        Args:
            module: 模块名称
            prompt_name: prompt 名称

        Returns:
            元数据字典，包含 active_version 和 version_history

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: prompt 不存在
        """
        data = self._load_prompt_file(module)

        if prompt_name not in data["prompts"]:
            raise ValueError(f"Prompt '{prompt_name}' 不存在于模块 '{module}'")

        return data["prompts"][prompt_name]["metadata"]

    def get_available_versions(self, module: str, prompt_name: str) -> list[str]:
        """
        获取 prompt 的所有可用版本

        Args:
            module: 模块名称
            prompt_name: prompt 名称

        Returns:
            版本列表

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: prompt 不存在
        """
        data = self._load_prompt_file(module)

        if prompt_name not in data["prompts"]:
            raise ValueError(f"Prompt '{prompt_name}' 不存在于模块 '{module}'")

        return list(data["prompts"][prompt_name]["versions"].keys())

    def get_usage_stats(self, prompt_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取使用统计数据

        Args:
            prompt_name: prompt 名称，如果为 None 则返回所有统计数据

        Returns:
            统计数据字典
        """
        if prompt_name is None:
            return self._usage_stats.copy()
        else:
            return self._usage_stats.get(prompt_name, {
                "total_count": 0,
                "version_stats": {},
                "last_used": None
            })

    def clear_cache(self) -> None:
        """清空缓存，强制重新加载文件"""
        self._cache.clear()
        logger.debug("已清空 prompt 缓存")
