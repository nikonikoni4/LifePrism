"""
分类颜色管理服务
提供统一的分类颜色生成和缓存机制
所有需要分类颜色的地方都应该使用这个服务
"""

import colorsys
import random
from typing import Dict, Optional
from lifewatch.storage import lw_db_manager


# 禁用分类使用的浅灰色
DISABLED_CATEGORY_COLOR = '#D1D5DB'

# Tailwind CSS 500 → 300 系列颜色映射
# 用于 Timeline 缩略图的柔和颜色显示
# ⚠️ 维护说明：如果前端调色盘变动，需同步更新此映射表
# @see frontend/page/category/components/CategorySettingsTab.tsx
TAILWIND_500_TO_300 = {
    '#EF4444': '#FCA5A5',  # red-300
    '#F97316': '#FDBA74',  # orange-300
    '#EAB308': '#FCD34D',  # yellow-300
    '#22C55E': '#86EFAC',  # green-300
    '#14B8A6': '#5EEAD4',  # teal-300
    '#06B6D4': '#67E8F9',  # cyan-300
    '#3B82F6': '#93C5FD',  # blue-300
    '#6366F1': '#A5B4FC',  # indigo-300
    '#A855F7': '#C4B5FD',  # purple-300
    '#EC4899': '#F9A8D4',  # pink-300
}

# Tailwind CSS 500 → 100 系列颜色映射
# 用于用户自定义区块的极浅色显示
# ⚠️ 维护说明：如果前端调色盘变动，需同步更新此映射表
# @see frontend/page/category/components/CategorySettingsTab.tsx
TAILWIND_500_TO_100 = {
    '#EF4444': '#FEE2E2',  # red-100
    '#F97316': '#FFEDD5',  # orange-100
    '#EAB308': '#FEF9C3',  # yellow-100
    '#22C55E': '#DCFCE7',  # green-100
    '#14B8A6': '#CCFBF1',  # teal-100
    '#06B6D4': '#CFFAFE',  # cyan-100
    '#3B82F6': '#DBEAFE',  # blue-100
    '#6366F1': '#E0E7FF',  # indigo-100
    '#A855F7': '#EDE9FE',  # purple-100
    '#EC4899': '#FCE7F3',  # pink-100
}


