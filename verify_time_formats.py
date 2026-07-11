#!/usr/bin/env python3
"""
Verify time field formats in the database.
Query actual data to check format consistency.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

DB_PATH = r"D:\数据文档\lifeprismData\dataset\lifewatch_ai.db"

# Map tables to their time fields based on inventory
TIME_FIELDS_MAP = {
    'category_map_cache': ['created_at', 'updated_at'],
    'multi_purpose_map_cache': ['created_at', 'updated_at'],
    'single_purpose_map_cache': ['created_at', 'updated_at'],
    'user_app_behavior_log': ['created_at', 'updated_at', 'start_time', 'end_time'],
    'category': ['created_at', 'updated_at'],
    'sub_category': ['created_at', 'updated_at'],
    'tokens_usage_log': ['created_at'],
    'todo_list': ['created_at', 'updated_at', 'date', 'expected_finished_at', 'actual_finished_at'],
    'daily_focus': ['created_at', 'updated_at', 'date'],
    'weekly_focus': ['created_at', 'updated_at', 'year', 'month', 'week_num'],
    'goal': ['created_at', 'updated_at', 'start_date', 'expected_finished_at', 'time_invested_updated_at'],
    'goal_journal': ['created_at', 'updated_at', 'date', 'time'],
    'plan_doc': ['created_at', 'updated_at'],
    'chat_session': ['created_at', 'updated_at'],
    'timeline_custom_block': ['created_at', 'updated_at', 'start_time', 'end_time'],
    'goal_stats': ['created_at', 'date'],
    'daily_report': ['created_at', 'updated_at', 'date'],
    'weekly_report': ['created_at', 'updated_at', 'date'],
    'monthly_report': ['created_at', 'updated_at', 'date'],
    'time_paradoxes': ['created_at', 'updated_at'],
    'diary': ['created_at', 'updated_at', 'date'],
    'mood_types': ['created_at'],
    'mood_entries': ['created_at', 'updated_at'],
    'mood_impacts': ['created_at'],
    'user_values': ['created_at', 'updated_at'],
    'commitments': ['created_at', 'updated_at'],
    'schema_version': ['applied_at'],
    'habits': ['created_at', 'updated_at', 'paused_at'],
    'habit_challenges': ['created_at', 'updated_at', 'start_date', 'end_date', 'finished_at'],
    'habit_checkins': ['created_at', 'date', 'completed_at'],
    'habit_chains': ['created_at', 'updated_at'],
    'habit_chain_nodes': ['created_at', 'updated_at', 'trigger_time'],
    'screen_captures': ['created_at', 'captured_at'],
    'window_events': ['created_at', 'timestamp'],
    'raw_behavior_analysis': ['created_at', 'start_time', 'end_time'],
    'behavior_analysis': ['created_at', 'updated_at', 'start_time', 'end_time'],
    'custom_record_types': ['created_at', 'updated_at'],
    'custom_record_fields': ['created_at'],
}


def classify_format(value: Optional[str]) -> str:
    """Classify time format based on actual value."""
    if value is None:
        return "NULL"

    value = str(value).strip()

    if not value:
        return "EMPTY"

    # Standard SQLite format: YYYY-MM-DD HH:MM:SS
    if len(value) == 19 and value[10] == ' ' and value.count(':') == 2 and value.count('-') == 2:
        return "STANDARD"

    # ISO format with T: YYYY-MM-DDTHH:MM:SS or with microseconds
    if 'T' in value:
        if '.' in value:
            return "ISO_WITH_MICROSECONDS"
        return "ISO_WITH_T"

    # Date only: YYYY-MM-DD
    if len(value) == 10 and value.count('-') == 2:
        return "DATE_ONLY"

    # Time only: HH:MM or HH:MM:SS
    if ':' in value and '-' not in value and len(value) <= 8:
        return "TIME_ONLY"

    # Integer (year, month, week_num)
    if value.isdigit():
        return "INTEGER"

    return f"OTHER ({value[:30]}...)" if len(value) > 30 else f"OTHER ({value})"


def query_time_fields() -> Dict[str, Dict[str, Tuple[Optional[str], str]]]:
    """Query all time fields and return their values and formats."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    results = {}

    for table, fields in TIME_FIELDS_MAP.items():
        results[table] = {}

        field_str = ', '.join(fields)

        try:
            query = f"SELECT {field_str} FROM {table} ORDER BY rowid DESC LIMIT 1"
            cursor.execute(query)
            row = cursor.fetchone()

            if row is None:
                for field in fields:
                    results[table][field] = (None, "NO_DATA")
            else:
                for field, value in zip(fields, row):
                    format_type = classify_format(value)
                    results[table][field] = (value, format_type)

        except sqlite3.Error as e:
            for field in fields:
                results[table][field] = (None, f"ERROR: {str(e)}")

    conn.close()
    return results


