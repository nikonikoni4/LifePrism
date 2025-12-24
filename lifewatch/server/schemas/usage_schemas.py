from pydantic import BaseModel, Field

# usage饼图总览部分（今日 + 全部统计）
class UsageOverview(BaseModel):
    # 今日统计
    input_tokens: int = Field(..., description="今日输入 token 数")
    output_tokens: int = Field(..., description="今日输出 token 数")
    total_tokens: int = Field(..., description="今日总 token 数")
    input_tokens_price: float = Field(..., description="输入 token 价格每1000个token")
    output_tokens_price: float = Field(..., description="输出 token 价格每1000个token")
    total_price: float = Field(..., description="今日总价格")
    # 全部统计
    all_total_tokens: int = Field(..., description="全部总 token 数")
    all_total_price: float = Field(..., description="全部总价格")

# 数据处理tokens消耗统计（今日 + 全部统计）
class DataProcessingUsageStats(BaseModel):
    # 今日统计
    processing_items: int = Field(..., description="今日处理项目数")
    avg_processing_tokens: float = Field(..., description="今日平均处理token数")
    avg_cost: float = Field(..., description="今日平均处理token价格每1000个token")
    total_tokens: int = Field(..., description="今日总 token 数")
    total_cost: float = Field(..., description="今日总价格")
    # 全部统计
    all_total_tokens: int = Field(..., description="全部数据处理总 token 数")
    all_total_cost: float = Field(..., description="全部数据处理总价格")

# 其他消耗统计（今日 + 全部统计）
class OtherUsageStats(BaseModel):
    # 今日统计
    total_tokens: int = Field(..., description="今日其他消耗总 token 数")
    total_cost: float = Field(..., description="今日其他消耗总价格")
    # 全部统计
    all_total_tokens: int = Field(..., description="全部其他消耗总 token 数")
    all_total_cost: float = Field(..., description="全部其他消耗总价格")

# 7天柱形图统计的item
class UsageStats7DaysItem(BaseModel):
    day: str = Field(..., description="日期")
    total_cost: float = Field(..., description="总价格")
    total_tokens: int = Field(..., description="总 token 数")

# 7天柱形图统计
class UsageStats7Days(BaseModel):
    items: list[UsageStats7DaysItem] = Field(..., description="7天柱形图统计")
    
class UsageStatsResponse(BaseModel):
    usage_overview: UsageOverview = Field(..., description="使用总览")
    data_processing_usage_stats: DataProcessingUsageStats = Field(..., description="数据处理使用统计")
    other_usage_stats: OtherUsageStats = Field(..., description="其他消耗使用统计")
    usage_stats_7days: UsageStats7Days = Field(..., description="7天使用统计")
