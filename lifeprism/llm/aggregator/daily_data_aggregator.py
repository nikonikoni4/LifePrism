"""
日常数据聚合器
用于将行为日志数据进行聚合处理，提供更有意义的分析视图
"""
from typing import List, Dict, Tuple
from datetime import datetime


def aggregate_behavior_timeline(
    logs: List[Dict],
    output_limit: int = 20,
    min_duration: int = 0
) -> Tuple[List[Dict], int, int, int, int]:
    """
    将行为日志按时间顺序聚合，合并连续相同的 app+title 记录
    
    Args:
        logs: query_behavior_logs 返回的日志列表，必须按 start_time ASC 排序
              每条记录包含: start_time, end_time, duration, app, title, 
                          category_name, sub_category_name, goal_name
        output_limit: 输出限制条数，默认20条
        min_duration: 最小时长阈值(秒)，合并后时长小于此值的记录将被过滤，默认0（不过滤）
    
    Returns:
        Tuple[List[Dict], int, int, int, int]:
            - merged_logs: 合并后的日志列表（已应用限制）
            - raw_count: 原始条数（合并前）
            - total_merged_count: 合并后的总条数（过滤前）
            - filtered_count: 因时长过滤排除的条数
            - excluded_count: 因数量限制排除的条数
    
    合并后的记录格式:
        - start_time: 合并后的开始时间
        - end_time: 合并后的结束时间
        - total_duration: 合并后的总时长(秒)
        - app: 应用名称
        - title: 窗口标题
        - merge_count: 合并的原始记录数
        - category_name: 主分类名称
        - sub_category_name: 子分类名称
        - goal_name: 目标名称
    """
    if not logs:
        return [], 0, 0, 0, 0
    
    # 记录原始条数
    raw_count = len(logs)
    
    merged_logs = []
    current_group = None
    
    for log in logs:
        app = log.get('app', '')
        title = log.get('title', '')
        
        # 判断是否可以合并到当前组
        if current_group is not None:
            if current_group['app'] == app and current_group['title'] == title:
                # 合并：更新结束时间和累计时长
                current_group['end_time'] = log.get('end_time', '')
                current_group['total_duration'] += log.get('duration', 0)
                current_group['merge_count'] += 1
                continue
        
        # 保存上一个组（如果存在）
        if current_group is not None:
            merged_logs.append(current_group)
        
        # 开始新的组
        current_group = {
            'start_time': log.get('start_time', ''),
            'end_time': log.get('end_time', ''),
            'total_duration': log.get('duration', 0),
            'app': app,
            'title': title,
            'merge_count': 1,
            'category_name': log.get('category_name', ''),
            'sub_category_name': log.get('sub_category_name', ''),
            'goal_name': log.get('goal_name', '')
        }
    
    # 保存最后一个组
    if current_group is not None:
        merged_logs.append(current_group)
    
    # 统计合并后的总条数
    total_merged_count = len(merged_logs)
    
    # 应用时长过滤
    if min_duration > 0:
        filtered_logs = [log for log in merged_logs if log['total_duration'] >= min_duration]
        filtered_count = len(merged_logs) - len(filtered_logs)
        merged_logs = filtered_logs
    else:
        filtered_count = 0
    
    # 应用输出限制
    if output_limit and len(merged_logs) > output_limit:
        excluded_count = len(merged_logs) - output_limit
        merged_logs = merged_logs[:output_limit]
    else:
        excluded_count = 0
    
    return merged_logs, raw_count, total_merged_count, filtered_count, excluded_count


def format_behavior_timeline(
    merged_logs: List[Dict],
    start_time: str,
    end_time: str,
    raw_count: int,
    total_count: int,
    filtered_count: int,
    excluded_count: int
) -> str:
    """
    格式化聚合后的行为时间线为可读文本
    
    Args:
        merged_logs: aggregate_behavior_timeline 返回的合并日志列表
        start_time: 查询开始时间
        end_time: 查询结束时间
        raw_count: 原始条数（合并前）
        total_count: 合并后的总条数
        filtered_count: 因时长过滤排除的条数
        excluded_count: 因数量限制排除的条数
    
    Returns:
        格式化的文本
    
    输出格式示例:
        查询时间: 14:00 ~ 16:00，共 100 条，合并后 25 条，过滤 3 条短记录，因数量限制排除 5 条，获取 17 条：
          - 14:00 ~ 14:15 (15m) VSCode - project/main.py [工作/编程]
          - 14:15 ~ 14:30 (15m) Chrome - Stack Overflow [工作/查资料]
    """
    # 提取时间部分（只保留 HH:MM）
    def extract_time(time_str: str) -> str:
        if ' ' in time_str:
            return time_str.split()[1][:5]
        return time_str[:5] if len(time_str) >= 5 else time_str
    
    # 格式化时长
    def format_duration(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h{minutes}m" if minutes > 0 else f"{hours}h"
    
    # 构建输出
    lines = []
    
    # 标题行
    start_display = extract_time(start_time)
    end_display = extract_time(end_time)
    
    # 计算最终获取的条数
    final_count = len(merged_logs)
    
    # 构建统计信息：共xx条，合并后xx条，过滤xx条，因数量限制排除xx条，获取xx条
    stats_parts = [f"查询时间: {start_display} ~ {end_display}"]
    stats_parts.append(f"共 {raw_count} 条")
    stats_parts.append(f"合并后 {total_count} 条")
    if filtered_count > 0:
        stats_parts.append(f"过滤 {filtered_count} 条短记录")
    if excluded_count > 0:
        stats_parts.append(f"因数量限制排除 {excluded_count} 条")
    stats_parts.append(f"获取 {final_count} 条")
    
    lines.append("，".join(stats_parts) + "：")
    
    # 数据行
    for log in merged_logs:
        log_start = extract_time(log.get('start_time', ''))
        log_end = extract_time(log.get('end_time', ''))
        duration_str = format_duration(log.get('total_duration', 0))
        app = log.get('app', '未知')
        title = log.get('title', '')
        category = log.get('category_name', '')
        sub_category = log.get('sub_category_name', '')
        goal = log.get('goal_name', '')
        merge_count = log.get('merge_count', 1)
        
        # 构建基本信息
        parts = [f"  - {log_start} ~ {log_end} ({duration_str})"]
        
        # 应用和标题
        if title:
            parts.append(f"{app} - {title}")
        else:
            parts.append(app)
        
        # 分类信息
        if category or sub_category:
            if sub_category:
                parts.append(f"[{category}/{sub_category}]")
            else:
                parts.append(f"[{category}]")
        
        # 目标信息
        if goal:
            parts.append(f"{{{goal}}}")
        
        # 合并数量（如果大于1）
        if merge_count > 1:
            parts.append(f"(x{merge_count})")
        
        lines.append(" ".join(parts))
    
    return "\n".join(lines)
