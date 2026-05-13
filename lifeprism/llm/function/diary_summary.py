"""
日记总结脚本
自动触发：
1. 第二天自动总结前一天的日记
2. 日记更新之后的新ai summary
手动触发：
3. 手动更新：可以选择日记进行手动更新

其他地方需要配合的地方：
1. 前端需要增加AI日记总结显示的地方
2. 前端需要增加手动更新按钮
"""

from lifeprism.llm.bus import OutboundMessage, bus, MessageType, InboundMessage
from lifeprism.llm.providers import LLMResponse
from lifeprism.config import settings
from pathlib import Path
from lifeprism.llm.utils.md_os import read_md,write_date_md,extract_date_logs_from_file
from lifeprism.repository import diary_repository
from lifeprism.llm.prompts import PromptLoader, Prompts

# 创建 PromptLoader 实例
prompt_loader = PromptLoader(settings.lifeprism_data_path / "prompts")


async def ai_diary_summary(date:str, mood:str, importence : str ,custom_label:list[str], outdate_summary: str | None = None)->LLMResponse:
    """
    对某一天的日记进行总结
    args:
        date : 日记日期
        outdate_summary: 过时的日记总结（外部传入）
        mood : 写日记时的心情
        importence : 写日记时认为当前的内容是否重要
        custom_label : 写日记时的自定义标签
    """
    behavior_md_path = settings.lifeprism_data_path / "user" / "daily_data" / "behavior.md"
    behavior_md_path.parent.mkdir(parents=True, exist_ok=True)


    year = date.split("-")[0]
    month = date.split("-")[1]
    diary_context = read_md(settings.lifeprism_data_path / "diary" / year / month / f"{date}.md")
    # 一个人情绪或状态应该都是有一定连续性的，所以一定要把这个连续性给捕捉到，然后这个连续性破坏一定会有关键事件，这个关键事件一定要重点分析，这样就能绘制一个心里折线图了
    sys_parts = []
    # 任务提示词
    if outdate_summary:
        task_prompt = prompt_loader.load_prompt(Prompts.Schedule.UPDATE_DIARY_SUMMARY)
    else:
        task_prompt = prompt_loader.load_prompt(Prompts.Schedule.CREATE_DIARY_SUMMARY)
    sys_parts.append(task_prompt)

    # 用户画像（长期内容）
    user_md_path = settings.lifeprism_data_path / "user" / "user.md"
    user_md = read_md(user_md_path)
    if user_md:
        sys_parts.append(
            f"""
            ## 用户信息
            <user_message>
            {user_md}
            </user_message>
            """
            )
    system_prompt = "\n".join(sys_parts)

    user_parts = []
    # 用户近况
    recent_status_md_path = settings.lifeprism_data_path / "user" / "daily_data" / "recent_status.md"
    recent_status_md = read_md(recent_status_md_path)
    if recent_status_md:
        user_parts.append(
            f"""
            
            ## 用户近况（仅供参考，不作为总结对象主体）
            <recent_status>
            {recent_status_md}
            </recent_status>
            """
        )

    if outdate_summary:
        user_parts.append(
            f"""
            ## 旧日记总结内容
            <outdate_summary>
            {outdate_summary}
            </outdate_summary>
            """
        )

    diary= f"""
    ## 日记内容：需要总结的部分
    <diary>
    ## {date}
    {diary_context}
    </diary>
    """



    user_parts.append(diary)
    label_to_save = None
    if mood or importence or custom_label:
        
        label = "\n\n## 标签"
        label_to_save = "用户输入标签："
        if mood:
            label += f"\n用户输入心情（包括 非常愉悦，有点开心，平静，不太好，非常不好）：{mood}"
            label_to_save += f" 心情：{mood}"
        if importence:
            label += f"\n用户认为该日记的重要程度（包括重要，一般，平凡）：{importence}"
            label_to_save += f" 重要程度: {importence}"
        if custom_label:
            label += f"\n用户自定义标签：{custom_label}"
            label_to_save += f" 用户自定义标签: {custom_label}"
        user_parts.append(label)

    content = "\n".join(user_parts)
    msg = InboundMessage(
        content=content,
        type=MessageType.GENERAL_TASK,
        extra={'system_prompt':system_prompt}
    )
    result :OutboundMessage = await bus.send(msg) 
    result = result.response.content

    if result : 
        # 将ai summary写入lifeprismData\user\daily_data\behavior.md
        if label_to_save:
            result = f"{label_to_save}\n" + result
        write_date_md(behavior_md_path, date, result, subheading="日记总结", mode='overwrite' if outdate_summary else 'append')
        return result
        
    return None


if __name__ == "__main__":
    data = "2026-04-12"
    diary_context = None
    mood = "不太好"
    from lifeprism.llm.agent.loop import agent_loop
    import asyncio
    
    async def main():
        loop_task = asyncio.create_task(agent_loop.loop())
        # logger.info("[STARTUP] AgentLoop started") # logger is not imported in this file
        response = await ai_diary_summary(data, mood, None, None)
        print(response)
        loop_task.cancel() # Cancel the loop task when done to exit cleanly
        
    asyncio.run(main())