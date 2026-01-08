

def format_seconds(seconds: int) -> str:
    """将秒数格式化为可读时间"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}分钟"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}小时{minutes}分钟"
        return f"{hours}小时"


def format_segment_category_stats(segments_data: list, activities_by_segment: dict = None) -> str:
    """格式化分段统计与分类占比数据（统一输出，包含主要活动记录）
    
    Args:
        segments_data: 包含每个时段的统计和分类信息的列表
        activities_by_segment: 按时段索引组织的活动记录字典 {segment_index: [activities]}
    
    Returns:
        格式化的字符串，每个时段包含时间范围、分类占比和主要活动记录，子分类嵌套在主分类下
    """
    if not segments_data:
        return "  - 暂无数据"
    
    lines = []
    for i, seg in enumerate(segments_data, 1):
        # 时段标题
        lines.append(f"  - 时段{i}（{seg['segment_start']} 至 {seg['segment_end']}）")
        
        # 主分类占比
        categories = seg.get('categories', [])
        sub_categories = seg.get('sub_categories', [])
        
        if categories:
            lines.append("    - 分类占比:")
            
            # 为每个主分类找到对应的子分类
            for cat in categories:
                cat_id = cat['id']
                lines.append(f"      - {cat['name']}: {format_seconds(cat['duration'])}（{cat['percentage']}%）")
                
                # 找到属于这个主分类的子分类
                if sub_categories and cat_id != 'idle':  # 空闲没有子分类
                    related_subs = [sub for sub in sub_categories if sub.get('category_id') == cat_id]
                    for sub in related_subs:
                        lines.append(f"         - {sub['name']}: {format_seconds(sub['duration'])}（{sub['percentage']}%）")
        
        # 主要活动记录
        # 注意：activities_by_segment 使用 0-based segment_index，而 enumerate 从 1 开始
        segment_key = i - 1  # 将 1-based 的 i 转换为 0-based 的 segment_index
        if activities_by_segment and segment_key in activities_by_segment:
            activities = activities_by_segment[segment_key]
            if activities:
                lines.append("    - 主要活动记录:")
                for act in activities:
                    title = act.get('title', '未知')
                    app = act.get('app', '未知')
                    duration = format_seconds(act.get('duration_seconds', 0))
                    lines.append(f"      - {title}（{app}）: {duration}")
    
    return "\n".join(lines)


def format_longest_activities(activities: list) -> str:
    """格式化最长活动数据"""
    if not activities:
        return "  - 暂无数据"
    
    lines = []
    for act in activities:
        title = act.get('title', '未知')
        app = act.get('app', '未知')
        duration = format_seconds(act.get('duration_seconds', 0))
        lines.append(f"  - {title}（{app}）: {duration}")
    return "\n".join(lines)


def format_goal_time_spent(goals: dict) -> str:
    """格式化目标时间花费数据"""
    if not goals:
        return "  - 暂无目标时间记录"
    
    lines = []
    for goal_id, info in goals.items():
        name = info.get('name', '未知目标')
        duration = format_seconds(info.get('duration_seconds', 0))
        lines.append(f"  - {name}: {duration}")
    return "\n".join(lines)


def format_user_notes(notes: list) -> str:
    """格式化用户备注数据"""
    if not notes:
        return "  - 暂无用户备注"
    
    lines = []
    for note in notes:
        start = note.get('start_time', '')
        end = note.get('end_time', '')
        content = note.get('content', '')
        duration = note.get('duration_minutes', 0)
        lines.append(f"  - [{start} ~ {end}]（{duration}分钟）: {content}")
    return "\n".join(lines)


def _format_daily_summary(content: str) -> str:
    """格式化每日重点与任务"""
    if not content:
        return "  - 暂无数据"
    # 增加缩进，使输出整齐
    lines = content.strip().split('\n')
    return "\n".join([f"  {line}" for line in lines])




def format_hourly_logs(hourly_logs):
    """
    格式化按小时分段的活动日志
    
    Args:
        hourly_logs: get_logs_by_time 返回的字典数据
    
    Returns:
        str: 格式化后的文本
        20:00-21:00: 工作/学习(19m)
            1. [2分钟] antigravity - skills - antigravity - skill.md
            2. [2分钟] affine - affine
            3. [2分钟] antigravity - skills - antigravity - skill.md
    """
    if not hourly_logs:
        return "今日暂无活动记录"
    
    output_lines = []
    
    for hour_key in sorted(hourly_logs.keys()):
        hour_data = hourly_logs[hour_key]
        logs = hour_data.get('logs', [])
        category_stats = hour_data.get('category_stats', [])
        
        # 格式化分类统计
        category_parts = []
        for cat in category_stats:
            cat_name = cat.get('name', '未分类')
            duration_min = cat.get('duration', 0) // 60
            category_parts.append(f"{cat_name}({duration_min}m)")
        
        category_str = "，".join(category_parts) if category_parts else "无分类"
        
        # 输出时间段和分类统计
        output_lines.append(f"\n{hour_key}: {category_str}")
        
        # 输出详细日志
        for i, log in enumerate(logs, 1):
            duration_min = log.get('duration', 0) // 60
            app = log.get('app', 'Unknown')
            title = log.get('title', '')
            
            # 格式化输出
            if title:
                output_lines.append(f"  {i}. [{duration_min}分钟] {app} - {title}")
            else:
                output_lines.append(f"  {i}. [{duration_min}分钟] {app}")
    
    return "\n".join(output_lines)


def format_pc_active_time(ratios: list) -> str:
    """
    格式化电脑活跃时间占比
    
    Args:
        ratios: 24个时间段的活跃占比列表
    
    Returns:
        str: 格式化的活跃时间占比字符串，每行一个时间段
        格式示例：
        电脑使用时间：
         - 0~1 : 0
         - 1~2 : 0.5
    """
    if not ratios or len(ratios) != 24:
        return "数据格式错误"
    
    lines = ["电脑使用时间："]
    for i, ratio in enumerate(ratios):
        lines.append(f" - {i}~{i+1} : {ratio}")
    
    return "\n".join(lines)


def format_daily_goal_trend(goal_trends: list) -> str:
    """
    格式化每日目标趋势数据
    
    Args:
        goal_trends: 目标趋势数据列表
    
    Returns:
        str: 格式化的每日目标统计
    """
    if not goal_trends:
        return "暂无目标时间记录"
    
    output_lines = []
    
    for goal_data in goal_trends:
        goal_name = goal_data.get('goal_name', '未知目标')
        total_seconds = goal_data.get('total_seconds', 0)
        date_range_start = goal_data.get('date_range_start', '')
        date_range_end = goal_data.get('date_range_end', '')
        daily_durations = goal_data.get('daily_durations', {})
        
        # 格式化总时长
        total_hours = total_seconds // 3600
        total_minutes = (total_seconds % 3600) // 60
        total_str = f"{total_hours}h {total_minutes}m" if total_hours > 0 else f"{total_minutes}m"
        
        # 构建每日时长列表
        daily_list = []
        for date_str in sorted(daily_durations.keys()):
            seconds = daily_durations[date_str]
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            daily_list.append(f"{date_str}: {time_str}")
        
        # 输出格式
        output_lines.append(f"- {goal_name}: 总时长 {total_str}; 从{date_range_start}~{date_range_end}每天时长为：")
        for daily_item in daily_list:
            output_lines.append(f"  {daily_item}")
        output_lines.append("")  # 空行分隔
    
    return "\n".join(output_lines).strip()


def format_daily_category_trend(category_trends: list) -> str:
    """
    格式化每日分类趋势数据
    
    Args:
        category_trends: 分类趋势数据列表
    
    Returns:
        str: 格式化的每日分类统计
    """
    if not category_trends:
        return "暂无分类时间记录"
    
    output_lines = []
    
    for cat_data in category_trends:
        category_name = cat_data.get('category_name', '未分类')
        total_seconds = cat_data.get('total_seconds', 0)
        date_range_start = cat_data.get('date_range_start', '')
        date_range_end = cat_data.get('date_range_end', '')
        daily_durations = cat_data.get('daily_durations', {})
        
        # 格式化总时长
        total_hours = total_seconds // 3600
        total_minutes = (total_seconds % 3600) // 60
        total_str = f"{total_hours}h {total_minutes}m" if total_hours > 0 else f"{total_minutes}m"
        
        # 构建每日时长列表
        daily_list = []
        for date_str in sorted(daily_durations.keys()):
            seconds = daily_durations[date_str]
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            daily_list.append(f"{date_str}: {time_str}")
        
        # 输出格式
        output_lines.append(f"- {category_name}: 总时长 {total_str}; 从{date_range_start}~{date_range_end}每天时长为：")
        for daily_item in daily_list:
            output_lines.append(f"  {daily_item}")
        output_lines.append("")  # 空行分隔
    
    return "\n".join(output_lines).strip()


def format_computer_usage_schedule(schedule_data: list) -> str:
    """
    格式化电脑使用作息时间为表格格式
    
    Args:
        schedule_data: 作息时间数据列表
    
    Returns:
        str: 格式化的每日电脑使用时间表格
    """
    if not schedule_data:
        return "暂无电脑使用记录"
    
    # 表头
    output_lines = [
        "| 日期 | 最早记录时间 | 最早活动 | 最晚记录时间 | 最晚活动 |",
        "|------|-------------|----------|-------------|----------|"
    ]
    
    for day_data in schedule_data:
        date = day_data.get('date', '-')
        earliest_time = day_data.get('earliest_time', '-')
        earliest_activity = day_data.get('earliest_activity', '-')
        latest_time = day_data.get('latest_time', '-')
        latest_activity = day_data.get('latest_activity', '-')
        
        output_lines.append(
            f"| {date} | {earliest_time} | {earliest_activity} | {latest_time} | {latest_activity} |"
        )
    
    return "\n".join(output_lines)


def format_focus_and_todos(daily_data: list, show_completion_status: bool = True) -> str:
    """
    格式化重点与待办事项
    
    Args:
        daily_data: 每日数据列表
        show_completion_status: 是否显示任务完成状态，默认 True
    
    Returns:
        str: 格式化的每日摘要
    """
    if not daily_data:
        return "暂无数据"
    
    output_lines = []
    
    for day_data in daily_data:
        date = day_data.get('date', '')
        focus = day_data.get('focus', '无')
        todos = day_data.get('todos', [])
        completion_rate = day_data.get('completion_rate', 0)
        
        # output_lines.append(f"date: {date}")
        output_lines.append(f"- focus : {focus}")
        
        if todos:
            if show_completion_status:
                output_lines.append(f"- todos: {completion_rate}%")
            for i, todo in enumerate(todos, 1):
                content = todo.get('content', '')
                if show_completion_status:
                    state = todo.get('state', '')
                    state_display = "completed" if state == 'completed' else "not completed"
                    output_lines.append(f"  {i}. {content} {state_display}")
                else:
                    output_lines.append(f"  {i}. {content}")
        else:
            output_lines.append("- todos:")
            output_lines.append("  (无待办事项)")
        output_lines.append("")  # 换行分隔
    
    return "\n".join(output_lines).strip()


def format_behavior_logs_table(logs: list) -> str:
    """
    将行为日志格式化为表格形式
    
    Args:
        logs: query_behavior_logs 返回的日志列表
    
    Returns:
        str: 表格格式的日志
        
    示例:
        | 开始时间 | 结束时间 | 时长 | 应用 | 标题 | 分类 | 子分类 | 目标 |
        |----------|----------|------|------|------|------|--------|------|
        | 08:30    | 09:15    | 45m  | Chrome | 查看邮件 | 工作 | 邮件处理 | 提高效率 |
    """
    if not logs:
        return "暂无行为日志"
    
    # 表头
    header = "| 开始时间 | 结束时间 | 时长 | 应用 | 标题 | 分类 | 子分类 | 目标 |"
    separator = "|----------|----------|------|------|------|------|--------|------|"
    
    lines = [header, separator]
    
    for log in logs:
        # 提取时间（只保留 HH:MM）
        start_time = log.get('start_time', '')
        end_time = log.get('end_time', '')
        
        # 从 "YYYY-MM-DD HH:MM:SS" 格式提取 HH:MM
        if ' ' in start_time:
            start_time = start_time.split()[1][:5]  # 取 HH:MM
        if ' ' in end_time:
            end_time = end_time.split()[1][:5]  # 取 HH:MM
        
        # 格式化时长
        duration = log.get('duration', 0)
        if duration < 60:
            duration_str = f"{duration}s"
        elif duration < 3600:
            duration_str = f"{duration // 60}m"
        else:
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            duration_str = f"{hours}h{minutes}m" if minutes > 0 else f"{hours}h"
        
        # 其他字段
        app = log.get('app', '')[:10]  # 限制长度
        title = log.get('title', '')[:20]  # 限制长度
        category = log.get('category_name', '')[:8]
        sub_category = log.get('sub_category_name', '')[:10]
        goal = log.get('goal_name', '')[:10]
        
        # 构建行
        row = f"| {start_time:8} | {end_time:8} | {duration_str:4} | {app:10} | {title:20} | {category:8} | {sub_category:10} | {goal:10} |"
        lines.append(row)
    
    return "\n".join(lines)


def format_behavior_logs_lines(logs: list) -> str:
    """
    将行为日志格式化为每行一条的形式
    
    Args:
        logs: query_behavior_logs 返回的日志列表
    
    Returns:
        str: 行格式的日志
        
    示例:
        08:30 ~ 09:15 (45m) Chrome - 查看邮件 [工作/邮件处理] {提高效率}
        09:15 ~ 10:00 (45m) VSCode - 编写代码 [工作/编程] {项目开发}
    """
    if not logs:
        return "暂无行为日志"
    
    lines = []
    
    for log in logs:
        # 提取时间（只保留 HH:MM）
        start_time = log.get('start_time', '')
        end_time = log.get('end_time', '')
        
        # 从 "YYYY-MM-DD HH:MM:SS" 格式提取 HH:MM
        if ' ' in start_time:
            start_time = start_time.split()[1][:5]  # 取 HH:MM
        if ' ' in end_time:
            end_time = end_time.split()[1][:5]  # 取 HH:MM
        
        # 格式化时长
        duration = log.get('duration', 0)
        if duration < 60:
            duration_str = f"{duration}s"
        elif duration < 3600:
            duration_str = f"{duration // 60}m"
        else:
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            duration_str = f"{hours}h{minutes}m" if minutes > 0 else f"{hours}h"
        
        # 其他字段
        app = log.get('app', '未知应用')
        title = log.get('title', '')
        category = log.get('category_name', '')
        sub_category = log.get('sub_category_name', '')
        goal = log.get('goal_name', '')
        
        # 构建行
        line_parts = [f"{start_time} ~ {end_time} ({duration_str})"]
        
        # 应用和标题
        if title:
            line_parts.append(f"{app} - {title}")
        else:
            line_parts.append(app)
        
        # 分类信息
        if category or sub_category:
            if sub_category:
                line_parts.append(f"[{category}/{sub_category}]")
            else:
                line_parts.append(f"[{category}]")
        
        # 目标信息
        if goal:
            line_parts.append(f"{{{goal}}}")
        
        lines.append(" ".join(line_parts))
    
    return "\n".join(lines)


def format_daily_breakdown(breakdown_data: list) -> str:
    """
    格式化每日分解数据为表格形式
    
    Args:
        breakdown_data: get_daily_breakdown 返回的数据列表
    
    Returns:
        str: 表格格式的每日分解数据
    """
    if not breakdown_data:
        return "暂无每日数据"
    
    # 收集所有分类名称
    all_categories = set()
    for day in breakdown_data:
        for cat in day.get('categories', []):
            all_categories.add(cat['name'])
    
    # 取前3个主要分类（按总时长排序）
    category_totals = {}
    for day in breakdown_data:
        for cat in day.get('categories', []):
            name = cat['name']
            category_totals[name] = category_totals.get(name, 0) + cat.get('duration_seconds', 0)
    
    top_categories = sorted(category_totals.keys(), key=lambda x: category_totals[x], reverse=True)[:3]
    
    # 表头
    header_parts = ["日期", "使用时长"]
    header_parts.extend(top_categories)
    header_parts.extend(["电脑启用", "电脑结束"])
    
    output_lines = [" | ".join(header_parts)]
    output_lines.append("|".join(["---"] * len(header_parts)))
    
    for day in breakdown_data:
        date = day.get('date', '-')
        total_hours = day.get('total_duration_hours', 0)
        pc_start = day.get('pc_start_time', '-')
        pc_end = day.get('pc_end_time', '-')
        
        # 获取分类占比
        cat_map = {cat['name']: cat['percentage'] for cat in day.get('categories', [])}
        
        row_parts = [date, f"{total_hours}h"]
        for cat_name in top_categories:
            percentage = cat_map.get(cat_name, 0)
            row_parts.append(f"{percentage}%")
        row_parts.extend([pc_start, pc_end])
        
        output_lines.append(" | ".join(row_parts))
    
    return "\n".join(output_lines)


def format_daily_summaries(summaries: list) -> str:
    """
    格式化每日 AI 摘要
    
    Args:
        summaries: get_daily_summaries 返回的摘要列表
    
    Returns:
        str: 格式化的每日摘要
    """
    if not summaries:
        return "暂无每日摘要"
    
    lines = []
    for item in summaries:
        date = item.get('date', '')
        abstract = item.get('ai_summary_abstract', '')
        if abstract:
            lines.append(f"- {date}: {abstract}")
    
    return "\n".join(lines) if lines else "暂无每日摘要"

