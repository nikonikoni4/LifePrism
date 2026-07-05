"""
管理会话
"""
from dataclasses import dataclass,field
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import uuid
from lifeprism.config import settings
from lifeprism.utils import get_logger,NotFoundError
from lifeprism.utils.lazy_singleton import LazySingleton
import os 
logger = get_logger(__name__)
allow_role = ['user','assistant','tool','system']

@dataclass
class Session:
    id : str = field(default_factory=lambda: str(uuid.uuid4()))
    name : str = field(default_factory=lambda: f"session_{datetime.now().strftime('%Y%m%d%H%M')}")
    messages : list[dict[str,Any]] = field(default_factory=list)
    created_at : datetime = field(default_factory=datetime.now)
    updated_at : datetime = field(default_factory=datetime.now)
    # metadata : dict = field(default_factory=dict) # 扩展位，预留，暂时无任何作用
    last_compacted_loc : int = 0 # 上一次compact的位置 
    auto_compact : bool = True # 默认不自动进行压缩 这个是因为lifeprism 里目前没有长对话，
    last_processed_loc : int = 0 # 上次整理session信息的位置，区别与last_compacted_loc, last_compacted_loc仅仅作为对话压缩不涉及记忆提取

    # def retract_last_user_message(self) -> dict[str, Any]:
    #     """撤销最后一条 user 消息及其之后的所有消息，返回被撤销的 user 消息"""
    #     last_user_index = None
    #     for i in range(len(self.messages) - 1, -1, -1):
    #         if self.messages[i]['role'] == 'user':
    #             last_user_index = i
    #             break
    #     if last_user_index is None:
    #         raise ValueError("没有可撤销的 user 消息")
    #     retracted = self.messages[last_user_index]
    #     self.messages = self.messages[:last_user_index]
    #     self.updated_at = datetime.now()
    #     return retracted

    def add_message(self,role:str,content:str | list | None,**kw:Any) -> None:
        if role not in allow_role:
            raise ValueError(f"message role can't be {role}")
        self.messages.append({
            'role': role,
            'content':content,
            'timestamp':datetime.now().isoformat(),
            **kw
        })
        self.updated_at = datetime.now()
        
    def get_history_message(self) ->list[dict[str,Any]]:
        """加载未压缩的message"""
        load_loc = self.last_compacted_loc if self.auto_compact else 0 
        return self.messages[load_loc:]


