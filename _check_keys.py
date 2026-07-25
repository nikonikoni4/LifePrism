"""检查云端 storage.yaml 的 sync_api_key"""
import os
import yaml

# 云端 storage.yaml 路径
cloud_storage_path = "explore/LifePrism/localData/config/storage.yaml"
print(f"Cloud storage path: {cloud_storage_path}")
print(f"Exists: {os.path.exists(cloud_storage_path)}")

if os.path.exists(cloud_storage_path):
    with open(cloud_storage_path, "r", encoding="utf-8") as f:
        storage = yaml.safe_load(f) or {}
    print(f"Keys in storage: {list(storage.keys())}")
    sync_key = storage.get("sync_api_key", "NOT_FOUND")
    print(f"Cloud sync_api_key (first 10): {str(sync_key)[:10]}...")
else:
    print("Cloud storage.yaml not found - cloud has not been initialized with a key")

# 本地 keyring key
import keyring
from lifeprism.config.settings_manager import settings
settings._initialize()
# 本地是 full 模式，从 keyring 读
local_key = settings.get_storage_key("sync_api_key")
print(f"\nLocal sync_api_key (first 10): {str(local_key)[:10] if local_key else 'EMPTY'}...")

# 对比
if os.path.exists(cloud_storage_path):
    cloud_key = storage.get("sync_api_key")
    if cloud_key and local_key:
        print(f"\nKeys match: {cloud_key == local_key}")
    else:
        print(f"\nOne or both keys are empty - cloud: {bool(cloud_key)}, local: {bool(local_key)}")
