
from bokeh.core.validation.decorators import warning
from pydantic import BaseModel,Field
from typing import Annotated
import operator

def remain_old_value(old_value,new_value):
    if old_value:
        return old_value
    else:
        return new_value



class LogItem(BaseModel):
    # 基础数据
    id: int
    app: str
    duration: int = Field(description="时长,单位秒") # 时长
    title: str | None
    title_analysis: str | None = None  # 搜索分析结果，初始为None
    # 分类结果
    category: str | None = Field(default=None, description="存储分类结果") # 存储分类结果
    sub_category: str | None = Field(default=None, description="存储分类结果") # 存储分类结果
    link_to_goal: str | None = Field(default=None, description="与goal相关联") # 与goal相关联

class Goal(BaseModel):
    goal: str = Field(description="用户的目标") # 用户的目标
    category: str = Field(description="用户的目标绑定的分类, Goal必须有第一个类别") # 用户的目标绑定的分类, Goal必须有第一个类别
    sub_category: str | None = Field(description="用户的目标绑定的子分类") # 用户的目标绑定的子分类

class AppInFo(BaseModel):
    description : str = Field(description="app的描述")
    is_multipurpose : bool = Field(description="是否为被选择需要使用title信息来判断用途的应用")
    titles : list[str] | None = Field(default=None, description="该app的典型标题示例列表，用于辅助识别app用途")
# 定义状态


# def update_logitem(item_list:list[LogItem],update_data)->list[LogItem]:
#     """
#     更新LogItem 或 替换
#     args:
#         item_list : 原数据
#         update_data : 更新数据 {
#                         "update_flag": str,
#                         "update_date": 
#                         }
#     return:
#         list[LogItem]
#     """
#     # 获取更新类型
#     if isinstance(update_data,dict):
#         update_flag = update_data.get("update_flag",None)
#         if update_flag == "title_analysis":
#             update_data = update_data.get("update_data",None)
#             if isinstance(update_data,dict): # id:title_analysis
#                 for log_item in item_list:
#                     if log_item.id in update_data:
#                         log_item.title_analysis = update_data[log_item.id]
#         return item_list # 返回完整列表，只更新 title_analysis 字段
#     elif update_data:
#         return update_data # 直接替换
#     else:
#         return item_list

def test_add(item_list:list[LogItem],update_data:list[LogItem])->list[LogItem]:
    # print(f"test_add : {update_data}")
    if item_list and update_data:
        return item_list+ update_data
    elif item_list:
        return item_list
    elif update_data:
        return update_data
    return None

class classifyState(BaseModel):
    app_registry: dict[str, AppInFo]= Field(description="app : app_description") # app : app_description
    log_items: Annotated[list[LogItem],remain_old_value] = Field(description="原始分类数据") # 分类数据，不使用 reducer
    result_items: Annotated[list[LogItem] | None, test_add] = Field(default=None, description="输出结果") # 不更新log_items

class classifyStateLogitems(BaseModel):
    private_app_registry: dict[str, AppInFo]= Field(description="app : app_description") # app : app_description
    log_items_for_single: list[LogItem] | None = Field(default=None, description="单用途分类数据")
    log_items_for_multi: list[LogItem] | None = Field(default=None, description="多用途分类数据")
    log_items_for_multi_short: list[LogItem] | None = Field(default=None, description="多用途短时长分类数据")
    log_items_for_multi_long: list[LogItem] | None = Field(default=None, description="多用途长时长分类数据")