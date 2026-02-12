from typing import List

from lifeprism.config.settings_manager import settings


def get_warnings() -> List[str]:
    return settings.warnings