class SessionManager:
    """
    维护session的生命周期: 创建，加载，保存，删除
    """
    ALLOW_SAVE_MESSAGE_TYPE = ['user','assistant','tool']
    def __init__(self):
        self._cache : dict[str,Session] = {} # 存放已经加载过的内容 {id : session}

    @staticmethod
    def get_session_path_by_id(session_id)->Path:
        return  settings.session_path / f"{session_id}.jsonl" 

    def _load_session(self,session_id:str) -> Session :
        path = self.get_session_path_by_id(session_id)
        messages = []
        id = session_id
        name = None
        last_compacted_loc = None
        last_processed_loc = None
        # metadata = None
        created_at = None
        updated_at = None
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line  = line.strip()
                    if not line :
                        continue
                    data:dict = json.loads(line)
                    if data.get("_type") == "metadata":
                        # metadata:dict = data.get("metadata",{})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                        updated_at = datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
                        last_compacted_loc = data.get('last_compacted_loc')
                        last_processed_loc = data.get('last_processed_loc')
                        name = data.get('name')
                    else:
                        messages.append(data)
            return Session(
                id = id,
                name = name if name else 'default_name',
                last_compacted_loc = last_compacted_loc if last_compacted_loc else 0,
                last_processed_loc = last_processed_loc if last_processed_loc else 0,
                # metadata=metadata,
                messages = messages,
                created_at = created_at,
                updated_at = updated_at
            )
        else:
            logger.warning(f'在{path}中，找不到{session_id}.jsonl文件')
            raise NotFoundError(f'在{path}中，找不到{session_id}.jsonl文件') # 需要在上层捕获这个错误
            

    def get_or_create_session(self,session_id :str | None = None) -> Session:
        """
            加载或创建一个新的session
            args:
                session_id : str | None 当没有传入session_id时自动创建一个新的session
            return:
                Session
        """

        if session_id and session_id in self._cache: 
            # 已经缓存，直接返回
            return self._cache[session_id]
        elif session_id:
            # 未缓存，尝试加载
            session = self._load_session(session_id)
        else:
            # 不存在，创建新的Session
            session = Session()
        # 缓存Session
        self._cache[session.id] = session
        return session
                

    def delete_session(self,session_id:str) :
        path = self.get_session_path_by_id(session_id)
        if path.exists():
            
            os.remove(path) # 暂时不写错误处理
            if session_id in self._cache:
                del self._cache[session_id]

    @staticmethod
    def _remove_image_content(msg: dict[str, Any]) -> dict[str, Any]:
        """
        移除 user 消息中的图片 base64 内容

        Args:
            msg: 消息字典

        Returns:
            处理后的消息字典（深拷贝）
        """
        if msg.get('role') != 'user':
            return msg

        content = msg.get('content')
        if not isinstance(content, list):
            return msg

        # 深拷贝消息，避免修改原始数据
        import copy
        msg_copy = copy.deepcopy(msg)

        # 过滤掉图片类型的 content block
        filtered_content = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get('type', '')
                # 跳过图片类型的 block
                if block_type not in ('image', 'image_url'):
                    filtered_content.append(block)
            else:
                filtered_content.append(block)

        msg_copy['content'] = filtered_content
        return msg_copy

    def save_session(self,session:Session):
        if session:
            path = self.get_session_path_by_id(session.id)
            settings.session_path.mkdir(parents=True, exist_ok=True)
            with open(path,'w', encoding='utf-8') as f:
                metadata_line = {
                    "_type":"metadata",
                    "name" : session.name,
                    "created_at" : session.created_at.isoformat(),
                    "updated_at" : session.updated_at.isoformat(),
                    "last_compacted_loc" : session.last_compacted_loc,
                    "last_processed_loc" : session.last_processed_loc,
                    "message_len":len(session.messages)
                }
                f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
                for msg in session.messages:
                    if msg.get('role','') in self.ALLOW_SAVE_MESSAGE_TYPE:
                        # 移除 user 消息中的图片内容
                        processed_msg = self._remove_image_content(msg)
                        f.write(json.dumps(processed_msg, ensure_ascii=False) + "\n")
    @staticmethod
    def get_session_metadata(session_id: str) -> dict | None:
        """
        只读取 session 的 metadata，不加载完整 messages

        Args:
            session_id: session ID

        Returns:
            metadata 字典，如果文件不存在或格式错误则返回 None
        """
        path = SessionManager.get_session_path_by_id(session_id)
        if not path.exists():
            logger.warning(f"Session 文件不存在: {path}")
            return None

        try:
            with open(path, encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    data = json.loads(first_line)
                    if data.get("_type") == "metadata":
                        return data
            logger.warning(f"Session {session_id} 的 metadata 格式错误")
            return None
        except Exception as e:
            logger.error(f"读取 session {session_id} metadata 失败: {e}")
            return None

    def remove_from_cache(self, session_id: str) -> bool:
        """
        从缓存中移除指定的 session

        Args:
            session_id: 要移除的 session ID

        Returns:
            bool: 如果成功移除返回 True，如果 session 不在缓存中返回 False
        """
        if session_id in self._cache:
            del self._cache[session_id]
            logger.debug(f"已从缓存中移除 session: {session_id}")
            return True
        else:
            logger.debug(f"Session {session_id} 不在缓存中")
            return False

    @staticmethod
    def show_session_list(path:Path= settings.session_path)-> list[str]:
        """搜索存储地址内的jsonl, 返回session_id list（不带.jsonl后缀）"""
        if not path.exists():
            return []
        return [f.stem for f in path.glob('*.jsonl')]

    @staticmethod
    def show_session_content_list(date_filter: str | None = None, path: Path = settings.session_path) -> list[dict]:
        """
        返回 session 列表及其最新 user 消息预览

        Args:
            date_filter: 日期筛选，格式 'YYYY-MM-DD'，为 None 时返回所有
            path: session 存储路径

        Returns:
            list[dict]: [{"session_id": str, "session_current_msg": str}, ...]
        """
        if not path.exists():
            return []

        result = []
        for file in path.glob('*.jsonl'):
            session_id = file.stem
            last_user_msg = None
            updated_at = None

            try:
                with open(file, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get('_type') == 'metadata':
                            updated_at = data.get('updated_at', '')
                        elif data.get('role') == 'user':
                            last_user_msg = data.get('content', '')
            except Exception as e:
                logger.warning(f"读取 session {session_id} 失败: {e}")
                continue

            # 日期筛选
            if date_filter and updated_at:
                if not updated_at.startswith(date_filter):
                    continue

            # 提取前20个字符
            msg_preview = ''
            if last_user_msg:
                if isinstance(last_user_msg, str):
                    msg_preview = last_user_msg[:20]
                elif isinstance(last_user_msg, list):
                    msg_preview = str(last_user_msg)[:20]

            result.append({
                'session_id': session_id,
                'session_current_msg': msg_preview
            })

        return result

session_manager:SessionManager  = LazySingleton(SessionManager)


class ChatHistoryManager:
    """管理chat_history.json, 不作为单例，每次直接创建"""
    MAX_ITEMS = 1000
    def __init__(self,path:Path|None = None):
        if path:
            self.path = path
        else:
            self.path = settings.lifeprism_data_path / "user/daily_data/chat_history.json"
        self.path.parent.parent.mkdir(parents=True, exist_ok=True)
        self.histories :list[dict]= [] # timestamp,content,is_processed
        self.last_processed_time = datetime.now()
        self.load_histories()

    def load_histories(self)->list[dict]:
        """加载jsonl文件和meta_date

        兼容两种格式：
        - JSONL 格式（正确）：每行一个 JSON 对象
        - 旧格式（bug）：第二行为整个 JSON 数组 [{...}, {...}]
        """
        if self.path.exists():
            with self.path.open('r',encoding='utf-8') as f:
                for line in f:
                    line  = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    # 兼容旧格式：如果解析出来是 list，展开添加每个元素
                    if isinstance(data, list):
                        for entry in data:
                            if isinstance(entry, dict):
                                self.histories.append(entry)
                        continue
                    if data.get("_type",None):
                        self.last_processed_time = datetime.fromisoformat(data.get("last_processed_time",None)) if data.get("last_processed_time",None) else datetime.now()
                    else:
                        self.histories.append(data)
        if self.histories:
            # 只保存前1000条数据
            self.histories = self.histories[-self.MAX_ITEMS:]
        return self.histories
    
    def get_histories_to_dream(self)->list[dict]|None:
        """获取所有未被处理的聊天历史总结"""
        result = []
        for history in self.histories:
            if history.get("timestamp",None):
                if datetime.fromisoformat(history["timestamp"]) > self.last_processed_time:
                    result.append(history)
        return result
    def add_content(self, content: str, session_id: str | None = None) -> None:
        """添加聊天历史记录

        Args:
            content: 总结内容
            session_id: 会话 ID，为 None 时不关联会话

        Returns:
            None
        """
        if not content:
            logger.warning("chat_history.json添加失败，content为None")
            return
        self.path.parent.parent.mkdir(parents=True, exist_ok=True)

        # 构建历史记录项
        history_item = {
            "timestamp": datetime.now().isoformat(),
            "content": content
        }

        # 只有当 session_id 不为 None 时才添加该字段
        if session_id is not None:
            history_item["session_id"] = session_id
            logger.info(f"添加聊天历史: session_id={session_id}")
        else:
            logger.info("添加聊天历史: 未关联session")

        self.histories.append(history_item)
        

    def save_history(self,last_processed_time:datetime|None = None):
        """
        在添加完内容或处理完history之后需要调用这个函数
        args:
            last_processed_time 在process history message之后需要添加时间
            只添加history line 不需要添加last_processed_time参数
        """
        if last_processed_time:
            self.last_processed_time = last_processed_time
        with self.path.open("w",encoding="utf-8") as f:
            metadata_line = {
                    "_type":"metadata",
                    "last_processed_time":self.last_processed_time.isoformat()
                }
            f.write(json.dumps(metadata_line, ensure_ascii=False)+"\n")
            if self.histories:
                for entry in self.histories:
                    f.write(json.dumps(entry, ensure_ascii=False)+"\n")

    


if __name__ == "__main__":
    manager = SessionManager()

    # 1. 创建新 session
    session = manager.get_or_create_session()
    print(f"[创建] id={session.id}, name={session.name}")
    assert isinstance(session.id, str)

    # 2. 添加消息
    session.add_message(role='user', content='你好')
    session.add_message(role='assistant', content='你好，我是你的专属助手')
    assert len(session.messages) == 2
    assert session.messages[0]['role'] == 'user'
    print(f"[消息] 共 {len(session.messages)} 条")

    # 3. 保存 session
    manager.save_session(session)
    print("[保存] 已写入文件")

    # 4. 重新加载，验证内容一致
    manager._cache.clear()
    loaded = manager.get_or_create_session(session.id)
    assert loaded.id == session.id
    assert loaded.name == session.name
    assert len(loaded.messages) == 2
    assert loaded.messages[1]['content'] == '你好，我是你的专属助手'
    print(f"[加载] id={loaded.id}, 消息数={len(loaded.messages)}")

    # 5. show_session_list
    session_list = manager.show_session_list()
    assert any(session.id in s for s in session_list)
    print(f"[列表] {session_list}")

    # 6. 删除 session
    manager.delete_session(session.id)
    assert not manager.get_session_path_by_id(session.id).exists()
    print("[删除] 文件已删除")

    print("\n全部测试通过")

    print(session_manager.show_session_content_list("2026-04-28"))