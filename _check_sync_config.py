"""检查本地和云端的同步配置"""
import os
import yaml
import keyring as keyring_mod

# 本地 sync.remote_url
from lifeprism.config.settings_manager import settings, get_setting, set_setting
settings._initialize()
print("=" * 60)
print("Local sync config:")
print("=" * 60)
print(f"sync.remote_url: {get_setting('sync.remote_url')}")

# 本地 keyring sync_api_key
try:
    from lifeprism.sync.sync_config import get_sync_api_key
    local_key = get_sync_api_key()
    print(f"Local sync_api_key (first 10 chars): {local_key[:10] if local_key else 'EMPTY'}...")
except Exception as e:
    print(f"Local sync_api_key error: {e}")

# 云端 cloud_init.yaml
print("\n" + "=" * 60)
print("Cloud cloud_init.yaml:")
print("=" * 60)
cloud_config_path = "explore/LifePrism/localData/config/cloud_init.yaml"
if os.path.exists(cloud_config_path):
    with open(cloud_config_path, "r", encoding="utf-8") as f:
        cloud_config = yaml.safe_load(f)
    print(f"sync_api_key (first 10 chars): {str(cloud_config.get('sync_api_key', ''))[:10]}...")
    print(f"db_path: {cloud_config.get('db_path', 'N/A')}")
else:
    print(f"cloud_init.yaml not found at {cloud_config_path}")

# 确保 sync.remote_url 指向云端
if get_setting("sync.remote_url") != "http://localhost:8102":
    print("\n>>> Setting sync.remote_url to http://localhost:8102")
    set_setting("sync.remote_url", "http://localhost:8102")
