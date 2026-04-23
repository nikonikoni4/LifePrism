# 展示前需要做的

1. 调用llm按照小时合并语义，但是要保留原始的数据
2. 需要确认截图分析的时间点
3. 确认数据结构
4. 确认显示位置

## llm语义合并

问题：1. 应该是让llm自行判断一天的语义应该分配在什么地方，还是规定每隔多少小时？
应该按天输入，输入一天的数据，数据量应该不大，最多不过1000字，现在的模型应该能够应付。
结果：输入一天的全部分析数据，然后让llm对时间段进行主动分开，颗粒度是15min，
能够分割单情况1. 不是连续的数据桶 2. 两个数据桶之间所做的事情没有什么相同点
如果是 数据桶A：做事情A，并且做事情B，而数据桶B，做事情B呢？，应该合并。采取比较严格的分割判断标准
宁愿合并也不愿意拆开

## 截图分析启动方式
(这里边界条件未确认，比如说today - screenshot_retention_days +1 还是 today -screenshot_retention_days，这个要依据实际的截图保存具体是怎么计算的来确认边界)
1. 增量启动
    1. 判断上一次启动日期（依据数据库数据），若没有数据last_analysis_day = today -1 
    2. 判断上一次启动日期距离今天的时间是否大于截图最小保存时间
       today -  last_analysis_day  > screenshot_retention_days:
            yes -> start_date = today - screenshot_retention_days
            no -> start_date = last_analysis_day

2. 主动启动(用于重新生成)
    1. 范围：today - screenshot_retention_days 
    2. 选择日期确定start_date和start_end

## 数据结构

1. screen_analysis

start_time str
end_time str
behavior str
screenshot_count int # 这段时间都截图数量
create_at timestamp
update_at timestamp

2. behavior_summary 
start_time str
end_time str
behavior_summary
create_at timestamp

确认是否真的需要两个数据表

## 显示位置

1. 当前timeline的显示主区域是 (时间刻度)| （custom_block）| (timeline主体) | （点击之后显示的补充说明区域）
2. 我的想法，本质上ai判断的 behavior和custom_block是一个含义，都是记录当下做了什么，不过custom_block更直接。而且我想采用custom_block的方式显示。我的想法是减小timeline主体的宽度，留下一部分区域用来显示behavior
(时间刻度)| （custom_block）| (timeline主体) | [新增]behavior|（点击之后显示的补充说明区域）

具体显示

|timeline主体|  | HH-MM ~ HH-MM : xxxx | (点击behavior后在右侧，显示这段时间都具体内容)
|timeline主体|  |
|timeline主体|


最右侧显示内容：

---------
behavior的全部信息
---------

---------
每个数据桶的分点信息
HH-MM~ HH-MM
1. xxx
2. xxx
...
--------