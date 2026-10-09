"""手动索引与每日任务、业务同步共享本地任务互斥。"""

import asyncio

from lifeprism.rag.service import RagService
from lifeprism.server.services.global_task_state import TaskState, global_task_state
from lifeprism.utils.exceptions import ConflictError


async def start_manual_index(service: RagService) -> None:
    """取得全局任务互斥，移交后台构建，完成或失败后释放。"""
    acquired = await asyncio.to_thread(global_task_state.try_acquire, TaskState.LOCAL_TASK, 0.0)
    if not acquired:
        raise ConflictError("同步或本地任务正在执行，请稍后更新索引")
    transferred = False
    try:
        task = service.start_manual_build()
        task.add_done_callback(lambda _: global_task_state.release())
        transferred = True
    finally:
        if not transferred:
            global_task_state.release()
