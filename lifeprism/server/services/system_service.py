from typing import List, Dict

from lifeprism.config.settings_manager import settings


def get_warnings() -> List[Dict[str, str]]:
    return settings.warnings
