# 1. 测试输入准备：地址，输入数据类型
# 2. 测试轮次：同一个数据和版本可以多次测试
# 3. 测试输出准备：输出地址，输出数据类型
# 4. 输出测试人工评估表（文本输出类）：包含5列，llm输入，llm输出，是否通过，评分，原因，其他内容
# metadata 测试变量：1. 测试prompt名称 2. 测试prompt版本 3. 测试prompt轮次 4. 通过率 5. temperature
# 1. 输入文件夹结构： 一个文件夹放置一个prompt输入内容
# 2. 输出文件夹： 该prompt的总地址， 文件结构 prompt/version, prompt/meta_data.json
# 3. meta_data.json:
# [
#             {version,round:  , pass_ratio: , temperature,create_at,input_file}
#     ]
#
# 4. 扔个测试评估表，采用excel格式输出，指定分页卡名称为r{round}-t{temperature}
# 5. 每个轮次的测试可以指定输入文件
#
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from typing_extensions import TypedDict

from lifeprism.llm.prompts import PromptRef, Prompts


class PromptRound(TypedDict):
    version: int  # 测试版本
    round: int  # 测试轮次
    pass_ratio: float  # 测试通过率，百分比
    temperature: float
    create_at: str  # 创建时间
    input_file: list[str]  # 测试输入文件


class TestLog(TypedDict):
    system_prompt: str
    user_message: str
    result: str
    version: str
    temperature: float
    input_data_date: str  # 输入数据日期，格式 "YYYY-MM-DD"


class ConversationManager:
    """
    对话管理类
    保存每轮测试输入的 Message list，输出为 JSONL 文件
    """

    def __init__(self, input_path: Path, version: str, round: int, temperature: float):
        """
        args:
            input_path: 输入路径（版本号之前的路径）
            version: 版本号
            round: 轮次
            temperature: 温度参数
        """
        self.input_path = input_path
        self.version = version
        self.round = round
        self.temperature = temperature
        self.file_path = input_path / version / f"r{round}-t{temperature}.jsonl"
        self.messages: list[list[dict]] = []

        # 如果文件存在，加载历史消息（支持继续对话）
        if self.file_path.exists():
            with self.file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.messages.append(json.loads(line))

    def add_messages(self, messages: list[dict]):
        """添加一轮测试的 message list"""
        self.messages.append(messages)

    def save(self):
        """保存为 JSONL 文件"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("w", encoding="utf-8") as f:
            for msg_list in self.messages:
                f.write(json.dumps(msg_list, ensure_ascii=False) + "\n")

    @staticmethod
    def load(
        input_path: Path, version: str, round: int, temperature: float
    ) -> "ConversationManager":
        """从已有文件加载对话历史"""
        return ConversationManager(input_path, version, round, temperature)


class LLMTestBase(ABC):
    META_DATA_FILE_NAME = "meta_data.json"
    EVAL_SHEET_COLUMNS = ["llm_input", "llm_output", "pass", "score", "reason", "other"]

    def __init__(
        self,
        prompt: PromptRef,
        prompt_version: str,
        input_path: Path,
        output_path: Path = Path("D:/desktop/软件开发/LifeWatch-AI/test/llm_prompt_test.py"),
        temperature=0.7,
    ):
        """
        args :
            prompt : PromptRef 类，使用Prompts引出
            prompt_version : prompt需要测试的版本
            input_path : 数据输入地址
            output_path ： 结果输出地址，是该prompt的总地址，输出时会输出到 output_path/prompt/version中
        """
        self.prompt = prompt
        self.prompt_version = prompt_version
        self.input_path = input_path
        self.output_path = output_path
        self.temperature = temperature
        self.metadata: list[PromptRound] = self.get_metadata()

    def set_prompt_version(self, prompt_version: str):
        """设置 prompt 版本"""
        if prompt_version:
            self.prompt_version = prompt_version

    def set_temperature(self, temperature: float):
        """设置 temperature 参数"""
        if temperature is not None:
            self.temperature = temperature

    def get_metadata(self) -> list[PromptRound]:
        """从output_path 获取metadata，没有则自动创建"""
        path = self.output_path / f"{self.prompt.name}/{self.META_DATA_FILE_NAME}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                data: dict = json.load(f)
                return [PromptRound(**item) for item in data]
        return []

    def get_next_round(self) -> int:
        """获取下一个轮次号"""
        if not self.metadata:
            return 1
        return max(r["round"] for r in self.metadata) + 1

    def save_metadata(self):
        """保存metadata到文件"""
        path = self.output_path / f"{self.prompt.name}/{self.META_DATA_FILE_NAME}"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    @abstractmethod
    def data_input(self, input_files: list[str] = None) -> list[Any]:
        """
        输入数据解析
        args :
            input_files 输入的文件名称列表
        return :
            输出每次llm调用的需要的数据
        """
        pass

    @abstractmethod
    def run_test(self, input_files: list[str] = None) -> list[dict]:
        """
        执行测试
        args :
            input_files 输入的文件名称列表，默认None为全量测试
        return :
            测试结果列表，每个元素包含llm_input和llm_output
        """
        pass

    @abstractmethod
    def generate_eval_sheet(self, test_results: list[dict], round: int, temperature: float) -> Path:
        """
        生成Excel评估表
        args :
            test_/ 测试结果列表
            round 测试轮次
            temperature 温度参数
        return :
            Excel文件路径
        """
        pass

    @abstractmethod
    def read_eval_result(self, eval_sheet_path: Path) -> float:
        """
        读取评估结果，计算通过率
        args :
            eval_sheet_path Excel评估表路径
        return :
            通过率（0-1）
        """
        pass

    @abstractmethod
    def main(self):
        """执行测试主函数"""
        pass

    def update_metadata(self, round: int, pass_ratio: float, input_files: list[str]):
        """
        更新metadata
        args :
            round 测试轮次
            pass_ratio 通过率
            input_files 测试输入文件列表
        """
        new_round: PromptRound = {
            "version": self.prompt_version,
            "round": round,
            "pass_ratio": pass_ratio,
            "temperature": self.temperature,
            "create_at": datetime.now().isoformat(),
            "input_file": input_files,
        }
        self.metadata.append(new_round)
        self.save_metadata()

    def save_log(self, test_logs: list[TestLog], round: int):
        """
        保存测试日志到 JSON 文件
        args:
            test_logs: 测试日志列表
            round: 测试轮次
        """
        log_path = (
            self.output_path
            / self.prompt.name
            / self.prompt_version
            / f"r{round}-t{self.temperature}.json"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as f:
            json.dump(test_logs, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    t = LLMTestBase(
        Prompts.Schedule.CREATE_DIARY_SUMMARY,
        "v1",
        Path("D:/desktop/软件开发/LifeWatch-AI/test/llm_prompt_test.py/dataset"),
        Path("D:/desktop/软件开发/LifeWatch-AI/test/llm_prompt_test.py//"),
    )
    print(t.get_metadata())
