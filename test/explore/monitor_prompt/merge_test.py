
from dataclasses import dataclass
import json
from pathlib import Path
import asyncio

from lifeprism.llm.providers.llm_providers.build_llm_client import create_llm_client



CHUNK_MINUTES = 15

# 语义合并的系统提示词将原来CHUNK_MINUTES的语义进行合并。
# 输入的数据是：分析输出的所有数据
MERGE_SYSTEMP_PROMPT=f"""
    ## 任务
    你需要对输入的行为语义进行合并，使得相似且相邻的行为得以合并，使得不相邻或语义不同的行为分离。

    ## 核心原则
    宁愿合并也不要将行为分离的过于分散。即有明显行为变化的时间段才需要分离。

    ## 合并判断标准
    对于两个时间段A和B，同时满足以下两个条件时才合并：

    1. **时间相邻**：两个时间段相邻（间隔不超过{CHUNK_MINUTES}分钟）

    2. **行为一致**：A时间段和B时间段进行着符合用户同一个目的、逻辑一致或同类型的行为
       - 例如：A时间段在编写某个功能，B时间段在调试该功能（具有时间连续性和一致性）
       - 例如：A时间段在视频网站看视频，B时间段在另一个视频网站看视频（都属于娱乐行为）
       - 例如：A时间段在做某个任务的准备工作，B时间段在执行该任务（同一目的）

    **不满足以上条件则分离**。

    ## 执行步骤
    1. 按时间顺序遍历每个时间段，从第一个开始
    2. 判断当前时间段之后是否有相邻的时间段：
       - 不存在：直接总结当前时间段的所有行为（包括已合并的内容）
       - 存在：判断是否满足合并条件
         - 满足：合并两个时间段，继续判断下一个
         - 不满足：总结当前时间段，开始处理下一个时间段

    ## 注意事项
    当你没有把握判断时，倾向于合并而不是分离，这样不会违反核心原则。

    ## 输出格式
    输出一个 JSON 数组，每个元素包含以下字段：
    - start_time: 合并后的开始时间，格式 YYYY-MM-DD HH:MM:SS
    - end_time: 合并后的结束时间，格式 YYYY-MM-DD HH:MM:SS
    - behavior_summary: 这段时间的行为总结（一句话概括）
    - behaviors: 原始输入的分点内容（保持原格式，用换行符分隔）

    ## 输出示例
    [
        {{
            "start_time": "2026-04-19 11:00:00",
            "end_time": "2026-04-19 11:10:00",
            "behavior_summary": "用户针对habit模块习惯界面链条时间计算bug进行修复开发准备，梳理bug复现场景和修复方案，查询相关参考资料后，编写了具体修复开发计划，规划好了前后端的修改任务。",
            "behaviors": "1. 和AI讨论habit模块习惯链条时间计算bug的修复方案，梳理时间计算算法和后端API契约，记录bug的复现场景\n2. 调用AI获取项目文档和系统化调试bug的相关参考资料\n3. 编写habit链条时间计算bug的修复开发计划文档，规划前后端具体修改任务"
        }}
    ]

"""

SUMMARY_SYSTEM_PROMPT = """
## task 
你需要对输入的用户行为进行总结

## 需要做的事情
1. 输入内容如果包含相似、重复的内容需要合理合并
2. 输入的内容如果包含逻辑关系，可以进行合理推理，比如用户先编写xx计划，然后执行xx计划等
3. 如果所做的事情与用户的目标相关，需要结合目标进行说明。但不能直接说在进行xx目标，而是要结合具体行为和目标关系说明

## 不要做的事情
1. 不要简单重复输入内容中已经有点内容
2. 输出不要超过200字
3. 输出中不要直接包含“用户”等主语
4. 不要使用“完成了”等字眼，因为仅凭输入是无法判断是否完成了某项工作（即使输入的行为包含“完成”类似的语义也不能在总结中输出“完成”），只描述做了什么内容，而不是完成了什么

## 输入说明
输入行为的顺序就是真实动作的时间顺序

## 输出契约
直接输出总结内容

例如：
完成了habit模块习惯界面链条时间计算bug的全流程修复开发工作，期间穿插查看AI对 心理学概念的解析，并在思源笔记中编写整理《复利效应》的相关读书笔记

"""

