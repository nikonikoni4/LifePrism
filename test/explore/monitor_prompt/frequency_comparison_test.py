"""
监控频率方案对比测试

目的：
1. 不实际截图，模拟不同频率策略下的截图触发
2. 复用现有的engaged状态判断逻辑
3. 统计和对比不同方案的截图数量

输出：
1. Active时间段记录（engaged segments）
2. 9种频率组合的截图数量统计（3方案 x 3等级）
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass
from collections import defaultdict

from lifeprism.monitor.screenshot.models import FrequencyPolicy, WindowContext, CaptureReason
from lifeprism.monitor.screenshot.scheduler import ScreenshotScheduler
from lifeprism.monitor.screenshot.input_tracker import InputActivityTracker


@dataclass
class FrequencyScheme:
    """频率方案定义"""
    name: str
    policies: Dict[int, FrequencyPolicy]  # level -> policy
    scheduled_interval: int


# 定义3个方案
SCHEMES = {
    "原始设计": FrequencyScheme(
        name="原始设计",
        policies={
            1: FrequencyPolicy(level=1, first_active_after_seconds=45, repeat_active_every_seconds=90, enter_cooldown_seconds=8),
            2: FrequencyPolicy(level=2, first_active_after_seconds=30, repeat_active_every_seconds=60, enter_cooldown_seconds=6),
            3: FrequencyPolicy(level=3, first_active_after_seconds=20, repeat_active_every_seconds=40, enter_cooldown_seconds=4),
        },
        scheduled_interval=60,
    ),
    "方案A": FrequencyScheme(
        name="方案A（简单翻倍）",
        policies={
            1: FrequencyPolicy(level=1, first_active_after_seconds=90, repeat_active_every_seconds=180, enter_cooldown_seconds=120),
            2: FrequencyPolicy(level=2, first_active_after_seconds=60, repeat_active_every_seconds=120, enter_cooldown_seconds=90),
            3: FrequencyPolicy(level=3, first_active_after_seconds=40, repeat_active_every_seconds=80, enter_cooldown_seconds=60),
        },
        scheduled_interval=180,
    ),
    "方案A'": FrequencyScheme(
        name="方案A'（数据优化）",
        policies={
            1: FrequencyPolicy(level=1, first_active_after_seconds=60, repeat_active_every_seconds=240, enter_cooldown_seconds=120),
            2: FrequencyPolicy(level=2, first_active_after_seconds=45, repeat_active_every_seconds=180, enter_cooldown_seconds=90),
            3: FrequencyPolicy(level=3, first_active_after_seconds=30, repeat_active_every_seconds=120, enter_cooldown_seconds=60),
        },
        scheduled_interval=180,
    ),
}


@dataclass
class EngagedSegment:
    """Engaged时间段"""
    segment_id: str
    start_time: float
    end_time: float
    duration: float


@dataclass
class CaptureStats:
    """截图统计"""
    scheme_name: str
    level: int
    scheduled_count: int
    active_first_count: int
    active_repeat_count: int
    enter_count: int

    @property
    def active_total(self) -> int:
        return self.active_first_count + self.active_repeat_count

    @property
    def total_count(self) -> int:
        return self.scheduled_count + self.active_total + self.enter_count


def load_window_events(db_path: Path, start_date: str, end_date: str) -> List[Tuple]:
    """加载窗口事件数据"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, duration, app, title
        FROM window_events
        WHERE timestamp >= ? AND timestamp < ?
        ORDER BY timestamp
    """, (start_date, end_date))

    events = cursor.fetchall()
    conn.close()
    return events


def simulate_engaged_segments(
    window_events: List[Tuple],
    keyboard_keepalive: int = 12,
    mouse_keepalive: int = 6
) -> List[EngagedSegment]:
    """
    模拟engaged状态，生成engaged segments

    注意：这里简化处理，假设窗口切换就是有活动
    实际系统中engaged由键鼠事件驱动
    """
    segments = []
    current_segment = None
    segment_counter = 0

    for timestamp_str, duration, app, title in window_events:
        timestamp = datetime.fromisoformat(timestamp_str).timestamp()

        # 简化：假设每个窗口事件都代表用户活动
        # 如果距离上次活动超过keepalive，则结束当前segment
        if current_segment is None:
            # 开始新segment
            segment_counter += 1
            current_segment = {
                'id': f'seg-{segment_counter}',
                'start': timestamp,
                'last_activity': timestamp,
            }
        else:
            # 检查是否超过keepalive
            if timestamp - current_segment['last_activity'] > keyboard_keepalive:
                # 结束当前segment
                segments.append(EngagedSegment(
                    segment_id=current_segment['id'],
                    start_time=current_segment['start'],
                    end_time=current_segment['last_activity'],
                    duration=current_segment['last_activity'] - current_segment['start']
                ))

                # 开始新segment
                segment_counter += 1
                current_segment = {
                    'id': f'seg-{segment_counter}',
                    'start': timestamp,
                    'last_activity': timestamp,
                }
            else:
                # 更新最后活动时间
                current_segment['last_activity'] = timestamp

    # 处理最后一个segment
    if current_segment is not None:
        segments.append(EngagedSegment(
            segment_id=current_segment['id'],
            start_time=current_segment['start'],
            end_time=current_segment['last_activity'],
            duration=current_segment['last_activity'] - current_segment['start']
        ))

    return segments


def simulate_captures(
    segments: List[EngagedSegment],
    scheme: FrequencyScheme,
    level: int,
    time_range: Tuple[float, float]
) -> CaptureStats:
    """
    模拟指定方案和等级下的截图触发

    Args:
        segments: engaged时间段列表
        scheme: 频率方案
        level: 频率等级（1/2/3）
        time_range: 时间范围（start_epoch, end_epoch）

    Returns:
        截图统计结果
    """
    policy = scheme.policies[level]
    scheduler = ScreenshotScheduler(
        policy=policy,
        scheduled_interval_seconds=scheme.scheduled_interval,
        enter_delay_ms=700,
    )

    start_epoch, end_epoch = time_range

    # 统计计数器
    scheduled_count = 0
    active_first_count = 0
    active_repeat_count = 0
    enter_count = 0

    # 记录每个segment是否已触发第一张active
    segment_first_done = set()

    # 模拟时间推进（每秒检查一次）
    current_time = start_epoch
    current_segment_id = None

    while current_time <= end_epoch:
        # 判断当前时间是否在某个segment内
        engaged = False
        for seg in segments:
            if seg.start_time <= current_time <= seg.end_time:
                engaged = True
                current_segment_id = seg.segment_id
                break

        if not engaged:
            current_segment_id = None

        # 构造窗口上下文（简化）
        window = WindowContext(app="TestApp", title="Test", is_afk=False)

        # 调用scheduler评估
        iso_time = datetime.fromtimestamp(current_time).isoformat()
        requests = scheduler.evaluate(
            now_epoch=current_time,
            now_iso=iso_time,
            window=window,
            engaged=engaged,
            engaged_segment_id=current_segment_id,
            enter_events=[],  # 简化：不模拟enter事件
        )

        # 统计截图类型
        for req in requests:
            if req.reason == CaptureReason.SCHEDULED:
                scheduled_count += 1
            elif req.reason == CaptureReason.ACTIVE:
                if req.engaged_segment_id not in segment_first_done:
                    active_first_count += 1
                    segment_first_done.add(req.engaged_segment_id)
                else:
                    active_repeat_count += 1
            elif req.reason == CaptureReason.ENTER:
                enter_count += 1

        # 时间推进1秒
        current_time += 1.0

    return CaptureStats(
        scheme_name=scheme.name,
        level=level,
        scheduled_count=scheduled_count,
        active_first_count=active_first_count,
        active_repeat_count=active_repeat_count,
        enter_count=enter_count,
    )


def print_segments_report(segments: List[EngagedSegment]):
    """打印engaged segments报告"""
    print("=" * 80)
    print("Engaged Segments 分析")
    print("=" * 80)
    print(f"总segment数: {len(segments)}")

    if not segments:
        print("没有engaged segment")
        return

    total_duration = sum(seg.duration for seg in segments)
    avg_duration = total_duration / len(segments)

    print(f"总engaged时长: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)")
    print(f"平均segment时长: {avg_duration:.1f}秒")
    print()

    # 按时长分布统计
    duration_buckets = defaultdict(int)
    for seg in segments:
        if seg.duration < 30:
            duration_buckets["<30s"] += 1
        elif seg.duration < 60:
            duration_buckets["30-60s"] += 1
        elif seg.duration < 120:
            duration_buckets["1-2min"] += 1
        elif seg.duration < 300:
            duration_buckets["2-5min"] += 1
        elif seg.duration < 600:
            duration_buckets["5-10min"] += 1
        else:
            duration_buckets[">=10min"] += 1

    print("时长分布:")
    for bucket in ["<30s", "30-60s", "1-2min", "2-5min", "5-10min", ">=10min"]:
        count = duration_buckets[bucket]
        pct = count / len(segments) * 100
        print(f"  {bucket:10s}: {count:4d} ({pct:5.1f}%)")
    print()


def print_comparison_table(all_stats: List[CaptureStats]):
    """打印对比表格"""
    print("=" * 120)
    print("截图数量对比（9种频率组合）")
    print("=" * 120)

    # 按方案分组
    schemes = {}
    for stat in all_stats:
        if stat.scheme_name not in schemes:
            schemes[stat.scheme_name] = []
        schemes[stat.scheme_name].append(stat)

    # 打印表头
    print(f"{'方案':<20s} | {'等级':<6s} | {'Scheduled':>10s} | {'Active(首)':>10s} | {'Active(续)':>10s} | {'Active合计':>10s} | {'Enter':>10s} | {'总计':>10s}")
    print("-" * 120)

    # 按方案打印
    for scheme_name in ["原始设计", "方案A（简单翻倍）", "方案A'（数据优化）"]:
        if scheme_name not in schemes:
            continue

        stats_list = sorted(schemes[scheme_name], key=lambda x: x.level)
        for i, stat in enumerate(stats_list):
            scheme_col = scheme_name if i == 0 else ""
            level_name = f"L{stat.level}"
            print(f"{scheme_col:<20s} | {level_name:<6s} | {stat.scheduled_count:>10d} | {stat.active_first_count:>10d} | {stat.active_repeat_count:>10d} | {stat.active_total:>10d} | {stat.enter_count:>10d} | {stat.total_count:>10d}")

        if scheme_name != "方案A'（数据优化）":
            print("-" * 120)

    print("=" * 120)


def main():
    # 配置
    db_path = Path("localData/dataset/lifewatch_ai.db")
    start_date = "2026-04-19 00:00:00"
    end_date = "2026-04-21 00:00:00"

    print(f"加载数据: {start_date} -> {end_date}")
    print()

    # 1. 加载窗口事件
    window_events = load_window_events(db_path, start_date, end_date)
    print(f"加载了 {len(window_events)} 条窗口事件")
    print()

    # 2. 模拟engaged segments
    segments = simulate_engaged_segments(window_events)
    print_segments_report(segments)

    # 3. 计算时间范围
    if not segments:
        print("没有engaged segment，无法进行模拟")
        return

    start_epoch = min(seg.start_time for seg in segments)
    end_epoch = max(seg.end_time for seg in segments)
    time_range = (start_epoch, end_epoch)

    print(f"时间范围: {datetime.fromtimestamp(start_epoch)} -> {datetime.fromtimestamp(end_epoch)}")
    print()

    # 4. 模拟9种频率组合
    all_stats = []

    for scheme_name, scheme in SCHEMES.items():
        print(f"模拟方案: {scheme_name}")
        for level in [1, 2, 3]:
            print(f"  L{level}...", end=" ", flush=True)
            stats = simulate_captures(segments, scheme, level, time_range)
            all_stats.append(stats)
            print(f"完成 (总计: {stats.total_count})")
        print()

    # 5. 打印对比表格
    print_comparison_table(all_stats)

    # 6. 保存详细报告
    output_file = Path("test/explore/monitor_prompt/frequency_comparison_report.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"监控频率方案对比报告\n")
        f.write(f"生成时间: {datetime.now().isoformat()}\n")
        f.write(f"数据范围: {start_date} -> {end_date}\n")
        f.write(f"\n")

        # 写入segments信息
        f.write("=" * 80 + "\n")
        f.write("Engaged Segments 详细信息\n")
        f.write("=" * 80 + "\n")
        for seg in segments:
            start_dt = datetime.fromtimestamp(seg.start_time)
            end_dt = datetime.fromtimestamp(seg.end_time)
            f.write(f"{seg.segment_id}: {start_dt} -> {end_dt} (时长: {seg.duration:.1f}s)\n")
        f.write("\n")

        # 写入统计表格
        f.write("=" * 120 + "\n")
        f.write("截图数量对比\n")
        f.write("=" * 120 + "\n")
        f.write(f"{'方案':<20s} | {'等级':<6s} | {'Scheduled':>10s} | {'Active(首)':>10s} | {'Active(续)':>10s} | {'Active合计':>10s} | {'Enter':>10s} | {'总计':>10s}\n")
        f.write("-" * 120 + "\n")

        schemes_dict = {}
        for stat in all_stats:
            if stat.scheme_name not in schemes_dict:
                schemes_dict[stat.scheme_name] = []
            schemes_dict[stat.scheme_name].append(stat)

        for scheme_name in ["原始设计", "方案A（简单翻倍）", "方案A'（数据优化）"]:
            if scheme_name not in schemes_dict:
                continue

            stats_list = sorted(schemes_dict[scheme_name], key=lambda x: x.level)
            for i, stat in enumerate(stats_list):
                scheme_col = scheme_name if i == 0 else ""
                level_name = f"L{stat.level}"
                f.write(f"{scheme_col:<20s} | {level_name:<6s} | {stat.scheduled_count:>10d} | {stat.active_first_count:>10d} | {stat.active_repeat_count:>10d} | {stat.active_total:>10d} | {stat.enter_count:>10d} | {stat.total_count:>10d}\n")

            if scheme_name != "方案A'（数据优化）":
                f.write("-" * 120 + "\n")

    print(f"\n详细报告已保存到: {output_file}")


if __name__ == "__main__":
    main()
