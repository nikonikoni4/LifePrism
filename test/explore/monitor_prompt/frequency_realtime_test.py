"""
监控频率方案实时对比测试

目的：
1. 真实运行监控系统，监听键鼠事件，判断engaged状态
2. 不实际截图，只记录"如果截图会在什么时候触发"
3. 同时模拟9种频率方案，记录每种方案的截图触发次数
4. 输出：engaged时间段 + 9种方案的截图数量对比

运行方式：
    python test/explore/monitor_prompt/frequency_realtime_test.py --duration 3600

参数：
    --duration: 运行时长（秒），默认3600（1小时）
"""

import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, field
from collections import defaultdict

from pynput import keyboard, mouse

from lifeprism.monitor.screenshot.models import FrequencyPolicy, WindowContext, CaptureReason
from lifeprism.monitor.screenshot.scheduler import ScreenshotScheduler
from lifeprism.monitor.screenshot.input_tracker import InputActivityTracker
from lifeprism.monitor.windows_monitor.monitor import WindowMonitor
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider


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
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time > 0 else 0.0


@dataclass
class CaptureRecord:
    """截图记录"""
    timestamp: float
    reason: CaptureReason
    scheme_name: str
    level: int
    segment_id: str = None


@dataclass
class SchemeStats:
    """方案统计"""
    scheme_name: str
    level: int
    scheduled_count: int = 0
    active_first_count: int = 0
    active_repeat_count: int = 0
    enter_count: int = 0

    @property
    def active_total(self) -> int:
        return self.active_first_count + self.active_repeat_count

    @property
    def total_count(self) -> int:
        return self.scheduled_count + self.active_total + self.enter_count


