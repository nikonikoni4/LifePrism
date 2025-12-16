from langgraph.store.memory import InMemoryStore
import uuid
# 创建 store
in_memory_store = InMemoryStore()
# 定义命名空间 (类似文件夹结构)
user_id = "1"
namespace = (user_id, "memories")  # 元组形式
# 存储数据 - put(namespace, key, value)
memory_id = str(uuid.uuid4())
memory = {"food_preference": "I like pizza"}
in_memory_store.put(namespace, memory_id, memory)
# 检索数据 - search(namespace)
memories = in_memory_store.search(namespace)
# 结果是一个 Item 对象列表
for item in memories:
    print(item.dict())
    # {
    #     'value': {'food_preference': 'I like pizza'},
    #     'key': '07e0caf4-1631-...',
    #     'namespace': ['1', 'memories'],
    #     'created_at': '2024-10-02T17:22:31...',
    #     'updated_at': '2024-10-02T17:22:31...'
    # }