from lifeprism.config.settings_manager import settings


def get_warnings() -> list[dict[str, str]]:
    return settings.warnings
