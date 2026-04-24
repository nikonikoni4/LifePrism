"""
Diary 服务层 - 日记业务逻辑

设计原则：数据库只存 meta 信息，内容存 md 文件
文件存储路径：lifeprismData/diary/YYYY/MM/{date}.md
模板存储路径：lifeprismData/diary/template/{name}.md

架构：纯函数模块（无内存缓存，不需要单例）
"""
import asyncio
import hashlib
import json
from typing import Any, Optional
from pathlib import Path
from datetime import datetime

from lifeprism.llm.function.diary_summary import ai_diary_summary
from lifeprism.server.schemas.diary_schemas import (
    DiaryItem,
    DiaryMetaItem,
    DiaryListResponse,
    DiaryAISummaryResponse,
    UpdateDiaryMetaRequest,
    SaveDiaryContentRequest,
    TemplateItem,
    TemplateListResponse,
    CreateTemplateRequest,
    UpdateTemplateRequest,
    GenerateDiaryAISummaryRangeRequest,
    GenerateDiaryAISummaryRangeResponse,
    ExistingSummaryMode,
)
from lifeprism.repository import diary_repository
from lifeprism.utils import get_logger

logger = get_logger(__name__)

_MOOD_LABEL_MAP = {
    "very_happy": "非常愉悦",
    "happy": "有点开心",
    "calm": "平静",
    "bad": "不太好",
    "very_bad": "非常不好",
}

_IMPORTANCE_LABEL_MAP = {
    "important": "重要",
    "normal": "一般",
    "unimportant": "平凡",
}


# ==================== 文件路径工具 ====================

def _get_diary_dir() -> Path:
    """获取日记目录路径"""
    from lifeprism.config.settings_manager import settings
    return Path(settings.lifeprism_data_path) / "diary"


def _get_diary_file_path(date: str) -> Path:
    """根据日期返回日记正文文件路径：diary/YYYY/MM/YYYY-MM-DD.md"""
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    year = f"{date_obj.year:04d}"
    month = f"{date_obj.month:02d}"
    return _get_diary_dir() / year / month / f"{date}.md"


def _get_template_dir() -> Path:
    """获取模板目录路径"""
    return _get_diary_dir() / "template"


def _ensure_diary_dir():
    """确保日记目录存在"""
    try:
        _get_diary_dir().mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"创建日记目录失败: {e}")


def _ensure_template_dir():
    """确保模板目录存在"""
    try:
        _get_template_dir().mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"创建模板目录失败: {e}")


def _read_diary_content(date: str) -> str:
    """从文件读取日记内容，不存在则返回空字符串"""
    try:
        file_path = _get_diary_file_path(date)
        if file_path.exists():
            return file_path.read_text(encoding='utf-8')
        return ""
    except Exception as e:
        logger.error(f"读取日记文件 {date} 失败: {e}")
        return ""


def _write_diary_content(date: str, content: str):
    """写入日记内容到文件"""
    try:
        file_path = _get_diary_file_path(date)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
    except Exception as e:
        logger.error(f"写入日记文件 {date} 失败: {e}")


