from lifeprism.config import settings
from lifeprism.llm.utils import read_md,extract_behavior_logs_from_file
from pathlib import Path
print(extract_behavior_logs_from_file("localData/user/daily_data/behavior.md","2026-04-12"))