"""
Prompt 管理系统使用示例

展示如何在实际代码中使用 PromptLoader 和 Prompts 类
"""

from pathlib import Path

from lifeprism.llm.prompts import PromptLoader, PromptRef, Prompts


def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("示例 1: 基本使用")
    print("=" * 60)

    # 初始化 loader
    prompts_dir = Path("templates/prompts")
    loader = PromptLoader(prompts_dir)

    # 推荐方式：使用 Prompts 类
    prompt = loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)
    print(f"✓ 加载成功: {len(prompt)} 字符")

    # 向后兼容：字符串方式
    prompt_old = loader.load_prompt("activity_summary", module="schedule")
    print(f"✓ 字符串方式也可用: {len(prompt_old)} 字符")


def example_with_parameters():
    """参数注入示例"""
    print("\n" + "=" * 60)
    print("示例 2: 参数注入")
    print("=" * 60)

    prompts_dir = Path("templates/prompts")
    loader = PromptLoader(prompts_dir)

    # 使用 Prompts 类加载带参数的 prompt
    prompt = loader.load_prompt(
        Prompts.Schedule.UPDATE_MEMORY,
        recent_state_path="templates/user/daily_data/recent_status.md",
        user_md_path="templates/user/user.md",
        diary_path_template="templates/user/diary/{year}/{month}/{year}-{month}-{day}.md",
    )

    print(f"✓ 参数注入成功: {len(prompt)} 字符")


def example_version_management():
    """版本管理示例"""
    print("\n" + "=" * 60)
    print("示例 3: 版本管理")
    print("=" * 60)

    prompts_dir = Path("templates/prompts")
    loader = PromptLoader(prompts_dir)

    # 加载默认版本（active_version）
    prompt_default = loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)
    print(f"✓ 默认版本: {len(prompt_default)} 字符")

    # 加载指定版本
    prompt_v1 = loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY, version="v1")
    print(f"✓ v1 版本: {len(prompt_v1)} 字符")

    # 查询可用版本
    versions = loader.get_available_versions("schedule", "activity_summary")
    print(f"✓ 可用版本: {versions}")

    # 查询元数据
    metadata = loader.get_prompt_metadata("schedule", "activity_summary")
    print(f"✓ 当前激活版本: {metadata['active_version']}")


def example_usage_stats():
    """使用统计示例"""
    print("\n" + "=" * 60)
    print("示例 4: 使用统计")
    print("=" * 60)

    prompts_dir = Path("templates/prompts")
    loader = PromptLoader(prompts_dir)

    # 加载几次 prompt
    loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)
    loader.load_prompt(Prompts.Schedule.MOOD_SUMMARY)
    loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)

    # 查询统计数据
    stats = loader.get_usage_stats("activity_summary")
    print(f"✓ activity_summary 使用次数: {stats['total_count']}")
    print(f"✓ 版本统计: {stats['version_stats']}")
    print(f"✓ 最后使用: {stats['last_used']}")

    # 查询所有统计
    all_stats = loader.get_usage_stats()
    print(f"✓ 总共使用了 {len(all_stats)} 个不同的 prompts")


def example_real_world_usage():
    """实际应用场景示例"""
    print("\n" + "=" * 60)
    print("示例 5: 实际应用场景")
    print("=" * 60)

    prompts_dir = Path("templates/prompts")
    loader = PromptLoader(prompts_dir)

    # 场景 1: 定时任务 - 生成活动总结
    print("\n场景 1: 生成活动总结")
    activity_prompt = loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)
    print(f"  ✓ 获取 prompt: {len(activity_prompt)} 字符")
    # 这里会调用 LLM API，传入 activity_prompt 和用户数据

    # 场景 2: 定时任务 - 更新用户记忆
    print("\n场景 2: 更新用户记忆")
    memory_prompt = loader.load_prompt(
        Prompts.Schedule.UPDATE_MEMORY,
        recent_state_path="templates/user/daily_data/recent_status.md",
        user_md_path="templates/user/user.md",
        diary_path_template="templates/user/diary/{year}/{month}/{year}-{month}-{day}.md",
    )
    print(f"  ✓ 获取 prompt: {len(memory_prompt)} 字符")
    # 这里会调用 LLM API，传入 memory_prompt

    # 场景 3: 聊天功能 - 提取聊天内容
    print("\n场景 3: 提取聊天内容")
    extract_prompt = loader.load_prompt(Prompts.Schedule.EXTRACT_CHAT)
    print(f"  ✓ 获取 prompt: {len(extract_prompt)} 字符")
    # 这里会调用 LLM API，传入 extract_prompt 和聊天记录


def example_custom_prompt_ref():
    """自定义 PromptRef 示例"""
    print("\n" + "=" * 60)
    print("示例 6: 自定义 PromptRef（高级用法）")
    print("=" * 60)

    prompts_dir = Path("templates/prompts")
    loader = PromptLoader(prompts_dir)

    # 如果需要动态构造 PromptRef（不推荐，但支持）
    custom_ref = PromptRef("schedule", "activity_summary")
    prompt = loader.load_prompt(custom_ref)
    print(f"✓ 使用自定义 PromptRef: {len(prompt)} 字符")

    # 推荐使用预定义的 Prompts 类常量
    prompt_recommended = loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)
    print(f"✓ 推荐使用 Prompts 类: {len(prompt_recommended)} 字符")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Prompt 管理系统使用示例")
    print("=" * 60)

    # 运行所有示例
    example_basic_usage()
    example_with_parameters()
    example_version_management()
    example_usage_stats()
    example_real_world_usage()
    example_custom_prompt_ref()

    print("\n" + "=" * 60)
    print("所有示例运行完成")
    print("=" * 60)

    print("\n💡 提示:")
    print("  - 推荐使用 Prompts 类而不是字符串")
    print("  - IDE 会提供自动补全和类型检查")
    print("  - 重构时 IDE 可以找到所有引用")
    print("  - 代码更简洁，避免拼写错误")