class CategoryColorManager:
    """
    分类颜色管理器（单例模式）
    负责生成和缓存所有分类的颜色
    """
    
    _instance: Optional['CategoryColorManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化颜色管理器"""
        if not CategoryColorManager._initialized:
            self.db_manager = lw_db_manager
            self._main_category_colors: Dict[str, str] = {}  # {category_id: color}
            self._sub_category_colors: Dict[str, str] = {}   # {sub_category_id: color}
            # Timeline 缩略图专用的柔和颜色缓存
            self._timeline_main_colors: Dict[str, str] = {}  # {category_id: soft_color}
            self._timeline_sub_colors: Dict[str, str] = {}   # {sub_category_id: soft_color}
            # 用户自定义区块专用的极浅色缓存
            self._custom_block_main_colors: Dict[str, str] = {}  # {category_id: lightest_color}
            self._custom_block_sub_colors: Dict[str, str] = {}   # {sub_category_id: lightest_color}
            CategoryColorManager._initialized = True
    
    def initialize_colors(self) -> None:
        """
        初始化所有分类的颜色
        从数据库读取所有分类，生成并缓存颜色
        应在应用启动时或首次请求时调用
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 获取所有主分类及其基础颜色和状态
            cursor.execute("""
                SELECT id, name, color, COALESCE(state, 1) as state
                FROM category 
                ORDER BY id
            """)
            main_categories = cursor.fetchall()
            
            # 记录禁用的主分类
            disabled_main_categories = set()
            
            for cat_id, cat_name, base_color, state in main_categories:
                if state == 0:
                    # 禁用的主分类使用浅灰色
                    self._main_category_colors[cat_id] = DISABLED_CATEGORY_COLOR
                    disabled_main_categories.add(cat_id)
                else:
                    # 启用的主分类使用数据库中的颜色
                    self._main_category_colors[cat_id] = base_color or self._get_default_color(cat_id)
            
            # 2. 获取所有子分类并生成渐变色（包含状态）
            cursor.execute("""
                SELECT sc.id, sc.name, sc.category_id, c.color, COALESCE(sc.state, 1) as state
                FROM sub_category sc
                LEFT JOIN category c ON sc.category_id = c.id
                ORDER BY sc.category_id, sc.id
            """)
            sub_categories = cursor.fetchall()
            
            # 按主分类分组（分离启用和禁用的子分类）
            sub_by_main: Dict[str, list] = {}  # 启用的子分类
            disabled_subs: Dict[str, str] = {}  # 禁用的子分类 {sub_id: sub_id}
            
            for sub_id, sub_name, main_cat_id, main_color, state in sub_categories:
                if state == 0 or main_cat_id in disabled_main_categories:
                    # 禁用的子分类，或者其主分类被禁用
                    disabled_subs[sub_id] = sub_id
                else:
                    if main_cat_id not in sub_by_main:
                        sub_by_main[main_cat_id] = []
                    sub_by_main[main_cat_id].append((sub_id, sub_name, main_color))
            
            # 为启用的子分类生成颜色变体
            for main_cat_id, subs in sub_by_main.items():
                base_color = self._main_category_colors.get(main_cat_id, '#5B8FF9')
                variant_colors = self._generate_color_variants(base_color, len(subs))
                
                for idx, (sub_id, sub_name, _) in enumerate(subs):
                    self._sub_category_colors[sub_id] = variant_colors[idx]
            
            # 为禁用的子分类设置浅灰色
            for sub_id in disabled_subs:
                self._sub_category_colors[sub_id] = DISABLED_CATEGORY_COLOR
            
            # 4. 初始化 Timeline 缩略图专用的柔和颜色
            self._initialize_timeline_colors()
    
    def get_main_category_color(self, category_id: str) -> str:
        """
        获取主分类颜色
        
        Args:
            category_id: 主分类ID
            
        Returns:
            str: 颜色值 (Hex)
        """
        if not self._main_category_colors:
            self.initialize_colors()
        
        return self._main_category_colors.get(category_id, self._get_default_color(category_id))
    
    def get_sub_category_color(self, sub_category_id: str) -> str:
        """
        获取子分类颜色
        
        Args:
            sub_category_id: 子分类ID
            
        Returns:
            str: 颜色值 (Hex)
        """
        if not self._sub_category_colors:
            self.initialize_colors()
        
        return self._sub_category_colors.get(sub_category_id, '#9CA3AF')
    
    def get_all_main_colors(self) -> Dict[str, str]:
        """
        获取所有主分类颜色映射
        
        Returns:
            Dict[str, str]: {category_id: color}
        """
        if not self._main_category_colors:
            self.initialize_colors()
        
        return self._main_category_colors.copy()
    
    def get_all_sub_colors(self) -> Dict[str, str]:
        """
        获取所有子分类颜色映射
        
        Returns:
            Dict[str, str]: {sub_category_id: color}
        """
        if not self._sub_category_colors:
            self.initialize_colors()
        
        return self._sub_category_colors.copy()
    
    def refresh_colors(self) -> None:
        """
        刷新颜色缓存（当数据库中的分类发生变化时调用）
        """
        self._main_category_colors.clear()
        self._sub_category_colors.clear()
        self._timeline_main_colors.clear()
        self._timeline_sub_colors.clear()
        self._custom_block_main_colors.clear()
        self._custom_block_sub_colors.clear()
        self.initialize_colors()
    
    # =========================================================================
    # Timeline 缩略图专用颜色（柔和色调）
    # =========================================================================
    
    def _initialize_timeline_colors(self) -> None:
        """
        初始化 Timeline 缩略图专用的柔和颜色
        基于原有颜色生成更柔和的变体（更高亮度、更低饱和度）
        """
        # 为主分类生成柔和颜色
        for cat_id, original_color in self._main_category_colors.items():
            if original_color == DISABLED_CATEGORY_COLOR:
                self._timeline_main_colors[cat_id] = DISABLED_CATEGORY_COLOR
            else:
                self._timeline_main_colors[cat_id] = self._soften_color(original_color)
        
        # 为子分类生成柔和颜色
        for sub_id, original_color in self._sub_category_colors.items():
            if original_color == DISABLED_CATEGORY_COLOR:
                self._timeline_sub_colors[sub_id] = DISABLED_CATEGORY_COLOR
            else:
                self._timeline_sub_colors[sub_id] = self._soften_color(original_color)
        
        # 同时初始化自定义区块的极浅色
        self._initialize_custom_block_colors()
    
    def _initialize_custom_block_colors(self) -> None:
        """
        初始化用户自定义区块专用的极浅颜色（Tailwind 100 系列）
        基于原有颜色生成最浅的变体，用于自定义区块的半透明覆盖显示
        """
        # 为主分类生成极浅颜色
        for cat_id, original_color in self._main_category_colors.items():
            if original_color == DISABLED_CATEGORY_COLOR:
                self._custom_block_main_colors[cat_id] = DISABLED_CATEGORY_COLOR
            else:
                self._custom_block_main_colors[cat_id] = self._lightest_color(original_color)
        
        # 为子分类生成极浅颜色
        for sub_id, original_color in self._sub_category_colors.items():
            if original_color == DISABLED_CATEGORY_COLOR:
                self._custom_block_sub_colors[sub_id] = DISABLED_CATEGORY_COLOR
            else:
                self._custom_block_sub_colors[sub_id] = self._lightest_color(original_color)
    
    def _soften_color(self, hex_color: str) -> str:
        """
        将颜色转换为更柔和的版本
        
        策略：
        1. 优先：检查 Tailwind 500→200 映射表，直接返回对应的 200 系列颜色
        2. 备用：如果不在映射表中，动态计算柔和色（提高亮度、降低饱和度）
        
        Args:
            hex_color: 原始 Hex 颜色
            
        Returns:
            str: 柔和的 Hex 颜色
        """
        # 标准化颜色格式（大写）
        normalized_color = hex_color.upper()
        
        # 1. 优先使用 Tailwind 500→200 映射
        if normalized_color in TAILWIND_500_TO_300:
            return TAILWIND_500_TO_300[normalized_color]

        # 2. 备用方案：动态计算柔和色
        color = hex_color
        if color.startswith('#'):
            color = color[1:]
        
        if len(color) != 6:
            return hex_color
        
        try:
            r = int(color[0:2], 16) / 255.0
            g = int(color[2:4], 16) / 255.0
            b = int(color[4:6], 16) / 255.0
        except ValueError:
            return hex_color
        
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        
        # 调整亮度和饱和度使颜色更柔和
        # 亮度提高到 0.70 ~ 0.78 范围
        new_l = 0.70 + (l * 0.1)  # 基础亮度 0.70，略微保留原亮度差异
        new_l = min(0.78, max(0.65, new_l))  # 限制在合理范围
        
        # 饱和度降低到原来的 55% ~ 70%
        new_s = s * 0.60
        new_s = max(0.25, min(0.55, new_s))  # 保证有一定饱和度但不会太鲜艳
        
        r_new, g_new, b_new = colorsys.hls_to_rgb(h, new_l, new_s)
        
        return "#{:02x}{:02x}{:02x}".format(
            int(max(0, min(1, r_new)) * 255),
            int(max(0, min(1, g_new)) * 255),
            int(max(0, min(1, b_new)) * 255)
        )
    
    def _lightest_color(self, hex_color: str) -> str:
        """
        将颜色转换为最浅的版本（Tailwind 100 系列）
        
        策略：
        1. 优先：检查 Tailwind 500→100 映射表，直接返回对应的 100 系列颜色
        2. 备用：如果不在映射表中，动态计算极浅色（更高亮度、更低饱和度）
        
        Args:
            hex_color: 原始 Hex 颜色
            
        Returns:
            str: 极浅的 Hex 颜色
        """
        # 标准化颜色格式（大写）
        normalized_color = hex_color.upper()
        
        # 1. 优先使用 Tailwind 500→100 映射
        if normalized_color in TAILWIND_500_TO_100:
            return TAILWIND_500_TO_100[normalized_color]
        # 2. 备用方案：动态计算极浅色
        color = hex_color
        if color.startswith('#'):
            color = color[1:]
        
        if len(color) != 6:
            return hex_color
        
        try:
            r = int(color[0:2], 16) / 255.0
            g = int(color[2:4], 16) / 255.0
            b = int(color[4:6], 16) / 255.0
        except ValueError:
            return hex_color
        
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        
        # 调整亮度和饱和度使颜色更浅（比 _soften_color 更浅）
        # 亮度提高到 0.90 ~ 0.95 范围（对应 Tailwind 100 系列）
        new_l = 0.90 + (l * 0.05)  # 基础亮度 0.90
        new_l = min(0.95, max(0.88, new_l))  # 限制在极浅范围
        
        # 饱和度大幅降低到原来的 25% ~ 40%
        new_s = s * 0.35
        new_s = max(0.15, min(0.35, new_s))  # 保留轻微色调
        
        r_new, g_new, b_new = colorsys.hls_to_rgb(h, new_l, new_s)
        
        return "#{:02x}{:02x}{:02x}".format(
            int(max(0, min(1, r_new)) * 255),
            int(max(0, min(1, g_new)) * 255),
            int(max(0, min(1, b_new)) * 255)
        )
    
    def get_timeline_main_color(self, category_id: str) -> str:
        """
        获取 Timeline 缩略图专用的主分类柔和颜色
        
        Args:
            category_id: 主分类ID
            
        Returns:
            str: 柔和颜色值 (Hex)
        """
        if not self._timeline_main_colors:
            if not self._main_category_colors:
                self.initialize_colors()
            else:
                self._initialize_timeline_colors()
        
        return self._timeline_main_colors.get(
            category_id, 
            self._soften_color(self._get_default_color(category_id))
        )
    
    def get_timeline_sub_color(self, sub_category_id: str) -> str:
        """
        获取 Timeline 缩略图专用的子分类柔和颜色
        
        Args:
            sub_category_id: 子分类ID
            
        Returns:
            str: 柔和颜色值 (Hex)
        """
        if not self._timeline_sub_colors:
            if not self._sub_category_colors:
                self.initialize_colors()
            else:
                self._initialize_timeline_colors()
        
        return self._timeline_sub_colors.get(
            sub_category_id,
            self._soften_color('#9CA3AF')  # 默认灰色的柔和版本
        )
    
    # =========================================================================
    # 用户自定义区块专用颜色（极浅色调，Tailwind 100 系列）
    # =========================================================================
    
    def get_custom_block_main_color(self, category_id: str) -> str:
        """
        获取用户自定义区块专用的主分类极浅颜色（Tailwind 100 系列）
        
        Args:
            category_id: 主分类ID
            
        Returns:
            str: 极浅颜色值 (Hex)
        """
        if not self._custom_block_main_colors:
            if not self._main_category_colors:
                self.initialize_colors()
            else:
                self._initialize_custom_block_colors()
        
        return self._custom_block_main_colors.get(
            category_id, 
            self._lightest_color(self._get_default_color(category_id))
        )
    
    def get_custom_block_sub_color(self, sub_category_id: str) -> str:
        """
        获取用户自定义区块专用的子分类极浅颜色（Tailwind 100 系列）
        
        Args:
            sub_category_id: 子分类ID
            
        Returns:
            str: 极浅颜色值 (Hex)
        """
        if not self._custom_block_sub_colors:
            if not self._sub_category_colors:
                self.initialize_colors()
            else:
                self._initialize_custom_block_colors()
        
        return self._custom_block_sub_colors.get(
            sub_category_id,
            self._lightest_color('#9CA3AF')  # 默认灰色的极浅版本
        )
    
    def _get_default_color(self, category_id: str) -> str:
        """
        为未找到颜色的分类生成默认颜色
        
        Args:
            category_id: 分类ID
            
        Returns:
            str: 默认颜色 (Hex)
        """
        # 基于分类ID的哈希值生成颜色
        hash_val = hash(category_id)
        hue = (hash_val % 360) / 360.0
        r, g, b = colorsys.hls_to_rgb(hue, 0.6, 0.7)
        return "#{:02x}{:02x}{:02x}".format(
            int(r * 255), int(g * 255), int(b * 255)
        )
    
    def _generate_color_variants(self, base_color: str, count: int, level: int = 2) -> list[str]:
        """
        基于基础颜色生成同色系配色方案（亮度渐变）
        
        Args:
            base_color: 基础颜色 (Hex)
            count: 需要生成的颜色数量
            level: 层级（2=子分类，3=具体log），层级越高颜色越浅
            
        Returns:
            list[str]: 颜色列表 (Hex)
        """
        # 处理 Hex 格式
        if base_color.startswith('#'):
            base_color = base_color[1:]
        
        if len(base_color) != 6:
            return [f"#{base_color}"] * count if base_color else ["#5B8FF9"] * count
            
        try:
            r = int(base_color[0:2], 16) / 255.0
            g = int(base_color[2:4], 16) / 255.0
            b = int(base_color[4:6], 16) / 255.0
        except ValueError:
            return ["#5B8FF9"] * count
        
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        
        colors = []
        
        if count <= 1:
            # 单个颜色时，根据层级选择亮度
            if level == 2:
                single_l = 0.55  # 子分类：中等偏深
            else:  # level == 3
                single_l = 0.75  # log：较浅
            r_new, g_new, b_new = colorsys.hls_to_rgb(h, single_l, s)
            return ["#{:02x}{:02x}{:02x}".format(
                int(max(0, min(1, r_new)) * 255),
                int(max(0, min(1, g_new)) * 255),
                int(max(0, min(1, b_new)) * 255)
            )]
            
        # 根据层级设置亮度范围
        # level=2 (子分类): 0.40 ~ 0.65 (较深)
        # level=3 (log): 0.65 ~ 0.88 (较浅)
        if level == 2:
            max_l = 0.65  # 子分类最浅亮度
            min_l = 0.40  # 子分类最深亮度
        else:  # level == 3
            max_l = 0.88  # log最浅亮度
            min_l = 0.65  # log最深亮度
        
        for i in range(count):
            if count > 1:
                # 从浅到深：第一个(i=0)使用max_l，最后一个使用min_l
                new_l = max_l - (max_l - min_l) * (i / (count - 1))
            else:
                new_l = l
                
            # 饱和度微调：浅色稍微降低饱和度，深色保持饱和度
            sat_ratio = 1 - 0.15 * ((count - 1 - i) / count) if count > 1 else 1
            new_s = s * sat_ratio
            
            r_new, g_new, b_new = colorsys.hls_to_rgb(h, new_l, new_s)
            
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(max(0, min(1, r_new)) * 255),
                int(max(0, min(1, g_new)) * 255),
                int(max(0, min(1, b_new)) * 255)
            )
            colors.append(hex_color)
            

        return colors
    
    def generate_color_variants(self, base_color: str, count: int, level: int = 2) -> list[str]:
        """
        公开方法：基于基础颜色生成同色系配色方案
        
        Args:
            base_color: 基础颜色 (Hex)
            count: 需要生成的颜色数量
            level: 层级（2=子分类，3=具体log），层级越高颜色越浅
            
        Returns:
            list[str]: 颜色列表 (Hex)
        """
        return self._generate_color_variants(base_color, count, level)


# 全局单例实例（懒加载）
from lifewatch.utils import LazySingleton
color_manager = LazySingleton(CategoryColorManager)


# 便捷函数
def get_category_color(category_id: str, is_sub_category: bool = False) -> str:
    """
    获取分类颜色的便捷函数
    
    Args:
        category_id: 分类ID
        is_sub_category: 是否为子分类
        
    Returns:
        str: 颜色值 (Hex)
    """
    if is_sub_category:
        return color_manager.get_sub_category_color(category_id)
    else:
        return color_manager.get_main_category_color(category_id)


def generate_color_variants(base_color: str, count: int, level: int = 2) -> list[str]:
    """
    生成颜色变体的便捷函数
    
    Args:
        base_color: 基础颜色 (Hex)
        count: 需要生成的颜色数量
        level: 层级（2=子分类，3=具体log），层级越高颜色越浅
            - level=2: 亮度范围 0.40~0.65 (较深，适用于子分类)
            - level=3: 亮度范围 0.65~0.88 (较浅，适用于具体log)
        
    Returns:
        list[str]: 颜色列表 (Hex)
    """
    return color_manager.generate_color_variants(base_color, count, level)


def initialize_category_colors() -> None:
    """
    初始化分类颜色（应在应用启动时调用）
    """
    color_manager.initialize_colors()


def get_log_color(base_color: str) -> str:
    """
    为 log 即时生成一个随机的浅色变体
    
    基于子分类颜色，在 level=3 的亮度范围 (0.65~0.88) 内随机生成一个浅色，
    用于区分同一子分类下的不同 log。
    
    Args:
        base_color: 子分类的基础颜色 (Hex)
        
    Returns:
        str: 随机生成的浅色 (Hex)
    """
    # 处理 Hex 格式
    color = base_color
    if color.startswith('#'):
        color = color[1:]
    
    if len(color) != 6:
        return base_color
        
    try:
        r = int(color[0:2], 16) / 255.0
        g = int(color[2:4], 16) / 255.0
        b = int(color[4:6], 16) / 255.0
    except ValueError:
        return base_color
    
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    
    # 在 level=3 的亮度范围内随机选择
    new_l = random.uniform(0.65, 0.88)
    
    # 饱和度略微降低，让浅色更柔和
    new_s = s * random.uniform(0.75, 0.95)
    
    r_new, g_new, b_new = colorsys.hls_to_rgb(h, new_l, new_s)
    
    return "#{:02x}{:02x}{:02x}".format(
        int(max(0, min(1, r_new)) * 255),
        int(max(0, min(1, g_new)) * 255),
        int(max(0, min(1, b_new)) * 255)
    )


def get_timeline_category_color(category_id: str, is_sub_category: bool = False) -> str:
    """
    获取 Timeline 缩略图专用的柔和分类颜色
    
    这些颜色比原分类颜色更柔和（更高亮度、更低饱和度），
    专门用于 Timeline 缩略图显示，使整体视觉效果更舒适。
    
    注意：旭日图等其他组件应继续使用 get_category_color() 获取原有颜色。
    
    Args:
        category_id: 分类ID
        is_sub_category: 是否为子分类
        
    Returns:
        str: 柔和颜色值 (Hex)
    """
    if is_sub_category:
        return color_manager.get_timeline_sub_color(category_id)
    else:
        return color_manager.get_timeline_main_color(category_id)


def get_custom_block_category_color(category_id: str, is_sub_category: bool = False) -> str:
    """
    获取用户自定义区块专用的极浅分类颜色（Tailwind 100 系列）
    
    这些颜色是最浅的变体，专门用于用户自定义区块的半透明覆盖显示，
    提供非常柔和的视觉效果，不会干扰底层的时间线显示。
    
    颜色层级：
    - get_category_color(): 原始颜色 (500系列)
    - get_timeline_category_color(): 柔和颜色 (300系列) - Timeline 缩略图
    - get_custom_block_category_color(): 极浅颜色 (100系列) - 自定义区块
    
    Args:
        category_id: 分类ID
        is_sub_category: 是否为子分类
        
    Returns:
        str: 极浅颜色值 (Hex)
    """
    if is_sub_category:
        return color_manager.get_custom_block_sub_color(category_id)
    else:
        return color_manager.get_custom_block_main_color(category_id)


if __name__ == "__main__":
    # 测试
    print("初始化颜色管理器...")
    color_manager.initialize_colors()
    
    print("\n主分类颜色:")
    main_colors = color_manager.get_all_main_colors()
    for cat_id, color in main_colors.items():
        print(f"  {cat_id}: {color}")
    
    print("\n子分类颜色:")
    sub_colors = color_manager.get_all_sub_colors()
    for sub_id, color in sub_colors.items():
        print(f"  {sub_id}: {color}")
    
    # 测试层级颜色生成
    print("\n层级颜色变体测试 (基础色: #3B82F6 blue-500):")
    base = "#3B82F6"
    
    print("\n  Level 2 (子分类, 较深):")
    level2_colors = generate_color_variants(base, 5, level=2)
    for i, c in enumerate(level2_colors):
        print(f"    [{i}] {c}")
    
    print("\n  Level 3 (Log, 较浅):")
    level3_colors = generate_color_variants(base, 5, level=3)
    for i, c in enumerate(level3_colors):
        print(f"    [{i}] {c}")
    
    # 测试 get_log_color 即时生成
    print("\n即时生成 Log 颜色测试 (基于子分类色 #3B82F6):")
    for i in range(5):
        log_color = get_log_color(base)
        print(f"  Log {i+1}: {log_color}")
