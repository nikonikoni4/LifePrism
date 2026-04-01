import win32gui
import win32process
import win32api
import win32con
import psutil
from typing import Optional
from lifeprism.utils.logger import get_logger
from .exceptions import MonitorError

logger = get_logger(__name__)

def get_active_window_handle() -> int:
    """
    获取当前前台窗口的句柄 (HWND)。
    """
    return win32gui.GetForegroundWindow()

def get_window_title(hwnd: int) -> str:
    """
    获取指定窗口的标题。
    """
    try:
        return win32gui.GetWindowText(hwnd)
    except Exception as e:
        logger.error(f"获取窗口标题失败 (HWND: {hwnd}): {e}")
        return ""

def get_app_name(hwnd: int) -> str:
    """
    获取窗口所属的应用程序名称。
    优先通过进程 ID 获取，如果失败则尝试其他方式。
    """
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid <= 0:
            return "unknown"

        # 尝试通过 psutil 获取进程名
        process = psutil.Process(pid)
        return process.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # 可能是以管理员权限运行的进程
        return _get_app_name_fallback(hwnd)
    except Exception as e:
        logger.debug(f"获取应用名称失败 (HWND: {hwnd}): {e}")
        return "unknown"

def get_app_path(hwnd: int) -> str:
    """
    获取窗口所属的应用程序可执行文件路径。
    """
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid <= 0:
            return ""

        process = psutil.Process(pid)
        return process.exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return _get_app_path_fallback(hwnd)
    except Exception as e:
        logger.debug(f"获取应用路径失败 (HWND: {hwnd}): {e}")
        return ""

def _get_app_name_fallback(hwnd: int) -> str:
    """
    当 psutil 无法访问进程时（如管理员权限进程），尝试通过 WMI 或其他方式获取名称。
    注意：此处简化处理，aw-watcher-window 中使用了 WMI，但我们先尝试 win32api。
    """
    try:
        # 尝试通过 WMI 获取（如果安装了 wmi 库）
        import wmi
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        c = wmi.WMI()
        for process in c.Win32_Process(ProcessId=pid):
            return process.Name
    except ImportError:
        logger.debug("wmi 库未安装，无法使用 WMI fallback")
    except Exception as e:
        logger.debug(f"WMI fallback 获取应用名称失败: {e}")

    return "unknown"

def _get_app_path_fallback(hwnd: int) -> str:
    """
    管理员权限进程的可执行文件路径 fallback。
    """
    try:
        import wmi
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        c = wmi.WMI()
        for process in c.Win32_Process(ProcessId=pid):
            return process.ExecutablePath
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"WMI fallback 获取应用路径失败: {e}")

    return ""