class RealtimeMonitorTest:
    """实时监控测试"""

    def __init__(self, duration_seconds: int):
        self.duration_seconds = duration_seconds
        self.start_time = None
        self.end_time = None

        # 监控组件（不启动WindowMonitor的后台线程，只用它的snapshot方法）
        self.window_monitor = WindowMonitor(MonitorDataProvider())

        self.input_tracker = InputActivityTracker(
            keyboard_keepalive_seconds=12,
            mouse_keepalive_seconds=6,
            time_source=time.time,
            segment_id_factory=lambda: f"seg-{int(time.time() * 1000)}",
        )

        # 为每个方案和等级创建独立的scheduler
        self.schedulers: Dict[tuple, ScreenshotScheduler] = {}
        for scheme_name, scheme in SCHEMES.items():
            for level in [1, 2, 3]:
                key = (scheme_name, level)
                self.schedulers[key] = ScreenshotScheduler(
                    policy=scheme.policies[level],
                    scheduled_interval_seconds=scheme.scheduled_interval,
                    enter_delay_ms=700,
                )

        # 数据记录
        self.segments: List[EngagedSegment] = []
        self.current_segment: EngagedSegment = None
        self.capture_records: List[CaptureRecord] = []

        # 键鼠监听器
        self.keyboard_listener = None
        self.mouse_listener = None

        # 运行标志
        self.running = False

    def on_keyboard_event(self, key):
        """键盘事件回调"""
        try:
            key_name = key.char if hasattr(key, 'char') else key.name
        except AttributeError:
            key_name = str(key)

        self.input_tracker.record_keyboard_event(key_name)

    def on_mouse_event(self, x, y, button=None, pressed=None):
        """鼠标事件回调"""
        self.input_tracker.record_mouse_event()

    def evaluate_all_schemes(self):
        """评估所有方案的截图触发"""
        now = time.time()
        now_iso = datetime.fromtimestamp(now).isoformat()

        # 获取当前窗口上下文
        window_context = self.window_monitor.snapshot_window_context()

        # 获取engaged状态
        input_snapshot = self.input_tracker.snapshot()
        engaged = input_snapshot.engaged
        segment_id = input_snapshot.engaged_segment_id

        # 获取pending enter事件
        enter_events = self.input_tracker.consume_enter_events()

        # 记录engaged segment
        if engaged and segment_id:
            if self.current_segment is None or self.current_segment.segment_id != segment_id:
                # 结束上一个segment
                if self.current_segment is not None:
                    self.current_segment.end_time = now

                # 开始新segment
                self.current_segment = EngagedSegment(
                    segment_id=segment_id,
                    start_time=now,
                )
                self.segments.append(self.current_segment)
        elif not engaged and self.current_segment is not None:
            # 结束当前segment
            self.current_segment.end_time = now
            self.current_segment = None

        # 评估每个方案
        for (scheme_name, level), scheduler in self.schedulers.items():
            requests = scheduler.evaluate(
                now_epoch=now,
                now_iso=now_iso,
                window=window_context,
                engaged=engaged,
                engaged_segment_id=segment_id,
                enter_events=enter_events,
            )

            # 记录截图触发
            for req in requests:
                self.capture_records.append(CaptureRecord(
                    timestamp=now,
                    reason=req.reason,
                    scheme_name=scheme_name,
                    level=level,
                    segment_id=req.engaged_segment_id,
                ))

    def run(self):
        """运行监控测试"""
        print("=" * 80)
        print("监控频率方案实时对比测试")
        print("=" * 80)
        print(f"运行时长: {self.duration_seconds}秒 ({self.duration_seconds/60:.1f}分钟)")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("正在监听键鼠事件...")
        print("按 Ctrl+C 提前结束测试")
        print("=" * 80)
        print()

        self.start_time = time.time()
        self.running = True

        # 启动键鼠监听器
        self.keyboard_listener = keyboard.Listener(on_press=self.on_keyboard_event)
        self.mouse_listener = mouse.Listener(
            on_move=self.on_mouse_event,
            on_click=lambda x, y, button, pressed: self.on_mouse_event(x, y, button, pressed)
        )

        self.keyboard_listener.start()
        self.mouse_listener.start()

        try:
            # 主循环：每秒评估一次
            while self.running:
                current_time = time.time()

                # 检查是否超时
                if current_time - self.start_time >= self.duration_seconds:
                    break

                # 评估所有方案
                self.evaluate_all_schemes()

                # 每10秒打印一次进度
                elapsed = current_time - self.start_time
                if int(elapsed) % 10 == 0:
                    progress = elapsed / self.duration_seconds * 100
                    print(f"进度: {elapsed:.0f}s / {self.duration_seconds}s ({progress:.1f}%)", end="\r")

                # 等待1秒
                time.sleep(1.0)

        except KeyboardInterrupt:
            print("\n\n用户中断测试")

        finally:
            self.running = False
            self.end_time = time.time()

            # 停止监听器
            if self.keyboard_listener:
                self.keyboard_listener.stop()
            if self.mouse_listener:
                self.mouse_listener.stop()

            # 结束最后一个segment
            if self.current_segment is not None:
                self.current_segment.end_time = self.end_time

            print("\n\n测试完成，正在生成报告...")
            self.generate_report()

    def generate_report(self):
        """生成测试报告"""
        actual_duration = self.end_time - self.start_time

        # 统计engaged segments
        valid_segments = [seg for seg in self.segments if seg.duration > 0]
        total_engaged_time = sum(seg.duration for seg in valid_segments)

        print("\n")
        print("=" * 80)
        print("Engaged Segments 分析")
        print("=" * 80)
        print(f"测试时长: {actual_duration:.1f}秒 ({actual_duration/60:.1f}分钟)")
        print(f"总segment数: {len(valid_segments)}")
        print(f"总engaged时长: {total_engaged_time:.1f}秒 ({total_engaged_time/60:.1f}分钟)")

        if valid_segments:
            avg_duration = total_engaged_time / len(valid_segments)
            print(f"平均segment时长: {avg_duration:.1f}秒")

            # 时长分布
            duration_buckets = defaultdict(int)
            for seg in valid_segments:
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

            print("\n时长分布:")
            for bucket in ["<30s", "30-60s", "1-2min", "2-5min", "5-10min", ">=10min"]:
                count = duration_buckets[bucket]
                pct = count / len(valid_segments) * 100 if valid_segments else 0
                print(f"  {bucket:10s}: {count:4d} ({pct:5.1f}%)")

        print()

        # 统计每个方案的截图数量
        stats_dict = {}
        segment_first_done = defaultdict(set)  # (scheme, level) -> set of segment_ids

        for record in self.capture_records:
            key = (record.scheme_name, record.level)

            if key not in stats_dict:
                stats_dict[key] = SchemeStats(
                    scheme_name=record.scheme_name,
                    level=record.level,
                )

            stats = stats_dict[key]

            if record.reason == CaptureReason.SCHEDULED:
                stats.scheduled_count += 1
            elif record.reason == CaptureReason.ACTIVE:
                if record.segment_id not in segment_first_done[key]:
                    stats.active_first_count += 1
                    segment_first_done[key].add(record.segment_id)
                else:
                    stats.active_repeat_count += 1
            elif record.reason == CaptureReason.ENTER:
                stats.enter_count += 1

        # 打印对比表格
        print("=" * 120)
        print("截图数量对比（9种频率组合）")
        print("=" * 120)
        print(f"{'方案':<20s} | {'等级':<6s} | {'Scheduled':>10s} | {'Active(首)':>10s} | {'Active(续)':>10s} | {'Active合计':>10s} | {'Enter':>10s} | {'总计':>10s}")
        print("-" * 120)

        for scheme_name in ["原始设计", "方案A", "方案A'（数据优化）"]:
            for i, level in enumerate([1, 2, 3]):
                key = (scheme_name, level)
                stats = stats_dict.get(key, SchemeStats(scheme_name=scheme_name, level=level))

                scheme_col = scheme_name if i == 0 else ""
                level_name = f"L{level}"
                print(f"{scheme_col:<20s} | {level_name:<6s} | {stats.scheduled_count:>10d} | {stats.active_first_count:>10d} | {stats.active_repeat_count:>10d} | {stats.active_total:>10d} | {stats.enter_count:>10d} | {stats.total_count:>10d}")

            if scheme_name != "方案A'（数据优化）":
                print("-" * 120)

        print("=" * 120)
        print()

        # 保存详细报告
        self.save_report(valid_segments, stats_dict, actual_duration)

    def save_report(self, segments: List[EngagedSegment], stats_dict: Dict, duration: float):
        """保存详细报告到文件"""
        output_file = Path("test/explore/monitor_prompt/frequency_realtime_report.txt")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("监控频率方案实时对比报告\n")
            f.write(f"生成时间: {datetime.now().isoformat()}\n")
            f.write(f"测试时长: {duration:.1f}秒 ({duration/60:.1f}分钟)\n")
            f.write(f"开始时间: {datetime.fromtimestamp(self.start_time).isoformat()}\n")
            f.write(f"结束时间: {datetime.fromtimestamp(self.end_time).isoformat()}\n")
            f.write("\n")

            # 写入segments信息
            f.write("=" * 80 + "\n")
            f.write("Engaged Segments 详细信息\n")
            f.write("=" * 80 + "\n")
            f.write(f"总segment数: {len(segments)}\n")
            f.write(f"总engaged时长: {sum(seg.duration for seg in segments):.1f}秒\n")
            f.write("\n")

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

            for scheme_name in ["原始设计", "方案A", "方案A'（数据优化）"]:
                for i, level in enumerate([1, 2, 3]):
                    key = (scheme_name, level)
                    stats = stats_dict.get(key, SchemeStats(scheme_name=scheme_name, level=level))

                    scheme_col = scheme_name if i == 0 else ""
                    level_name = f"L{level}"
                    f.write(f"{scheme_col:<20s} | {level_name:<6s} | {stats.scheduled_count:>10d} | {stats.active_first_count:>10d} | {stats.active_repeat_count:>10d} | {stats.active_total:>10d} | {stats.enter_count:>10d} | {stats.total_count:>10d}\n")

                if scheme_name != "方案A'（数据优化）":
                    f.write("-" * 120 + "\n")

        print(f"详细报告已保存到: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="监控频率方案实时对比测试")
    parser.add_argument("--duration", type=int, default=3600, help="运行时长（秒），默认3600（1小时）")
    args = parser.parse_args()

    test = RealtimeMonitorTest(duration_seconds=args.duration)
    test.run()


if __name__ == "__main__":
    main()