def generate_report(results: Dict[str, Dict[str, Tuple[Optional[str], str]]]) -> str:
    """Generate markdown report."""

    # Group by format
    format_groups = defaultdict(list)
    no_data_fields = []

    for table, fields in results.items():
        for field, (value, format_type) in fields.items():
            if format_type == "NO_DATA":
                no_data_fields.append(f"{table}.{field}")
            else:
                format_groups[format_type].append((table, field, value))

    # Build report
    lines = []
    lines.append("# Backend Time Format Verification Report")
    lines.append("")
    lines.append("> **生成时间**: 2026-07-12")
    lines.append("> **数据来源**: 实际数据库查询结果")
    lines.append("> **数据库路径**: `D:\\数据文档\\lifeprismData\\dataset\\lifewatch_ai.db`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Part 1: Format Statistics
    lines.append("## 第一部分：格式统计")
    lines.append("")

    # Standard format
    if "STANDARD" in format_groups:
        lines.append("### 1. 标准格式 (`YYYY-MM-DD HH:MM:SS`)")
        lines.append("")
        lines.append("**SQLite DEFAULT 格式**，空格分隔，无 T，秒级精度")
        lines.append("")
        lines.append("| 表名 | 字段名 | 示例值 |")
        lines.append("|------|--------|--------|")
        for table, field, value in sorted(format_groups["STANDARD"]):
            lines.append(f"| {table} | {field} | `{value}` |")
        lines.append("")
        lines.append(f"**总计**: {len(format_groups['STANDARD'])} 个字段")
        lines.append("")

    # ISO with T
    if "ISO_WITH_T" in format_groups:
        lines.append("### 2. ISO 格式（带 T，无微秒）")
        lines.append("")
        lines.append("**格式**: `YYYY-MM-DDTHH:MM:SS`")
        lines.append("")
        lines.append("| 表名 | 字段名 | 示例值 |")
        lines.append("|------|--------|--------|")
        for table, field, value in sorted(format_groups["ISO_WITH_T"]):
            lines.append(f"| {table} | {field} | `{value}` |")
        lines.append("")
        lines.append(f"**总计**: {len(format_groups['ISO_WITH_T'])} 个字段")
        lines.append("")

    # ISO with microseconds
    if "ISO_WITH_MICROSECONDS" in format_groups:
        lines.append("### 3. ISO 格式（带 T 和微秒）")
        lines.append("")
        lines.append("**格式**: `YYYY-MM-DDTHH:MM:SS.ffffff`")
        lines.append("")
        lines.append("| 表名 | 字段名 | 示例值 |")
        lines.append("|------|--------|--------|")
        for table, field, value in sorted(format_groups["ISO_WITH_MICROSECONDS"]):
            lines.append(f"| {table} | {field} | `{value}` |")
        lines.append("")
        lines.append(f"**总计**: {len(format_groups['ISO_WITH_MICROSECONDS'])} 个字段")
        lines.append("")

    # Date only
    if "DATE_ONLY" in format_groups:
        lines.append("### 4. 日期格式 (`YYYY-MM-DD`)")
        lines.append("")
        lines.append("**纯日期字段**，无时间部分")
        lines.append("")
        lines.append("| 表名 | 字段名 | 示例值 |")
        lines.append("|------|--------|--------|")
        for table, field, value in sorted(format_groups["DATE_ONLY"]):
            lines.append(f"| {table} | {field} | `{value}` |")
        lines.append("")
        lines.append(f"**总计**: {len(format_groups['DATE_ONLY'])} 个字段")
        lines.append("")

    # Time only
    if "TIME_ONLY" in format_groups:
        lines.append("### 5. 时间格式 (`HH:MM` 或 `HH:MM:SS`)")
        lines.append("")
        lines.append("**纯时间字段**，无日期部分")
        lines.append("")
        lines.append("| 表名 | 字段名 | 示例值 |")
        lines.append("|------|--------|--------|")
        for table, field, value in sorted(format_groups["TIME_ONLY"]):
            lines.append(f"| {table} | {field} | `{value}` |")
        lines.append("")
        lines.append(f"**总计**: {len(format_groups['TIME_ONLY'])} 个字段")
        lines.append("")

    # Integer
    if "INTEGER" in format_groups:
        lines.append("### 6. 整数格式")
        lines.append("")
        lines.append("**用于 year, month, week_num 等字段**")
        lines.append("")
        lines.append("| 表名 | 字段名 | 示例值 |")
        lines.append("|------|--------|--------|")
        for table, field, value in sorted(format_groups["INTEGER"]):
            lines.append(f"| {table} | {field} | `{value}` |")
        lines.append("")
        lines.append(f"**总计**: {len(format_groups['INTEGER'])} 个字段")
        lines.append("")

    # NULL
    if "NULL" in format_groups:
        lines.append("### 7. 空值字段")
        lines.append("")
        lines.append("**值为 NULL 的字段**，可能是可选字段")
        lines.append("")
        lines.append("| 表名 | 字段名 |")
        lines.append("|------|--------|")
        for table, field, value in sorted(format_groups["NULL"]):
            lines.append(f"| {table} | {field} |")
        lines.append("")
        lines.append(f"**总计**: {len(format_groups['NULL'])} 个字段")
        lines.append("")

    # Other formats
    other_formats = {k: v for k, v in format_groups.items()
                     if k not in ["STANDARD", "ISO_WITH_T", "ISO_WITH_MICROSECONDS",
                                  "DATE_ONLY", "TIME_ONLY", "INTEGER", "NULL", "NO_DATA"]}
    if other_formats:
        lines.append("### 8. 其他格式")
        lines.append("")
        for format_type, entries in sorted(other_formats.items()):
            lines.append(f"#### {format_type}")
            lines.append("")
            lines.append("| 表名 | 字段名 | 示例值 |")
            lines.append("|------|--------|--------|")
            for table, field, value in sorted(entries):
                lines.append(f"| {table} | {field} | `{value}` |")
            lines.append("")
        lines.append("")

    # Part 2: Anomalies
    lines.append("---")
    lines.append("")
    lines.append("## 第二部分：异常字段")
    lines.append("")

    # Tables with mixed formats
    lines.append("### 1. 同表内格式不一致")
    lines.append("")
    mixed_format_tables = []
    for table, fields in results.items():
        formats_in_table = set()
        for field, (value, format_type) in fields.items():
            if format_type not in ["NO_DATA", "NULL", "INTEGER"]:
                formats_in_table.add(format_type)

        if len(formats_in_table) > 1:
            mixed_format_tables.append((table, formats_in_table, fields))

    if mixed_format_tables:
        for table, formats, fields in mixed_format_tables:
            lines.append(f"#### {table}")
            lines.append("")
            lines.append("| 字段名 | 格式 | 示例值 |")
            lines.append("|--------|------|--------|")
            for field, (value, format_type) in fields.items():
                if format_type not in ["NO_DATA", "NULL", "INTEGER"]:
                    lines.append(f"| {field} | {format_type} | `{value}` |")
            lines.append("")
    else:
        lines.append("**无异常**：所有表内字段格式一致")
        lines.append("")

    # No data fields
    lines.append("### 2. 无数据字段")
    lines.append("")
    if no_data_fields:
        lines.append("以下字段所在表无数据，无法验证格式：")
        lines.append("")
        for field in sorted(no_data_fields):
            lines.append(f"- `{field}`")
        lines.append("")
        lines.append(f"**总计**: {len(no_data_fields)} 个字段")
        lines.append("")
        lines.append("**注意**: 这些字段需要查看代码确认格式")
        lines.append("")
    else:
        lines.append("**无异常**：所有表都有数据")
        lines.append("")

    # Part 3: Verification Results
    lines.append("---")
    lines.append("")
    lines.append("## 第三部分：验证结果")
    lines.append("")

    # Calculate statistics
    total_fields = sum(len(fields) for fields in results.values())
    standard_count = len(format_groups.get("STANDARD", []))
    iso_t_count = len(format_groups.get("ISO_WITH_T", []))
    iso_micro_count = len(format_groups.get("ISO_WITH_MICROSECONDS", []))
    date_only_count = len(format_groups.get("DATE_ONLY", []))
    time_only_count = len(format_groups.get("TIME_ONLY", []))
    integer_count = len(format_groups.get("INTEGER", []))
    null_count = len(format_groups.get("NULL", []))
    no_data_count = len(no_data_fields)

    lines.append("### 统计摘要")
    lines.append("")
    lines.append("| 格式类型 | 字段数量 | 占比 |")
    lines.append("|---------|---------|------|")
    lines.append(f"| 标准格式 (`YYYY-MM-DD HH:MM:SS`) | {standard_count} | {standard_count/total_fields*100:.1f}% |")
    lines.append(f"| ISO 格式（带 T，无微秒） | {iso_t_count} | {iso_t_count/total_fields*100:.1f}% |")
    lines.append(f"| ISO 格式（带 T 和微秒） | {iso_micro_count} | {iso_micro_count/total_fields*100:.1f}% |")
    lines.append(f"| 日期格式 | {date_only_count} | {date_only_count/total_fields*100:.1f}% |")
    lines.append(f"| 时间格式 | {time_only_count} | {time_only_count/total_fields*100:.1f}% |")
    lines.append(f"| 整数格式 | {integer_count} | {integer_count/total_fields*100:.1f}% |")
    lines.append(f"| 空值 | {null_count} | {null_count/total_fields*100:.1f}% |")
    lines.append(f"| 无数据 | {no_data_count} | {no_data_count/total_fields*100:.1f}% |")
    lines.append(f"| **总计** | **{total_fields}** | **100%** |")
    lines.append("")

    # Key findings
    lines.append("### 关键发现")
    lines.append("")

    # Format inconsistency between SQLite and Python
    if iso_t_count > 0 or iso_micro_count > 0:
        lines.append("#### 🔴 格式不一致问题")
        lines.append("")
        lines.append(f"- **SQLite DEFAULT 格式**: `YYYY-MM-DD HH:MM:SS` ({standard_count} 个字段)")
        lines.append(f"- **Python `.isoformat()` 格式**: `YYYY-MM-DDTHH:MM:SS[.ffffff]` ({iso_t_count + iso_micro_count} 个字段)")
        lines.append("")
        lines.append("**影响**:")
        lines.append("1. 同一表内 `created_at` 和 `updated_at` 可能格式不一致")
        lines.append("2. 云端同步时可能因格式不一致判断为\"需要更新\"")
        lines.append("3. 字符串比较可能出错（`YYYY-MM-DD HH:MM:SS` < `YYYY-MM-DDTHH:MM:SS`）")
        lines.append("")

    # Mixed formats in same table
    if mixed_format_tables:
        lines.append("#### 🟡 同表内格式不一致")
        lines.append("")
        for table, formats, _ in mixed_format_tables:
            lines.append(f"- **{table}**: {', '.join(sorted(formats))}")
        lines.append("")

    # No data
    if no_data_count > 0:
        lines.append("#### ⚠️ 无数据字段")
        lines.append("")
        lines.append(f"有 {no_data_count} 个字段所在表无数据，需要查看代码确认格式")
        lines.append("")

    # Consistency score
    lines.append("### 格式一致性评分")
    lines.append("")

    # Calculate consistency score
    consistent_count = standard_count + date_only_count + time_only_count + integer_count
    verifiable_count = total_fields - no_data_count - null_count
    if verifiable_count > 0:
        consistency_score = (consistent_count / verifiable_count) * 100
    else:
        consistency_score = 0

    lines.append(f"**一致性得分**: {consistency_score:.1f}%")
    lines.append("")
    lines.append("**计算方式**:")
    lines.append(f"- 一致字段数: {consistent_count}")
    lines.append(f"- 可验证字段数: {verifiable_count}")
    lines.append(f"- 得分 = {consistent_count} / {verifiable_count} × 100%")
    lines.append("")

    if consistency_score >= 90:
        lines.append("✅ **评级**: 优秀（≥90%）")
    elif consistency_score >= 75:
        lines.append("🟡 **评级**: 良好（75-89%）")
    elif consistency_score >= 60:
        lines.append("🟠 **评级**: 中等（60-74%）")
    else:
        lines.append("🔴 **评级**: 需改进（<60%）")
    lines.append("")

    # Recommendations
    lines.append("### 修复建议")
    lines.append("")

    if iso_t_count > 0 or iso_micro_count > 0:
        lines.append("#### 1. 统一 Python 代码写入格式（高优先级）")
        lines.append("")
        lines.append("**问题**: Python 代码使用 `.isoformat()` 导致格式与 SQLite DEFAULT 不一致")
        lines.append("")
        lines.append("**修复**:")
        lines.append("```python")
        lines.append("# 错误写法")
        lines.append('data["updated_at"] = datetime.now().isoformat()  # 带 T')
        lines.append("")
        lines.append("# 正确写法")
        lines.append('data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 不带 T')
        lines.append("```")
        lines.append("")
        lines.append("**涉及文件**:")
        lines.append("- `lifeprism/repository/base_providers/lw_base_data_provider.py:1184`")
        lines.append("- `lifeprism/repository/providers/habit_providers.py:403`")
        lines.append("- `lifeprism/repository/providers/map_cache_providers.py:311, 672`")
        lines.append("")

    if mixed_format_tables:
        lines.append("#### 2. 修复同表内格式不一致（高优先级）")
        lines.append("")
        for table, _, _ in mixed_format_tables:
            lines.append(f"- **{table}**: 检查业务逻辑代码，确保所有时间字段使用相同格式")
        lines.append("")

    if no_data_count > 0:
        lines.append("#### 3. 验证无数据字段（中优先级）")
        lines.append("")
        lines.append("以下字段需要查看代码确认格式：")
        lines.append("")
        for field in sorted(no_data_fields)[:10]:  # Show first 10
            lines.append(f"- `{field}`")
        if no_data_count > 10:
            lines.append(f"- ... 还有 {no_data_count - 10} 个字段")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append(f"1. **总字段数**: {total_fields} 个时间字段")
    lines.append(f"2. **一致性得分**: {consistency_score:.1f}%")
    lines.append(f"3. **主要问题**:")
    lines.append(f"   - 格式不一致: {iso_t_count + iso_micro_count} 个字段使用 ISO 格式（带 T）")
    lines.append(f"   - 同表不一致: {len(mixed_format_tables)} 个表")
    lines.append(f"   - 无数据字段: {no_data_count} 个字段")
    lines.append("")
    lines.append("**下一步**:")
    lines.append("1. 修复 Python 代码中的 `.isoformat()` 调用")
    lines.append("2. 验证无数据字段的格式")
    lines.append("3. 测试数据同步逻辑")
    lines.append("")

    return '\n'.join(lines)


def main():
    print("Querying database...")
    results = query_time_fields()

    print("Generating report...")
    report = generate_report(results)

    output_path = Path(__file__).parent / "docs" / "generated" / "backend-time-format-verification.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\nReport generated: {output_path}")
    print(f"Total fields: {sum(len(fields) for fields in results.values())}")


if __name__ == '__main__':
    main()
