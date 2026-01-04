"""
LifeWatch-AI 自动更新检查器
基于 GitHub Releases 实现版本检查和更新下载
"""

import os
import json
import requests
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from packaging import version
import logging

logger = logging.getLogger(__name__)


class UpdateChecker:
    """软件更新检查器"""
    
    def __init__(
        self,
        current_version: str,
        github_repo: str = "your-username/LifeWatch-AI",
        update_check_interval: int = 86400  # 24小时
    ):
        """
        初始化更新检查器
        
        Args:
            current_version: 当前软件版本，如 "1.0.0"
            github_repo: GitHub 仓库，格式 "owner/repo"
            update_check_interval: 检查更新间隔（秒）
        """
        self.current_version = current_version
        self.github_repo = github_repo
        self.update_check_interval = update_check_interval
        self.api_url = f"https://api.github.com/repos/{github_repo}/releases/latest"
        
    def check_for_updates(self) -> Optional[Dict[str, Any]]:
        """
        检查是否有新版本
        
        Returns:
            如果有更新，返回更新信息字典：
            {
                "version": "1.0.1",
                "download_url": "https://...",
                "release_notes": "更新内容...",
                "published_at": "2026-01-04T10:00:00Z"
            }
            如果没有更新或检查失败，返回 None
        """
        try:
            # 发送请求到 GitHub API
            response = requests.get(
                self.api_url,
                timeout=10,
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            response.raise_for_status()
            
            release_data = response.json()
            
            # 解析版本号
            latest_version = release_data["tag_name"].lstrip("v")
            
            # 比较版本
            if version.parse(latest_version) > version.parse(self.current_version):
                # 查找 Windows 安装包
                download_url = None
                for asset in release_data.get("assets", []):
                    if asset["name"].endswith(".exe"):
                        download_url = asset["browser_download_url"]
                        break
                
                if not download_url:
                    logger.warning("未找到 Windows 安装包")
                    return None
                
                return {
                    "version": latest_version,
                    "download_url": download_url,
                    "release_notes": release_data.get("body", ""),
                    "published_at": release_data.get("published_at", ""),
                    "size": asset.get("size", 0)
                }
            
            logger.info(f"当前已是最新版本: {self.current_version}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"检查更新失败: {e}")
            return None
        except Exception as e:
            logger.error(f"解析更新信息失败: {e}")
            return None
    
    def download_update(
        self,
        download_url: str,
        progress_callback: Optional[callable] = None
    ) -> Optional[Path]:
        """
        下载更新安装包
        
        Args:
            download_url: 下载链接
            progress_callback: 进度回调函数 callback(downloaded, total)
        
        Returns:
            下载的文件路径，失败返回 None
        """
        try:
            # 创建临时文件
            temp_dir = Path(tempfile.gettempdir()) / "LifeWatch-AI-Updates"
            temp_dir.mkdir(exist_ok=True)
            
            filename = download_url.split("/")[-1]
            filepath = temp_dir / filename
            
            # 下载文件
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 调用进度回调
                        if progress_callback:
                            progress_callback(downloaded_size, total_size)
            
            logger.info(f"更新包下载完成: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"下载更新失败: {e}")
            return None
    
    def install_update(self, installer_path: Path, silent: bool = False) -> bool:
        """
        安装更新
        
        Args:
            installer_path: 安装包路径
            silent: 是否静默安装
        
        Returns:
            是否成功启动安装程序
        """
        try:
            if not installer_path.exists():
                logger.error(f"安装包不存在: {installer_path}")
                return False
            
            # 构建安装命令
            if silent:
                # 静默安装（Inno Setup 支持 /SILENT 参数）
                cmd = [str(installer_path), "/SILENT", "/CLOSEAPPLICATIONS"]
            else:
                # 交互式安装
                cmd = [str(installer_path)]
            
            # 启动安装程序
            subprocess.Popen(cmd)
            
            logger.info("已启动安装程序")
            return True
            
        except Exception as e:
            logger.error(f"启动安装程序失败: {e}")
            return False


class UpdateManager:
    """更新管理器（带缓存和配置）"""
    
    def __init__(self, config_dir: Path, current_version: str):
        self.config_dir = config_dir
        self.config_file = config_dir / "update_config.json"
        self.current_version = current_version
        self.checker = UpdateChecker(current_version)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载更新配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载更新配置失败: {e}")
        
        # 默认配置
        return {
            "auto_check": True,
            "auto_download": False,
            "auto_install": False,
            "last_check_time": 0,
            "skipped_version": None
        }
    
    def _save_config(self):
        """保存更新配置"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存更新配置失败: {e}")
    
    def should_check_update(self) -> bool:
        """判断是否应该检查更新"""
        if not self.config.get("auto_check", True):
            return False
        
        import time
        last_check = self.config.get("last_check_time", 0)
        interval = self.checker.update_check_interval
        
        return (time.time() - last_check) > interval
    
    def check_and_notify(self) -> Optional[Dict[str, Any]]:
        """检查更新并返回结果（用于 UI 通知）"""
        if not self.should_check_update():
            return None
        
        update_info = self.checker.check_for_updates()
        
        # 更新检查时间
        import time
        self.config["last_check_time"] = time.time()
        self._save_config()
        
        # 检查是否跳过此版本
        if update_info:
            skipped = self.config.get("skipped_version")
            if skipped == update_info["version"]:
                logger.info(f"用户已跳过版本: {skipped}")
                return None
        
        return update_info
    
    def skip_version(self, version: str):
        """跳过指定版本"""
        self.config["skipped_version"] = version
        self._save_config()
    
    def set_auto_update(self, auto_check: bool, auto_download: bool, auto_install: bool):
        """设置自动更新选项"""
        self.config["auto_check"] = auto_check
        self.config["auto_download"] = auto_download
        self.config["auto_install"] = auto_install
        self._save_config()


# 使用示例
if __name__ == "__main__":
    # 初始化更新检查器
    checker = UpdateChecker(current_version="1.0.0")
    
    # 检查更新
    update_info = checker.check_for_updates()
    
    if update_info:
        print(f"发现新版本: {update_info['version']}")
        print(f"更新内容:\n{update_info['release_notes']}")
        
        # 下载更新
        def progress(downloaded, total):
            percent = (downloaded / total) * 100 if total > 0 else 0
            print(f"\r下载进度: {percent:.1f}%", end="")
        
        installer_path = checker.download_update(
            update_info['download_url'],
            progress_callback=progress
        )
        
        if installer_path:
            print(f"\n下载完成: {installer_path}")
            
            # 安装更新
            user_input = input("是否立即安装？(y/n): ")
            if user_input.lower() == 'y':
                checker.install_update(installer_path, silent=False)
    else:
        print("当前已是最新版本")
