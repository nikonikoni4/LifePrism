"""
setting界面的schemas
"""

from pydantic import BaseModel, Field

 

class SettingItems(BaseModel):
    # 名称
    user_name : str |None = Field(description="用户名称")
    # API
    api_key : str |None = Field(default="API_KEY") # 不可读
    provider : str |None = Field(description="provider") 
    model : str |None = Field(description="模型选择")
    input_tokens_cost : float |None = Field(description="输入token单价 /1k")
    output_tokens_cost : float |None = Field(description="输出token单价 /1k")
    # classification mode
    classification_mode : str = Field(description="分类模式")
    long_log_threshold : int = Field(description="长时长阈值")
    # 多用途/浏览器应用名称列表
    multi_purpose_app_names : List[str]= Field(description="多用途/浏览器应用名称列表")
    # db
    aw_db_path : str = Field(description="activity watch db来源路径")
    lw_db_path : str = Field(description="life watch db保存路径")
    chat_db_path : str = Field(description="chat db保存路径")
    # 数据清洗时长阈值
    data_cleaning_threshold : int = Field(description="数据清洗时长阈值")


