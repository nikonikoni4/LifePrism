"""
分类颜色管理服务
提供统一的分类颜色生成和缓存机制
所有需要分类颜色的地方都应该使用这个服务
"""

import colorsys
from typing import Dict, Optional
from lifewatch.server.providers.statistical_data_providers import server_lw_data_provider


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
            self.db_manager = server_lw_data_provider.db
            self._main_category_colors: Dict[str, str] = {}  # {category_id: color}
            self._sub_category_colors: Dict[str, str] = {}   # {sub_category_id: color}
            CategoryColorManager._initialized = True
    
    def initialize_colors(self) -> None:
        """
        初始化所有分类的颜色
        从数据库读取所有分类，生成并缓存颜色
        应在应用启动时或首次请求时调用
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 获取所有主分类及其基础颜色
            cursor.execute("""
                SELECT id, name, color 
                FROM category 
                ORDER BY id
            """)
            main_categories = cursor.fetchall()
            
            for cat_id, cat_name, base_color in main_categories:
                # 主分类使用数据库中的颜色
                self._main_category_colors[cat_id] = base_color or self._get_default_color(cat_id)
            
            # 2. 获取所有子分类并生成渐变色
            cursor.execute("""
                SELECT sc.id, sc.name, sc.category_id, c.color
                FROM sub_category sc
                LEFT JOIN category c ON sc.category_id = c.id
                ORDER BY sc.category_id, sc.id
            """)
            sub_categories = cursor.fetchall()
            
            # 按主分类分组
            sub_by_main: Dict[str, list] = {}
            for sub_id, sub_name, main_cat_id, main_color in sub_categories:
                if main_cat_id not in sub_by_main:
                    sub_by_main[main_cat_id] = []
                sub_by_main[main_cat_id].append((sub_id, sub_name, main_color))
            
            # 为每个主分类的子分类生成颜色变体
            for main_cat_id, subs in sub_by_main.items():
                base_color = self._main_category_colors.get(main_cat_id, '#5B8FF9')
                variant_colors = self._generate_color_variants(base_color, len(subs))
                
                for idx, (sub_id, sub_name, _) in enumerate(subs):
                    self._sub_category_colors[sub_id] = variant_colors[idx]
    
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
        self.initialize_colors()
    
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
    
    def _generate_color_variants(self, base_color: str, count: int) -> list[str]:
        """
        基于基础颜色生成同色系配色方案（亮度渐变）
        
        Args:
            base_color: 基础颜色 (Hex)
            count: 需要生成的颜色数量
            
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
            return [f"#{base_color}"]
            
        # 生成亮度渐变
        # 保持色相(H)和饱和度(S)基本不变，调整亮度(L)
        # 亮度范围: 0.35 (深) 到 0.85 (浅)
        
        for i in range(count):
            min_l = 0.35
            max_l = 0.85
            
            if count > 1:
                new_l = min_l + (max_l - min_l) * (i / (count - 1))
            else:
                new_l = l
                
            # 饱和度微调
            new_s = s * (1 - 0.2 * (i / count)) 
            
            r_new, g_new, b_new = colorsys.hls_to_rgb(h, new_l, new_s)
            
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(max(0, min(1, r_new)) * 255),
                int(max(0, min(1, g_new)) * 255),
                int(max(0, min(1, b_new)) * 255)
            )
            colors.append(hex_color)
            

        return colors


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


def initialize_category_colors() -> None:
    """
    初始化分类颜色（应在应用启动时调用）
    """
    color_manager.initialize_colors()


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