def _calculate_word_count(content: str) -> int:
    """计算字数（去除空白后的字符数）"""
    return len(content.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", ""))


def _parse_custom_tags(tags_json: Optional[str]) -> list:
    """JSON 字符串 → List[str]"""
    if not tags_json:
        return []
    try:
        result = json.loads(tags_json)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _map_diary_meta_for_summary(item: dict) -> tuple[Optional[str], Optional[str], list[str]]:
    """将日记 meta 枚举值转换为 LLM 更易理解的文本标签"""
    mood = _MOOD_LABEL_MAP.get(item.get("mood")) if item.get("mood") else None
    importance = _IMPORTANCE_LABEL_MAP.get(item.get("importance")) if item.get("importance") else None
    custom_tags = _parse_custom_tags(item.get("custom_tags"))
    return mood, importance, custom_tags


def _extract_summary_content(result: Any) -> Optional[str]:
    """从 LLM 返回值中提取 summary 正文"""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("content")
    return getattr(result, "content", None)


def _compute_diary_source_hash(content: str) -> str:
    """计算日记正文的 hash（用于判断 AI 总结是否需要刷新）"""
    normalized = content.strip().replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


# ==================== 日记 CRUD ====================

def _convert_db_to_diary_item(item: dict, include_content: bool = False) -> DiaryItem:
    """将数据库记录转换为 DiaryItem"""
    content = ""
    if include_content:
        content = _read_diary_content(item['date'])

    return DiaryItem(
        date=item['date'],
        mood=item.get('mood'),
        importance=item.get('importance'),
        custom_tags=_parse_custom_tags(item.get('custom_tags')),
        word_count=item.get('word_count', 0),
        ai_summary=item.get('ai_summary'),
        diary_source_hash=item.get('diary_source_hash'),
        content=content,
        created_at=item.get('created_at', ''),
        updated_at=item.get('updated_at'),
    )


def _convert_db_to_meta_item(item: dict) -> DiaryMetaItem:
    """将数据库记录转换为 DiaryMetaItem"""
    return DiaryMetaItem(
        date=item['date'],
        mood=item.get('mood'),
        importance=item.get('importance'),
        custom_tags=_parse_custom_tags(item.get('custom_tags')),
        word_count=item.get('word_count', 0),
        ai_summary=item.get('ai_summary'),
        diary_source_hash=item.get('diary_source_hash'),
        created_at=item.get('created_at', ''),
        updated_at=item.get('updated_at'),
    )


def get_diary(date: str) -> Optional[DiaryItem]:
    """
    获取指定日期日记（meta + content），不存在则自动创建

    Args:
        date: 日期 YYYY-MM-DD

    Returns:
        Optional[DiaryItem]: 日记详情
    """
    item = diary_repository.get_diary_by_date(date)
    if not item:
        # 自动创建 DB 记录 + 空 md 文件
        success = diary_repository.create_diary(date)
        if not success:
            return None
        _ensure_diary_dir()
        item = diary_repository.get_diary_by_date(date)
        if not item:
            return None
    return _convert_db_to_diary_item(item, include_content=True)


def update_diary_meta(date: str, request: UpdateDiaryMetaRequest) -> Optional[DiaryItem]:
    """
    更新日记 meta（部分更新）

    Args:
        date: 日期 YYYY-MM-DD
        request: 更新请求

    Returns:
        Optional[DiaryItem]: 更新后的日记
    """
    existing = diary_repository.get_diary_by_date(date)
    if not existing:
        return None

    explicitly_set = request.model_fields_set
    update_data = {}

    if 'mood' in explicitly_set:
        update_data['mood'] = request.mood
    if 'importance' in explicitly_set:
        update_data['importance'] = request.importance
    if 'custom_tags' in explicitly_set:
        update_data['custom_tags'] = json.dumps(request.custom_tags, ensure_ascii=False)

    if update_data:
        diary_repository.update_diary(date, update_data)

    return _convert_db_to_diary_item(
        diary_repository.get_diary_by_date(date) or existing,
        include_content=True
    )


def save_diary_content(date: str, request: SaveDiaryContentRequest) -> Optional[DiaryItem]:
    """
    保存日记内容（写文件 + 更新 word_count）

    Args:
        date: 日期 YYYY-MM-DD
        request: 保存请求

    Returns:
        Optional[DiaryItem]: 更新后的日记
    """
    existing = diary_repository.get_diary_by_date(date)
    if not existing:
        return None

    _write_diary_content(date, request.content)
    word_count = _calculate_word_count(request.content)
    diary_repository.update_diary(date, {'word_count': word_count})

    return _convert_db_to_diary_item(
        diary_repository.get_diary_by_date(date) or existing,
        include_content=True
    )


async def generate_diary_ai_summary(date: str) -> DiaryAISummaryResponse:
    """
    手动生成指定日期日记 AI 总结，并覆盖写入 diary.ai_summary

    Args:
        date: 日期 YYYY-MM-DD

    Returns:
        DiaryAISummaryResponse: AI 总结内容

    Raises:
        ValueError: 日记为空、日记不存在或 AI 总结无法保存
    """
    item = diary_repository.get_diary_by_date(date)
    if not item:
        created = get_diary(date)
        if not created:
            raise ValueError(f"日记不存在: {date}")
        item = diary_repository.get_diary_by_date(date)
        if not item:
            raise ValueError(f"日记不存在: {date}")

    content = _read_diary_content(date).strip()
    if not content:
        raise ValueError("日记为空，无法总结")

    mood, importance, custom_tags = _map_diary_meta_for_summary(item)
    outdate_summary = item.get("ai_summary")
    result = await ai_diary_summary(date, mood, importance, custom_tags, outdate_summary=outdate_summary)
    summary_content = _extract_summary_content(result)
    if not summary_content:
        raise ValueError("AI 总结生成失败")

    source_hash = _compute_diary_source_hash(content)
    success = diary_repository.update_diary(date, {"ai_summary": summary_content, "diary_source_hash": source_hash})
    if not success:
        raise ValueError("AI 总结保存失败")

    return DiaryAISummaryResponse(content=summary_content)


async def generate_diary_ai_summary_range(request: GenerateDiaryAISummaryRangeRequest) -> GenerateDiaryAISummaryRangeResponse:
    """
    按日期范围生成日记 AI 总结，并根据 existing_summary_mode 应用不同策略
    """
    items = diary_repository.get_diaries_by_date_range(request.start_date, request.end_date)

    # 第一阶段：收集需要处理的项目
    to_process: list[tuple[str, bool]] = []  # (date, is_update)
    skipped: list[str] = []

    for item in items:
        date = item["date"]
        existing_summary = item.get("ai_summary")
        existing_hash = item.get("diary_source_hash")

        content = _read_diary_content(date).strip()
        if not content:
            skipped.append(date)
            continue

        current_hash = _compute_diary_source_hash(content)
        mode = request.existing_summary_mode

        if mode == ExistingSummaryMode.REGENERATE_ALL:
            to_process.append((date, existing_summary is not None))
        elif mode == ExistingSummaryMode.REGENERATE_CHANGED:
            if existing_hash is None or existing_hash != current_hash:
                to_process.append((date, existing_summary is not None))
            else:
                skipped.append(date)
        elif mode == ExistingSummaryMode.SKIP_EXISTING:
            if existing_summary is None:
                to_process.append((date, False))
            else:
                skipped.append(date)

    # 第二阶段：并发处理
    async def process_one(date: str, is_update: bool) -> tuple[str, bool] | tuple[None, None]:
        try:
            await generate_diary_ai_summary(date)
            return (date, is_update)
        except ValueError:
            return (None, None)

    results = await asyncio.gather(*[process_one(d, u) for d, u in to_process])

    created: list[str] = []
    updated: list[str] = []
    for i, r in enumerate(results):
        d, is_up = r
        if d is None:
            skipped.append(to_process[i][0])
        elif is_up:
            updated.append(d)
        else:
            created.append(d)

    return GenerateDiaryAISummaryRangeResponse(
        created_dates=created,
        updated_dates=updated,
        skipped_dates=skipped,
    )


def get_diary_list(start_date: str, end_date: str) -> DiaryListResponse:
    """
    获取日期范围内的日记列表（仅 meta）

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD

    Returns:
        DiaryListResponse: 日记 meta 列表
    """
    items = diary_repository.get_diaries_by_date_range(start_date, end_date)
    meta_items = [_convert_db_to_meta_item(item) for item in items]
    return DiaryListResponse(items=meta_items)


# ==================== 模板管理 ====================

def get_templates() -> TemplateListResponse:
    """
    获取模板列表（扫描模板目录）

    Returns:
        TemplateListResponse: 模板名称列表
    """
    template_dir = _get_template_dir()
    if not template_dir.exists():
        return TemplateListResponse(items=[])

    names = [f.stem for f in sorted(template_dir.glob("*.md"))]
    return TemplateListResponse(items=names)


def get_template(name: str) -> Optional[TemplateItem]:
    """
    获取模板内容

    Args:
        name: 模板名称

    Returns:
        Optional[TemplateItem]: 模板详情，不存在返回 None
    """
    file_path = _get_template_dir() / f"{name}.md"
    if not file_path.exists():
        return None
    try:
        content = file_path.read_text(encoding='utf-8')
        return TemplateItem(name=name, content=content)
    except Exception as e:
        logger.error(f"读取模板 {name} 失败: {e}")
        return None


def create_template(request: CreateTemplateRequest) -> TemplateItem:
    """
    创建模板

    Args:
        request: 创建请求

    Returns:
        TemplateItem: 新创建的模板

    Raises:
        ValueError: 模板名称已存在
    """
    file_path = _get_template_dir() / f"{request.name}.md"
    if file_path.exists():
        raise ValueError(f"模板已存在: {request.name}")

    _ensure_template_dir()
    file_path.write_text(request.content, encoding='utf-8')
    logger.info(f"创建模板 {request.name} 成功")
    return TemplateItem(name=request.name, content=request.content)


def update_template(name: str, request: UpdateTemplateRequest) -> Optional[TemplateItem]:
    """
    更新模板内容

    Args:
        name: 模板名称
        request: 更新请求

    Returns:
        Optional[TemplateItem]: 更新后的模板，不存在返回 None
    """
    file_path = _get_template_dir() / f"{name}.md"
    if not file_path.exists():
        return None

    file_path.write_text(request.content, encoding='utf-8')
    logger.info(f"更新模板 {name} 成功")
    return TemplateItem(name=name, content=request.content)


def delete_template(name: str) -> bool:
    """
    删除模板

    Args:
        name: 模板名称

    Returns:
        bool: 是否成功
    """
    file_path = _get_template_dir() / f"{name}.md"
    if not file_path.exists():
        return False

    try:
        file_path.unlink()
        logger.info(f"删除模板 {name} 成功")
        return True
    except Exception as e:
        logger.error(f"删除模板 {name} 失败: {e}")
        return False
