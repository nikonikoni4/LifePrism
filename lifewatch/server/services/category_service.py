"""
分类管理服务层
实现分类的业务逻辑和数据库操作
"""
from lifewatch.server.providers.statistical_data_providers import server_lw_data_provider
from lifewatch.server.schemas.category_schemas import (
    CategoryTreeResponse,
    CategoryTreeItem,
    SubCategoryTreeItem,
    CategoryStatsResponse,
    CategoryStatsIncludeOptions,
    CategoryDef,
    SubCategoryDef,
    AppUseInfo,
    TitleDuration
)
from lifewatch.server.providers.category_color_provider import color_manager
from lifewatch.utils import get_logger
from lifewatch.utils.common_utils import is_multipurpose_app
from datetime import datetime
import uuid

logger = get_logger(__name__)


class CategoryService:
    """分类管理服务"""
    
    def __init__(self):
        """
        初始化分类服务，使用全局数据提供者单例
        """
        self.server_lw_data_provider = server_lw_data_provider
        self.db = server_lw_data_provider.db
        # 缓存 DataFrame
        self._categories_df = self.server_lw_data_provider.load_categories()
        self._sub_categories_df = self.server_lw_data_provider.load_sub_categories()
        
        # 初始化分类名称映射（禁用的分类添加 (banned) 后缀）
        self.category_name_map = {}
        if self._categories_df is not None and not self._categories_df.empty:
            for _, row in self._categories_df.iterrows():
                cat_id = str(row['id'])
                name = row['name']
                state = row.get('state', 1) if 'state' in self._categories_df.columns else 1
                if state == 0:
                    name = f"{name} (banned)"
                self.category_name_map[cat_id] = name
        
        # 初始化子分类名称映射（禁用的子分类添加 (banned) 后缀）
        self.sub_category_name_map = {}
        if self._sub_categories_df is not None and not self._sub_categories_df.empty:
            for _, row in self._sub_categories_df.iterrows():
                sub_id = str(row['id'])
                name = row['name']
                state = row.get('state', 1) if 'state' in self._sub_categories_df.columns else 1
                if state == 0:
                    name = f"{name} (banned)"
                self.sub_category_name_map[sub_id] = name
        
        # 子分类 -> 父分类ID映射
        self.sub_to_parent_map = {
            str(row['id']): str(row['category_id'])
            for _, row in self._sub_categories_df.iterrows()
        } if self._sub_categories_df is not None and not self._sub_categories_df.empty else {}
    
    def get_category_tree(self, depth) -> CategoryTreeResponse:
        """
        获取分类树
        
        Args:
            depth: 树的深度，1=仅主分类，2=主分类+子分类
            
        Returns:
            CategoryTreeResponse: 分类树响应
        """
        try:
            # 使用缓存的 DataFrame
            if self._categories_df is None or self._categories_df.empty:
                return CategoryTreeResponse(data=[])
            
            # 构建分类树
            category_tree = []
            for _, cat_row in self._categories_df.iterrows():
                category_id = str(cat_row['id'])
                
                # 构建子分类列表
                subcategories = None
                if depth >= 2 and self._sub_categories_df is not None and not self._sub_categories_df.empty:
                    # 筛选属于当前主分类的子分类
                    sub_df = self._sub_categories_df[self._sub_categories_df['category_id'] == cat_row['id']]
                    subcategories = [
                        SubCategoryTreeItem(
                            id=str(sub_row['id']),
                            name=self.sub_category_name_map.get(str(sub_row['id']), sub_row['name']),
                            color=color_manager.get_sub_category_color(str(sub_row['id'])),
                            state=int(sub_row.get('state', 1)) if 'state' in sub_df.columns else 1
                        )
                        for _, sub_row in sub_df.iterrows()
                    ]
                
                # 获取主分类的 state
                cat_state = int(cat_row.get('state', 1)) if 'state' in self._categories_df.columns else 1
                
                category_tree.append(CategoryTreeItem(
                    id=category_id,
                    name=self.category_name_map.get(category_id, cat_row['name']),
                    color=color_manager.get_main_category_color(category_id),
                    state=cat_state,
                    subcategories=subcategories
                ))
            
            return CategoryTreeResponse(data=category_tree)
            
        except Exception as e:
            logger.error(f"获取分类树失败: {e}")
            raise

    def get_category_stats(self,
                            start_time: datetime,
                            end_time: datetime,
                            include_options: CategoryStatsIncludeOptions,
                            top_title: int,
                            category: str,
                            sub_category: str) -> CategoryStatsResponse:
        """
        获取分类统计数据
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            include_options: 包含选项（由 API 层解析后传入）
            top_title: 返回的 Top 标题数量
            category: 按主分类ID筛选（可选）
            sub_category: 按子分类ID筛选（可选）
            
        Returns:
            CategoryStatsResponse: 分类统计响应
        """
        
        # 验证时间参数（在 try 之外，让验证错误直接抛出）
        now = datetime.now()
        if start_time >= end_time:
            raise ValueError(f"start_time ({start_time}) 必须小于 end_time ({end_time})")
        if end_time > now:
            raise ValueError(f"end_time ({end_time}) 不能大于当前时间 ({now})")
        
        try:
            # 直接使用结构化的 include 选项（由 API 层解析）
            include_duration = include_options.include_duration
            include_app = include_options.include_app
            include_title = include_options.include_title
            
            # 转换时间为字符串格式
            start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # 加载行为日志数据
            behavior_df = self.server_lw_data_provider.load_user_app_behavior_log(
                start_time=start_time_str,
                end_time=end_time_str
            )
            
            # 使用缓存的分类元数据
            if self._categories_df is None or self._categories_df.empty:
                return CategoryStatsResponse(data=[], query={"start_time": start_time_str, "end_time": end_time_str})
            
            # 如果没有行为数据，返回空结构
            if behavior_df is None or behavior_df.empty:
                return self._build_empty_category_state(
                    category, 
                    sub_category,
                    start_time_str, 
                    end_time_str,
                    include_options
                )
            
            # 应用筛选条件
            if category:
                behavior_df = behavior_df[behavior_df['category_id'] == category]
            if sub_category:
                behavior_df = behavior_df[behavior_df['sub_category_id'] == sub_category]
            
            if behavior_df.empty:
                return self._build_empty_category_state(
                    category, sub_category,
                    start_time_str, end_time_str,
                    include_options
                )
            
            # 计算总时长（用于百分比计算）
            total_duration = int(behavior_df['duration'].sum())
            
            # 按主分类聚合
            category_stats = behavior_df.groupby('category_id').agg({
                'duration': 'sum'
            }).reset_index()
            
            # 构建结果
            category_state = []
            
            for _, cat_stat in category_stats.iterrows():
                cat_id = str(cat_stat['category_id']) if cat_stat['category_id'] else None
                if not cat_id or cat_id == 'None':
                    continue
                    
                cat_duration = int(cat_stat['duration'])
                cat_percent = round(cat_duration * 100 / total_duration) if total_duration > 0 else 0
                
                # 过滤属于当前主分类的数据
                cat_behavior_df = behavior_df[behavior_df['category_id'] == cat_id]
                
                # 构建子分类列表
                subcategories = self._build_subcategory_stats(
                    cat_behavior_df, cat_duration,
                    include_app, include_title, top_title
                )
                
                category_state.append(CategoryDef(
                    id=cat_id,
                    name=self.category_name_map.get(cat_id, '未知'),
                    color=color_manager.get_main_category_color(cat_id),
                    duration=cat_duration if include_duration else None,
                    duration_percent=cat_percent if include_duration else None,
                    subcategories=subcategories
                ))
            
            # 按时长降序排序
            category_state.sort(key=lambda x: x.duration or 0, reverse=True)
            
            return CategoryStatsResponse(
                data=category_state,
                query={
                    "start_time": start_time_str,
                    "end_time": end_time_str,
                    "include_options": include_options.model_dump(),
                    "category": category,
                    "sub_category": sub_category
                }
            )
            
        except Exception as e:
            logger.error(f"获取分类状态失败: {e}")
            raise
    
    def _build_subcategory_stats(self,
                                  cat_behavior_df,
                                  parent_duration: int,
                                  include_app: bool,
                                  include_title: bool,
                                  top_title: int) -> list[SubCategoryDef]:
        """构建子分类统计数据"""
        # 按子分类聚合
        sub_stats = cat_behavior_df.groupby('sub_category_id').agg({
            'duration': 'sum'
        }).reset_index()
        
        subcategories = []
        for _, sub_stat in sub_stats.iterrows():
            sub_id = str(sub_stat['sub_category_id']) if sub_stat['sub_category_id'] else None
            if not sub_id or sub_id == 'None':
                continue
                
            sub_duration = int(sub_stat['duration'])
            sub_percent = round(sub_duration * 100 / parent_duration) if parent_duration > 0 else 0
            
            # 过滤属于当前子分类的数据
            sub_behavior_df = cat_behavior_df[cat_behavior_df['sub_category_id'] == sub_id]
            
            # 构建应用列表
            app_use_info = None
            if include_app:
                app_use_info = self._build_app_stats(sub_behavior_df, include_title, top_title)
            
            subcategories.append(SubCategoryDef(
                id=sub_id,
                name=self.sub_category_name_map.get(sub_id, '未知'),
                color=color_manager.get_sub_category_color(sub_id),
                duration=sub_duration,
                duration_percent=sub_percent,
                app_use_info=app_use_info
            ))
        
        # 按时长降序排序
        subcategories.sort(key=lambda x: x.duration or 0, reverse=True)
        return subcategories
    
    def _build_app_stats(self,
                         sub_behavior_df,
                         include_title: bool,
                         top_title: int) -> list:
        """构建应用统计数据"""
        # 按应用聚合
        app_stats = sub_behavior_df.groupby('app').agg({
            'duration': 'sum'
        }).reset_index().sort_values('duration', ascending=False)
        
        apps = []
        for _, app_stat in app_stats.iterrows():
            app_name = app_stat['app']
            app_duration = int(app_stat['duration'])
            
            # 构建标题列表
            top_titles = None
            if include_title:
                app_behavior_df = sub_behavior_df[sub_behavior_df['app'] == app_name]
                title_stats = app_behavior_df.groupby('title').agg({
                    'duration': 'sum'
                }).reset_index().sort_values('duration', ascending=False).head(top_title)
                
                top_titles = [
                    TitleDuration(
                        title=str(row['title']) if row['title'] else '(无标题)',
                        duration=int(row['duration'])
                    )
                    for _, row in title_stats.iterrows()
                ]
            
            apps.append(AppUseInfo(
                name=app_name,
                duration=app_duration,
                top_titles=top_titles
            ))
        
        return apps
    
    def _build_empty_category_state(self,
                                     category_filter: str,
                                     sub_category_filter: str,
                                     start_time_str: str,
                                     end_time_str: str,
                                     include_options: CategoryStatsIncludeOptions) -> CategoryStatsResponse:
        """构建空数据状态响应"""
        
        # 如果有筛选条件，只返回筛选的分类
        if category_filter:
            filtered_cats = self._categories_df[self._categories_df['id'] == category_filter]
        else:
            filtered_cats = self._categories_df
            
        category_state = []
        for _, cat_row in filtered_cats.iterrows():
            cat_id = str(cat_row['id'])
            
            # 构建子分类（空数据）
            subcategories = None
            if self._sub_categories_df is not None and not self._sub_categories_df.empty:
                sub_df = self._sub_categories_df[self._sub_categories_df['category_id'] == cat_row['id']]
                if sub_category_filter:
                    sub_df = sub_df[sub_df['id'] == sub_category_filter]
                    
                subcategories = [
                    SubCategoryDef(
                        id=str(sub_row['id']),
                        name=self.sub_category_name_map.get(str(sub_row['id']), sub_row['name']),
                        color=color_manager.get_sub_category_color(str(sub_row['id'])),
                        duration=0,
                        duration_percent=0,
                        app_use_info=[]
                    )
                    for _, sub_row in sub_df.iterrows()
                ]
            
            category_state.append(CategoryDef(
                id=cat_id,
                name=self.category_name_map.get(cat_id, cat_row['name']),
                color=color_manager.get_main_category_color(cat_id),
                duration=0,
                duration_percent=0,
                subcategories=subcategories
            ))
        
        return CategoryStatsResponse(
            data=category_state,
            query={
                "start_time": start_time_str,
                "end_time": end_time_str,
                "include_options": include_options.model_dump(),
                "category": category_filter,
                "sub_category": sub_category_filter
            }
        )
    
    def _refresh_cache(self):
        """刷新分类缓存"""
        self._categories_df = self.server_lw_data_provider.load_categories()
        self._sub_categories_df = self.server_lw_data_provider.load_sub_categories()
        
        # 更新名称映射（禁用的分类添加 (banned) 后缀）
        self.category_name_map = {}
        if self._categories_df is not None and not self._categories_df.empty:
            for _, row in self._categories_df.iterrows():
                cat_id = str(row['id'])
                name = row['name']
                state = row.get('state', 1) if 'state' in self._categories_df.columns else 1
                if state == 0:
                    name = f"{name} (banned)"
                self.category_name_map[cat_id] = name
        
        self.sub_category_name_map = {}
        if self._sub_categories_df is not None and not self._sub_categories_df.empty:
            for _, row in self._sub_categories_df.iterrows():
                sub_id = str(row['id'])
                name = row['name']
                state = row.get('state', 1) if 'state' in self._sub_categories_df.columns else 1
                if state == 0:
                    name = f"{name} (banned)"
                self.sub_category_name_map[sub_id] = name
        
        self.sub_to_parent_map = {
            str(row['id']): str(row['category_id'])
            for _, row in self._sub_categories_df.iterrows()
        } if self._sub_categories_df is not None and not self._sub_categories_df.empty else {}
        
        # 刷新颜色管理器缓存
        color_manager.refresh_colors()
    
    def create_category(self, name: str, color: str) -> CategoryTreeItem:
        """
        创建新的主分类
        
        Args:
            name: 分类名称
            color: 分类颜色（十六进制格式）
            
        Returns:
            CategoryTreeItem: 创建的分类对象
        """
        try:
            if not name or not color:
                raise ValueError("分类名称和颜色不能为空")
            # 生成唯一ID（使用短UUID）
            category_id = f"cat-{str(uuid.uuid4())[:8]}"
            
            # 获取当前最大的 order_index
            categories_df = self.db.query('category')
            max_order = 0
            if not categories_df.empty and 'order_index' in categories_df.columns:
                max_order = categories_df['order_index'].max()
            
            # 插入数据
            data = {
                'id': category_id,
                'name': name,
                'color': color,
                'order_index': max_order + 1
            }
            
            self.db.insert('category', data)
            logger.info(f"成功创建分类: {category_id} - {name}")
            
            # 刷新缓存
            self._refresh_cache()
            
            return CategoryTreeItem(
                id=category_id,
                name=name,
                color=color,
                subcategories=[]
            )
            
        except Exception as e:
            logger.error(f"创建分类失败: {e}")
            raise
    
    def update_category(self, category_id: str, name: str, color: str) -> CategoryTreeItem:
        """
        更新主分类
        
        Args:
            category_id: 分类ID
            name: 新的分类名称（空字符串表示不更新）
            color: 新的分类颜色（空字符串表示不更新）
            
        Returns:
            CategoryTreeItem: 更新后的分类对象
            
        Raises:
            ValueError: 如果分类不存在
        """
        try:
            # 检查分类是否存在
            existing = self.db.get_by_id('category', 'id', category_id)
            if not existing:
                raise ValueError(f"分类 '{category_id}' 不存在")
            
            # 构建更新数据
            update_data = {}
            if name:
                update_data['name'] = name
            if color:
                update_data['color'] = color
            
            if not update_data:
                logger.warning("没有提供任何更新字段")
                return self._get_category_by_id(category_id)
            
            # 执行更新
            self.db.update_by_id('category', 'id', category_id, update_data)
            logger.info(f"成功更新分类: {category_id}")
            
            # 刷新缓存
            self._refresh_cache()
            
            # 返回更新后的分类
            return self._get_category_by_id(category_id)
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"更新分类失败: {e}")
            raise
    
    def delete_category(self, category_id: str, reassign_to: str) -> bool:
        """
        删除主分类
        
        Args:
            category_id: 要删除的分类ID
            reassign_to: 重新分配关联记录到的分类ID
            
        Returns:
            bool: 是否成功删除
            
        Raises:
            ValueError: 如果分类不存在
        """
        try:
            # 检查分类是否存在
            existing = self.db.get_by_id('category', 'id', category_id)
            if not existing:
                raise ValueError(f"分类 '{category_id}' 不存在")
            
            # 1. 重新分配关联的行为日志记录
            behavior_logs = self.db.query(
                'user_app_behavior_log',
                where={'category_id': category_id}
            )
            
            if not behavior_logs.empty:
                logger.info(f"找到 {len(behavior_logs)} 条关联记录，重新分配到 '{reassign_to}'")
                self.db.update(
                    'user_app_behavior_log',
                    {'category_id': reassign_to, 'sub_category_id': 'untracked'},
                    {'category_id': category_id}
                )
            
            # 2. 删除主分类（子分类会通过 CASCADE 自动删除）
            self.db.delete_by_id('category', 'id', category_id)
            logger.info(f"成功删除分类: {category_id}")
            
            # 刷新缓存
            self._refresh_cache()
            
            return True
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"删除分类失败: {e}")
            raise
    
    def create_sub_category(self, category_id: str, name: str) -> SubCategoryTreeItem:
        """
        创建子分类
        
        Args:
            category_id: 所属主分类ID
            name: 子分类名称
            
        Returns:
            SubCategoryTreeItem: 创建的子分类对象
            
        Raises:
            ValueError: 如果主分类不存在
        """
        try:
            # 验证主分类存在
            existing_cat = self.db.get_by_id('category', 'id', category_id)
            if not existing_cat:
                raise ValueError(f"主分类 '{category_id}' 不存在")
            
            # 生成唯一ID
            sub_id = f"sub-{str(uuid.uuid4())[:8]}"
            
            # 获取当前最大的 order_index
            sub_cats_df = self.db.query(
                'sub_category',
                where={'category_id': category_id}
            )
            max_order = 0
            if not sub_cats_df.empty and 'order_index' in sub_cats_df.columns:
                max_order = sub_cats_df['order_index'].max()
            
            # 插入数据
            data = {
                'id': sub_id,
                'category_id': category_id,
                'name': name,
                'order_index': max_order + 1
            }
            
            self.db.insert('sub_category', data)
            logger.info(f"成功创建子分类: {sub_id} - {name}")
            
            # 刷新缓存
            self._refresh_cache()
            
            return SubCategoryTreeItem(
                id=sub_id,
                name=name,
                color=color_manager.get_sub_category_color(sub_id)
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"创建子分类失败: {e}")
            raise
    
    def update_sub_category(self, category_id: str, sub_id: str, name: str) -> SubCategoryTreeItem:
        """
        更新子分类
        
        Args:
            category_id: 所属主分类ID
            sub_id: 子分类ID
            name: 新的子分类名称
            
        Returns:
            SubCategoryTreeItem: 更新后的子分类对象
            
        Raises:
            ValueError: 如果主分类或子分类不存在
        """
        try:
            # 验证主分类存在
            existing_cat = self.db.get_by_id('category', 'id', category_id)
            if not existing_cat:
                raise ValueError(f"主分类 '{category_id}' 不存在")
            
            # 验证子分类存在且属于该主分类
            existing_sub = self.db.get_by_id('sub_category', 'id', sub_id)
            if not existing_sub:
                raise ValueError(f"子分类 '{sub_id}' 不存在")
            
            if existing_sub['category_id'] != category_id:
                raise ValueError(f"子分类 '{sub_id}' 不属于分类 '{category_id}'")
            
            # 更新子分类
            self.db.update_by_id('sub_category', 'id', sub_id, {'name': name})
            logger.info(f"成功更新子分类: {sub_id}")
            
            # 刷新缓存
            self._refresh_cache()
            
            return SubCategoryTreeItem(
                id=sub_id,
                name=name,
                color=color_manager.get_sub_category_color(sub_id)
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"更新子分类失败: {e}")
            raise
    
    def delete_sub_category(self, category_id: str, sub_id: str) -> bool:
        """
        删除子分类
        
        Args:
            category_id: 所属主分类ID
            sub_id: 子分类ID
            
        Returns:
            bool: 是否成功删除
            
        Raises:
            ValueError: 如果主分类或子分类不存在
        """
        try:
            # 验证主分类存在
            existing_cat = self.db.get_by_id('category', 'id', category_id)
            if not existing_cat:
                raise ValueError(f"主分类 '{category_id}' 不存在")
            
            # 验证子分类存在且属于该主分类
            existing_sub = self.db.get_by_id('sub_category', 'id', sub_id)
            if not existing_sub:
                raise ValueError(f"子分类 '{sub_id}' 不存在")
            
            if existing_sub['category_id'] != category_id:
                raise ValueError(f"子分类 '{sub_id}' 不属于分类 '{category_id}'")
            
            # 重新分配关联的行为日志记录
            behavior_logs = self.db.query(
                'user_app_behavior_log',
                where={'sub_category_id': sub_id}
            )
            
            if not behavior_logs.empty:
                logger.info(f"找到 {len(behavior_logs)} 条关联记录，重新分配到 'untracked'")
                self.db.update(
                    'user_app_behavior_log',
                    {'sub_category_id': 'untracked'},
                    {'sub_category_id': sub_id}
                )
            
            # 删除子分类
            self.db.delete_by_id('sub_category', 'id', sub_id)
            logger.info(f"成功删除子分类: {sub_id}")
            
            # 刷新缓存
            self._refresh_cache()
            
            return True
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"删除子分类失败: {e}")
            raise
    
    def _get_category_by_id(self, category_id: str) -> CategoryTreeItem:
        """
        根据ID获取完整的分类对象（含子分类）- 内部使用，不存在时抛出异常
        
        Args:
            category_id: 分类ID
            
        Returns:
            CategoryTreeItem: 分类对象
        """
        category = self.db.get_by_id('category', 'id', category_id)
        if not category:
            raise ValueError(f"分类 '{category_id}' 不存在")
        
        # 获取子分类
        sub_cats_df = self.db.query(
            'sub_category',
            where={'category_id': category_id},
            order_by='order_index ASC'
        )
        
        subcategories = []
        if not sub_cats_df.empty:
            for _, sub_row in sub_cats_df.iterrows():
                subcategories.append(SubCategoryTreeItem(
                    id=str(sub_row['id']),
                    name=sub_row['name'],
                    color=color_manager.get_sub_category_color(str(sub_row['id']))
                ))
        
        return CategoryTreeItem(
            id=category['id'],
            name=category['name'],
            color=color_manager.get_main_category_color(category['id']),
            subcategories=subcategories
        )
    
    def get_category_by_id(self, category_id: str) -> CategoryTreeItem:
        """
        根据ID获取分类对象（公共方法，不存在时返回None）
        
        Args:
            category_id: 分类ID
            
        Returns:
            CategoryTreeItem: 分类对象，或 None 如果不存在
        """
        category = self.db.get_by_id('category', 'id', category_id)
        if not category:
            return None
        
        return CategoryTreeItem(
            id=category['id'],
            name=category['name'],
            color=color_manager.get_main_category_color(category['id'])
        )
    
    def toggle_category_state(self, category_id: str, state: int) -> CategoryTreeItem:
        """
        切换主分类的启用/禁用状态
        
        Args:
            category_id: 分类ID
            state: 新状态（1: 启用, 0: 禁用）
            
        Returns:
            CategoryTreeItem: 更新后的分类对象
            
        Raises:
            ValueError: 如果分类不存在
        """
        try:
            # 检查分类是否存在
            existing = self.db.get_by_id('category', 'id', category_id)
            if not existing:
                raise ValueError(f"分类 '{category_id}' 不存在")
            
            old_state = existing.get('state', 1)
            
            # 更新分类状态
            self.db.update_by_id('category', 'id', category_id, {'state': state})
            logger.info(f"成功切换分类 '{category_id}' 状态为 {state}")
            
            # 同步更新 app_purpose_category 表的 state
            if state == 0:
                # 禁用：将该分类下所有记录的 state 置为 0
                self._disable_app_purpose_records_by_category(category_id)
            elif state == 1 and old_state == 0:
                # 启用：恢复符合条件的记录（主分类和子分类都启用）
                self._enable_app_purpose_records_by_category(category_id)
            
            # 刷新缓存
            self._refresh_cache()
            
            # 返回更新后的分类
            return self._get_category_by_id(category_id)
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"切换分类状态失败: {e}")
            raise
    
    def toggle_sub_category_state(self, category_id: str, sub_id: str, state: int) -> SubCategoryTreeItem:
        """
        切换子分类的启用/禁用状态
        
        Args:
            category_id: 主分类ID
            sub_id: 子分类ID
            state: 新状态（1: 启用, 0: 禁用）
            
        Returns:
            SubCategoryTreeItem: 更新后的子分类对象
            
        Raises:
            ValueError: 如果主分类或子分类不存在
        """
        try:
            # 验证主分类存在
            existing_cat = self.db.get_by_id('category', 'id', category_id)
            if not existing_cat:
                raise ValueError(f"主分类 '{category_id}' 不存在")
            
            # 验证子分类存在且属于该主分类
            existing_sub = self.db.get_by_id('sub_category', 'id', sub_id)
            if not existing_sub:
                raise ValueError(f"子分类 '{sub_id}' 不存在")
            
            if existing_sub['category_id'] != category_id:
                raise ValueError(f"子分类 '{sub_id}' 不属于分类 '{category_id}'")
            
            old_state = existing_sub.get('state', 1)
            
            # 更新子分类状态
            self.db.update_by_id('sub_category', 'id', sub_id, {'state': state})
            logger.info(f"成功切换子分类 '{sub_id}' 状态为 {state}")
            
            # 同步更新 app_purpose_category 表的 state
            if state == 0:
                # 禁用：将该子分类下所有记录的 state 置为 0
                self._disable_app_purpose_records_by_sub_category(sub_id)
            elif state == 1 and old_state == 0:
                # 启用：恢复符合条件的记录（主分类和子分类都启用）
                self._enable_app_purpose_records_by_sub_category(sub_id, category_id)
            
            # 刷新缓存
            self._refresh_cache()
            
            # 返回更新后的子分类
            return SubCategoryTreeItem(
                id=sub_id,
                name=self.sub_category_name_map.get(sub_id, existing_sub['name']),
                color=color_manager.get_sub_category_color(sub_id),
                state=state
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"切换子分类状态失败: {e}")
            raise
    
    # ==================== app_purpose_category 状态同步方法 ====================
    
    def _disable_app_purpose_records_by_category(self, category_id: str):
        """
        禁用主分类时，将 app_purpose_category 中该分类的所有记录 state 置为 0
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE app_purpose_category 
                    SET state = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE category_id = ?
                """, (category_id,))
                affected = cursor.rowcount
                conn.commit()
                logger.info(f"禁用分类 '{category_id}' 时，置 {affected} 条 app_purpose_category 记录为无效")
        except Exception as e:
            logger.error(f"禁用分类记录失败: {e}")
            raise
    
    def _disable_app_purpose_records_by_sub_category(self, sub_category_id: str):
        """
        禁用子分类时，将 app_purpose_category 中该子分类的所有记录 state 置为 0
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE app_purpose_category 
                    SET state = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE sub_category_id = ?
                """, (sub_category_id,))
                affected = cursor.rowcount
                conn.commit()
                logger.info(f"禁用子分类 '{sub_category_id}' 时，置 {affected} 条 app_purpose_category 记录为无效")
        except Exception as e:
            logger.error(f"禁用子分类记录失败: {e}")
            raise
    
    def _enable_app_purpose_records_by_category(self, category_id: str):
        """
        启用主分类时，恢复 app_purpose_category 中符合条件的记录
        
        恢复条件：主分类启用 AND 子分类也启用
        恢复前：删除同 (app, title) 中 created_at 更晚的记录
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取该分类下所有子分类的启用状态
                cursor.execute("""
                    SELECT id, state FROM sub_category WHERE category_id = ?
                """, (category_id,))
                sub_categories = {row[0]: row[1] for row in cursor.fetchall()}
                
                # 获取该分类下所有待恢复的记录
                cursor.execute("""
                    SELECT app, title, sub_category_id, created_at 
                    FROM app_purpose_category 
                    WHERE category_id = ? AND state = 0
                """, (category_id,))
                records = cursor.fetchall()
                
                total_enabled = 0
                total_deleted = 0
                
                for app, title, sub_cat_id, created_at in records:
                    # 检查子分类是否也启用
                    sub_state = sub_categories.get(sub_cat_id, 1)  # 默认启用
                    if sub_state == 0:
                        # 子分类还是禁用状态，不恢复
                        continue
                    
                    # 根据应用类型选择删除条件
                    # 单分类应用：只匹配 app 删除（同一 app 只有一个分类）
                    # 多分类应用：匹配 app + title 删除（同一 app 不同 title 可能有不同分类）
                    if created_at:
                        if is_multipurpose_app(app):
                            # 多分类应用：删除同 (app, title) 中 created_at 更晚的记录
                            cursor.execute("""
                                DELETE FROM app_purpose_category 
                                WHERE app = ? AND title = ? AND created_at > ?
                            """, (app, title, created_at))
                        else:
                            # 单分类应用：删除同 app 中 created_at 更晚的记录
                            cursor.execute("""
                                DELETE FROM app_purpose_category 
                                WHERE app = ? AND created_at > ?
                            """, (app, created_at))
                        total_deleted += cursor.rowcount
                    
                    # 恢复该记录
                    cursor.execute("""
                        UPDATE app_purpose_category 
                        SET state = 1, updated_at = CURRENT_TIMESTAMP
                        WHERE app = ? AND title = ? AND category_id = ?
                    """, (app, title, category_id))
                    total_enabled += cursor.rowcount
                
                conn.commit()
                logger.info(f"启用分类 '{category_id}' 时，恢复 {total_enabled} 条记录，删除 {total_deleted} 条冲突记录")
                
        except Exception as e:
            logger.error(f"启用分类记录失败: {e}")
            raise
    
    def _enable_app_purpose_records_by_sub_category(self, sub_category_id: str, category_id: str):
        """
        启用子分类时，恢复 app_purpose_category 中符合条件的记录
        
        恢复条件：主分类启用 AND 子分类启用
        恢复前：删除同 (app, title) 中 created_at 更晚的记录
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 检查主分类是否启用
                cursor.execute("""
                    SELECT state FROM category WHERE id = ?
                """, (category_id,))
                result = cursor.fetchone()
                if not result or result[0] == 0:
                    # 主分类还是禁用状态，不恢复
                    logger.info(f"主分类 '{category_id}' 仍处于禁用状态，跳过恢复子分类记录")
                    return
                
                # 获取该子分类下所有待恢复的记录
                cursor.execute("""
                    SELECT app, title, created_at 
                    FROM app_purpose_category 
                    WHERE sub_category_id = ? AND state = 0
                """, (sub_category_id,))
                records = cursor.fetchall()
                
                total_enabled = 0
                total_deleted = 0
                
                for app, title, created_at in records:
                    # 根据应用类型选择删除条件
                    # 单分类应用：只匹配 app 删除（同一 app 只有一个分类）
                    # 多分类应用：匹配 app + title 删除（同一 app 不同 title 可能有不同分类）
                    if created_at:
                        if is_multipurpose_app(app):
                            # 多分类应用：删除同 (app, title) 中 created_at 更晚的记录
                            cursor.execute("""
                                DELETE FROM app_purpose_category 
                                WHERE app = ? AND title = ? AND created_at > ?
                            """, (app, title, created_at))
                        else:
                            # 单分类应用：删除同 app 中 created_at 更晚的记录
                            cursor.execute("""
                                DELETE FROM app_purpose_category 
                                WHERE app = ? AND created_at > ?
                            """, (app, created_at))
                        total_deleted += cursor.rowcount
                    
                    # 恢复该记录
                    cursor.execute("""
                        UPDATE app_purpose_category 
                        SET state = 1, updated_at = CURRENT_TIMESTAMP
                        WHERE app = ? AND title = ? AND sub_category_id = ?
                    """, (app, title, sub_category_id))
                    total_enabled += cursor.rowcount
                
                conn.commit()
                logger.info(f"启用子分类 '{sub_category_id}' 时，恢复 {total_enabled} 条记录，删除 {total_deleted} 条冲突记录")
                
        except Exception as e:
            logger.error(f"启用子分类记录失败: {e}")
            raise

    # ==================== app_purpose_category 数据管理 ====================
    
    def get_app_purpose_category_list(
        self,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        state: int | None = None
    ):
        """
        获取 app_purpose_category 列表
        
        Args:
            page: 页码
            page_size: 每页数量
            search: 搜索关键词
            state: 状态筛选
        
        Returns:
            AppPurposeCategoryResponse: 分页响应
        """
        from lifewatch.server.schemas.category_schemas import (
            AppPurposeCategoryItem,
            AppPurposeCategoryResponse
        )
        import math
        
        try:
            # 调用 base provider 的分页查询
            result = self.server_lw_data_provider.load_app_purpose_category(
                page=page,
                page_size=page_size,
                search=search,
                state=state
            )
            
            # 分页查询返回 (df, total) 元组
            df, total = result
            
            # 构建响应数据
            items = []
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    # 映射 category_id 和 sub_category_id 到名称
                    category_id = row.get('category_id')
                    sub_category_id = row.get('sub_category_id')
                    
                    category_name = self.category_name_map.get(str(category_id), None) if category_id else None
                    sub_category_name = self.sub_category_name_map.get(str(sub_category_id), None) if sub_category_id else None
                    
                    items.append(AppPurposeCategoryItem(
                        id=int(row['id']),
                        app=row['app'],
                        app_description=row.get('app_description'),
                        title=row['title'],
                        title_analysis=row.get('title_analysis'),
                        category=category_name,
                        sub_category=sub_category_name,
                        category_id=str(category_id) if category_id else None,
                        sub_category_id=str(sub_category_id) if sub_category_id else None,
                        is_multipurpose_app=bool(row.get('is_multipurpose_app', 0)),
                        state=int(row.get('state', 1)),
                        created_at=str(row.get('created_at')) if row.get('created_at') else None
                    ))
            
            total_pages = math.ceil(total / page_size) if total > 0 else 1
            
            return AppPurposeCategoryResponse(
                data=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
            
        except Exception as e:
            logger.error(f"获取 app_purpose_category 列表失败: {e}")
            raise
    
    def _get_category_state_from_cache(self, category_id: str) -> int:
        """
        从缓存获取分类的状态
        
        Args:
            category_id: 主分类ID
        
        Returns:
            int: 分类状态（1: 启用, 0: 禁用），默认返回 1
        """
        if self._categories_df is None or self._categories_df.empty:
            return 1
        
        cat_row = self._categories_df[self._categories_df['id'] == category_id]
        if cat_row.empty:
            return 1
        
        return int(cat_row.iloc[0].get('state', 1))
    
    def update_app_purpose_category(
        self, 
        record_id: int, 
        category_id: str, 
        sub_category_id: str | None = None
    ) -> bool:
        """
        更新 app_purpose_category 记录的分类
        
        Args:
            record_id: 记录ID
            category_id: 新的主分类ID
            sub_category_id: 新的子分类ID
        
        Returns:
            bool: 是否更新成功
        """
        try:
            # 从缓存获取目标分类的状态
            state = self._get_category_state_from_cache(category_id)
            
            result = self.server_lw_data_provider.update_app_purpose_category_by_id(
                record_id=record_id,
                category_id=category_id,
                sub_category_id=sub_category_id,
                state=state
            )
            
            if result:
                logger.info(f"成功更新 app_purpose_category 记录 ID={record_id} 的分类")
            else:
                logger.warning(f"未找到 app_purpose_category 记录 ID={record_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"更新 app_purpose_category 记录失败: {e}")
            raise
    
    def batch_update_app_purpose_category(
        self,
        record_ids: list[int],
        category_id: str,
        sub_category_id: str | None = None
    ) -> int:
        """
        批量更新 app_purpose_category 记录的分类
        
        Args:
            record_ids: 记录ID列表
            category_id: 新的主分类ID
            sub_category_id: 新的子分类ID
        
        Returns:
            int: 成功更新的数量
        """
        try:
            # 从缓存获取目标分类的状态
            state = self._get_category_state_from_cache(category_id)
            
            count = self.server_lw_data_provider.batch_update_app_purpose_category_by_ids(
                record_ids=record_ids,
                category_id=category_id,
                sub_category_id=sub_category_id,
                state=state
            )
            
            logger.info(f"批量更新 {count} 条 app_purpose_category 记录的分类")
            return count
            
        except Exception as e:
            logger.error(f"批量更新 app_purpose_category 记录失败: {e}")
            raise
    
    def delete_app_purpose_category(self, record_id: int) -> bool:
        """
        删除 app_purpose_category 记录
        
        Args:
            record_id: 记录ID
        
        Returns:
            bool: 是否删除成功
        """
        try:
            result = self.server_lw_data_provider.delete_app_purpose_category_by_id(record_id)
            
            if result:
                logger.info(f"成功删除 app_purpose_category 记录 ID={record_id}")
            else:
                logger.warning(f"未找到 app_purpose_category 记录 ID={record_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"删除 app_purpose_category 记录失败: {e}")
            raise
    
    def batch_delete_app_purpose_category(self, record_ids: list[int]) -> int:
        """
        批量删除 app_purpose_category 记录
        
        Args:
            record_ids: 记录ID列表
        
        Returns:
            int: 成功删除的数量
        """
        try:
            count = self.server_lw_data_provider.batch_delete_app_purpose_category_by_ids(record_ids)
            
            logger.info(f"批量删除 {count} 条 app_purpose_category 记录")
            return count
            
        except Exception as e:
            logger.error(f"批量删除 app_purpose_category 记录失败: {e}")
            raise


if __name__ == "__main__":
    from datetime import datetime, timedelta
    from lifewatch.server.schemas.category_schemas import CategoryStatsIncludeOptions
    
    test_service = CategoryService()
    
    # 测试 get_category_stats
    end_time = datetime.now()
    start_time = end_time - timedelta(days=1)
    
    include_options = CategoryStatsIncludeOptions.from_include_string("duration,app,title")
    
    category_state = test_service.get_category_stats(
        start_time=start_time,
        end_time=end_time,
        include_options=include_options,
        top_title=5,
        category="",
        sub_category=""
    )
    import json
    print(json.dumps(category_state.model_dump(), indent=4, ensure_ascii=False))
