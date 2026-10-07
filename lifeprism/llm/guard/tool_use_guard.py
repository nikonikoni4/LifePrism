"""工具调用护栏：tool/call 事件上按路径白名单逐条裁决。

本文件自 ``myagent.agent.guard.tool_use_guard`` 复制而来，检测逻辑与原实现
一致。lifeprism 注册并使用本文件里的 ``ToolUseGuard``，不再引用 myagent 的
那份。两份实现当前并存、可能各自漂移，见
``docs/technical-debt/2026-10-08-guard-duplicated-lifeprism-myagent.md``。

与原文的三处差异，均为适配新归属地：文件头补本模块 docstring；日志改用
``lifeprism.utils.get_logger``（与 lifeprism 其余模块一致）；两处函数签名按
lifeprism 的 ruff format 规范重排（原文为 ``x : dict`` 这类带空格写法）。

payload 类型（``ToolCallInfo`` / ``ToolCallPayload``）仍从 myagent 导入：事件
广播的就是那两个类的实例，类型必须同源。
"""

import json
from pathlib import Path

from myagent.infra.events.payload import ToolCallInfo, ToolCallPayload

from lifeprism.utils import get_logger

logger = get_logger(__name__)


class ToolUseGuard:
    """
    工具护栏组件，默认加载启用
    定于tool/use事件在工具调用之前对工具进行权限/路径检测
    采用注册制，yaml控制开启/关闭检测内容，检测参数

    裁决（waterfall）约定——本事件链上所有订阅方共用同一套形状：
    裁决值是**反对意见表** {call_id: {"decision": "deny", "reason": str}}，
    只装自己反对的 call，缺席 = 不反对（检查通过、或这条不归我管，对调用方都是
    不拦）。调用方拿到后逐条查 `call.id in vetoes` 决定拒绝还是执行。

    payload 是整批、裁决是逐条，两者不冲突：路径这类判据只依赖单条 call 自己，
    逐条判即可；要整批视野才能判的订阅方（这批里有几个写操作）也从同一个 payload
    取数。故本订阅方不认领整批——即使本批有反对意见也照常 await _next()，把下游
    的反对并进来（见 file_sys_path_guard）。
    """

    # 受管工具 -> 其路径参数名。注意这里是耦合了 lifeprism 的工具调用，但是目前仍
    # 写在这里面；正常应该这里是直接 import 工具然后获取工具的名称而不是硬编码。
    # 新增带路径的工具时，在这里补一行即可（只此一处）。
    _PATH_PARAM_BY_TOOL = {
        "read_file": "file_path",
        "write_file": "file_path",
        "edit_file": "file_path",
        # 以下三个同样能按路径读到文件内容，不护住等于给白名单留了个绕过的口子
        "file_tree_py": "dir_path",
        "search_file_py": "search_dir",
        "search_string_py": "path",
    }

    def __init__(self, tool_user_config: dict):
        self.config = tool_user_config  # 包含 allow_path : list[str]
        # 白名单条目在构造时一次归一化：相对条目按进程 CWD 解析——与工具自己
        # 拿到相对 file_path 时的落点规则一致（工具是 Path(file_path) 交给 open），
        # 两边规则必须相同，否则护栏看的是 A 路径、工具写的是 B 路径
        self.allow_path = [Path(p).resolve() for p in self.config.get("allow_path") or []]

    async def file_sys_path_guard(self, payload: ToolCallPayload, _next: callable) -> dict:
        """tool/call 的 waterfall 订阅方：对文件系统类工具逐条做路径白名单检测。

        返回反对意见表（只装被拒的 call）；本批没有反对意见时返回空表 {}。**只要本
        订阅方跑过就一定返回 dict**，故调用方见到 None 只可能是"链上没人认领"，不会
        与"护栏看过了、没意见"混淆。

        为什么有反对也不截断链：截断的话，下游订阅方对其他 call 的意见会连带丢失
        ——护栏反对 call A 不代表 B 就该免检。故照常 await _next()，把下游的反对
        并进来。合并是并集（链上各订阅方都只产出 deny，不存在"allow 盖掉 deny"的
        问题）；同一条 call 被两层都反对时保留更外层（先注册者）的理由。

        不修改输入：只读 payload，不就地写回 call.arguments——那个 dict 是 provider
        的输出，后面的 session 记录与回喂模型都还要用。

        前缀匹配用的是路径段级判断（Path.is_relative_to），不是子串包含：
        子串包含下白名单 ["user"] 会放行 /etc/superuser/x 这类路径，等于形同虚设。
        匹配对象是 resolve() 后的绝对路径，顺带把 ../ 穿越与软链接指向外部的情况
        一并算清楚——护栏看到的就是工具实际会落到的地方。Windows 下纯路径比较
        大小写不敏感，无需额外处理。

        必须是 async：waterfall 订阅契约要求订阅方可被 await。契约见
        docs/coding-rules/2026-09-18-waterfall订阅契约.md（该文档在 myagent 仓库）。

        args:
            payload : ToolCallPayload，携带本批全部工具调用（list[ToolCallInfo]）
            _next   : 链上下一个订阅方；本订阅方放行时调用

        Returns:
            {call_id: {"decision": "deny", "reason": str}}，可能为空表。
        """
        vetoes: dict[str, dict] = {}
        for call in payload.tool_call_requests:
            reason = self._deny_reason(call)
            if reason is None:
                continue
            vetoes[call.id] = {"decision": "deny", "reason": reason}
            logger.warning("路径护栏拒绝工具调用 %s(%s): %s", call.name, call.id, reason)

        if vetoes:
            return vetoes
        downstream = await _next()
        # 下游不是本约定形状：None 即链尾再无人认领，此时返回到此为止的反对意见
        # （空表也是有效裁决——"护栏看过了，没意见"）
        if not isinstance(downstream, dict):
            return vetoes
        for call_id, verdict in downstream.items():
            vetoes.setdefault(call_id, verdict)
        return vetoes

    def _deny_reason(self, call: ToolCallInfo) -> str | None:
        """单条 call 的判定：返回拒绝理由；不反对 / 不归本护栏管的返回 None。"""
        param_name = self._PATH_PARAM_BY_TOOL.get(call.name)
        if param_name is None:
            return None
        # 归一化成 dict：dict 直通，str 再解析一次（见 _parse_arguments）。护栏不能
        # 因为上游没解析出结构就跳过检——那样"护栏只认 dict"本身就成了绕过口子。
        arguments = self._parse_arguments(call.arguments)
        # 连解析都拿不到对象：这个调用本来就走不通执行路径，跳过它不产生"绕过护栏
        # 执行危险动作"的口子（见 ADR: 2026-09-10-工具调用解析与截断处置移入工具层）
        if arguments is None:
            return None
        raw_path = arguments.get(param_name)
        # 路径缺失/非字符串：不归护栏管，交工具层的参数校验去报错
        if not isinstance(raw_path, str) or not raw_path:
            return None
        if self._is_allowed(raw_path):
            return None

        if not self.allow_path:
            # fail-closed：没配白名单不等于不限制，否则配置漏了会静默放行一切
            return f"未配置 allow_path 白名单，已拒绝 {call.name} 对路径 {raw_path} 的访问"
        return (
            f"路径 {raw_path} 不在允许访问的范围内，已拒绝 {call.name} 的调用；"
            f"可访问范围：{', '.join(str(p) for p in self.allow_path)}"
        )

    @staticmethod
    def _parse_arguments(arguments: str | dict) -> dict | None:
        """把 call.arguments 归一成 dict；拿不到对象返回 None。

        dict 直通（provider 已解析成功）。str 在此再试一次 json.loads：provider
        尽力解析失败时留的是 wire 原文，但"provider 没解析出来"不等于"这条调用
        没有结构化参数"——session 回放等其他构造路径同样可能给出合法 JSON 字符串。
        护栏是安全判据，判据所需的数据得自己拿得准，不能因为上游形态不同而静默免检。

        解析不出对象（非法 JSON，或结果是数组/数字/null）返回 None，由调用方按
        "跳过"处理——这类调用在工具层也会解析失败、拿不到可执行参数。

        不修改输入：返回的是新对象或原对象本身，绝不写回 call.arguments。
        """
        if isinstance(arguments, dict):
            return arguments
        if not isinstance(arguments, str):
            return None
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _is_allowed(self, path: str) -> bool:
        """判断路径是否落在白名单内（任一条目为其祖先或本身即算命中）。"""
        if not self.allow_path:
            return False
        target = Path(path).resolve()
        return any(target.is_relative_to(root) for root in self.allow_path)
