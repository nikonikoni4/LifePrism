#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ActivityWatch 数据库直接读取器
直接从 ActivityWatch SQLite 数据库读取数据,替代 API 方式,提升性能
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
import pytz

from lifewatch.config import WINDOW_BUCKET_ID, LOCAL_TIMEZONE

logger = logging.getLogger(__name__)
from lifewatch.storage import AWBaseDataProvider

class ProcessorAWDataProvider(AWBaseDataProvider):
    """
    Processor 模块专用的 AW 数据提供者
    继承自 AWBaseDataProvider，使用全局 aw_db_manager
    """
    def __init__(self):
        # 调用父类初始化，使用全局单例 aw_db_manager
        super().__init__()