@dataclass
class BehaviorAnalysis:
    start_time: str # YYYY-MM-DD HH-MM-SS
    end_time : str
    screen_count: int
    behavior_summary : str
    behaviors : str

@dataclass
class SingalBucketAnalysis:
    start_time : str # YYYY-MM-DD HH-MM-SS
    end_time : str
    behavior : str
    screen_count  :int


def merge_behaviors_by_time(
    bucket_list: list[SingalBucketAnalysis],
    chunk_minutes: int = CHUNK_MINUTES
) -> list[BehaviorAnalysis]:
    """
    根据时间间隔合并行为分析结果

    Args:
        bucket_list: 原始的时间段列表
        chunk_minutes: 时间间隔阈值（分钟），超过此间隔则分离

    Returns:
        合并后的行为分析列表
    """
    from datetime import datetime

    if not bucket_list:
        return []

    # 按时间排序
    sorted_buckets = sorted(bucket_list, key=lambda x: x.start_time)

    merged_results: list[BehaviorAnalysis] = []
    current_group: list[SingalBucketAnalysis] = [sorted_buckets[0]]

    for i in range(1, len(sorted_buckets)):
        prev_bucket = sorted_buckets[i - 1]
        curr_bucket = sorted_buckets[i]

        # 解析时间
        prev_end = datetime.fromisoformat(prev_bucket.end_time)
        curr_start = datetime.fromisoformat(curr_bucket.start_time)

        # 计算时间间隔（分钟）
        time_gap = (curr_start - prev_end).total_seconds() / 60

        # 判断是否合并
        if time_gap <= chunk_minutes:
            # 合并到当前组
            current_group.append(curr_bucket)
        else:
            # 保存当前组，开始新组
            merged_results.append(_create_behavior_analysis(current_group))
            current_group = [curr_bucket]

    # 处理最后一组
    if current_group:
        merged_results.append(_create_behavior_analysis(current_group))

    return merged_results


def _create_behavior_analysis(buckets: list[SingalBucketAnalysis]) -> BehaviorAnalysis:
    """
    将一组时间段合并为一个行为分析结果

    Args:
        buckets: 需要合并的时间段列表

    Returns:
        合并后的行为分析
    """
    # 获取起止时间
    start_time = buckets[0].start_time.replace('T', ' ')
    end_time = buckets[-1].end_time.replace('T', ' ')

    # 合并所有行为描述
    behaviors_list = [f"{i+1}. {bucket.behavior}" for i, bucket in enumerate(buckets)]
    behaviors = "\n".join(behaviors_list)
    screen_count = sum(bucket.screen_count for bucket in buckets)

    # 生成简单的总结（可以后续用 LLM 优化）
    behavior_summary = ""

    return BehaviorAnalysis(
        start_time=start_time,
        end_time=end_time,
        screen_count=screen_count,
        behavior_summary=behavior_summary,
        behaviors=behaviors
    ) 



# 数据准备
def load_bucket_analysis_from_json(
    json_path: str = "test/explore/monitor_prompt/screenshot_analysis_v2_result.json",
) -> list[SingalBucketAnalysis]:
    raw = json.loads(Path(json_path).read_text(encoding="utf-8"))
    return [SingalBucketAnalysis(**item) for item in raw]


bucket_analysis_list: list[SingalBucketAnalysis] = load_bucket_analysis_from_json()
behavior_analysis_list = merge_behaviors_by_time(bucket_analysis_list,15)
for i in range(len(behavior_analysis_list)):
    print(behavior_analysis_list[i])

llm = create_llm_client()


async def main() -> None:
    summaries: list[dict] = []
    for item in behavior_analysis_list:
        user_prompt = f"""
## 用户目标
1. 完成《复利效应》读书笔记编写
2. 修复habits模块的相关bug

## 用户数据
{item.behaviors}
"""
        messages = [
            {'role': "system", 'content': SUMMARY_SYSTEM_PROMPT},
            {'role': "user", 'content': user_prompt}
        ]
        response = await llm.chat(messages)
        item.behavior_summary = response.content.strip() if response and response.content else ""
        summaries.append({
            "start_time": item.start_time,
            "end_time": item.end_time,
            "screen_count": item.screen_count,
            "behavior_summary": item.behavior_summary,
            "behaviors": item.behaviors,
        })

    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())