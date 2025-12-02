from lifewatch.storage.lifewatch_data_manager import LifeWatchDataManager
from lifewatch import config
from lifewatch.data.get_activitywatch_data import get_window_events
from lifewatch.data.data_clean import clean_activitywatch_data
from lifewatch.llm.cloud_classifier import QwenAPIClassifier
# 初始化数据库管理器
db_manager = LifeWatchDataManager(db_path=config.DB_PATH)

# 获取activitywatch的数据
aw_data = get_window_events(hours=6)
# 数据清洗
app_purpose_category_df = db_manager.load_app_purpose_category()
filtered_data,app_to_classify_df,app_to_classify_set = clean_activitywatch_data(aw_data, app_purpose_category_df)
# 分类
# 获取category和sub_category的id
category = db_manager.load_categories()
sub_category = db_manager.load_sub_categories()
category_id_dict = category.set_index('name')['id'].to_dict()
sub_category_id_dict = sub_category.set_index('name')['id'].to_dict()
classifier = QwenAPIClassifier(
    api_key=config.MODEL_KEY[config.SELECT_MODEL]["api_key"],
    base_url=config.MODEL_KEY[config.SELECT_MODEL]["base_url"],
    model=config.SELECT_MODEL,
    category=", ".join(category['name'].tolist()),
    sub_category=", ".join(sub_category['name'].tolist())
)





print(app_to_classify_df)
classified_app_df = classifier.classify(app_to_classify_df)
# 保存分类
db_manager.save_app_purpose_category(classified_app_df)
# 
print("开始将分类结果赋值给filtered_events_df...")

# 创建processed_df的查找字典，提高匹配效率
processed_dict = {}
for _, row in classified_app_df.iterrows():
    app = row['app']
    title = row.get('title', '')
    is_multipurpose = row.get('is_multipurpose_app', 0)
    
    if is_multipurpose == 0:
        # 单用途应用，以app为键
        processed_dict[('single', app.lower())] = {
            'category': row.get('category'),
            'sub_category': row.get('sub_category')
        }
    else:
        # 多用途应用，以(app, title)为键
        processed_dict[('multi', app.lower(), title.lower() if title else '')] = {
            'category': row.get('category'),
            'sub_category': row.get('sub_category')
        }

# 遍历filtered_events_df进行赋值
assigned_count = 0
for index, row in filtered_data.iterrows():
    app = row['app']
    title = row.get('title', '')
    is_multipurpose = row.get('is_multipurpose_app', 0)
    
    if is_multipurpose == 0:
        # 单用途应用匹配：只匹配app
        key = ('single', app.lower())
        if key in processed_dict:
            classification = processed_dict[key]
            filtered_data.at[index, 'category'] = classification['category']
            filtered_data.at[index, 'sub_category'] = classification['sub_category']
            assigned_count += 1
            print(f"✅ 单用途应用分类成功: {app} -> {classification['category']}/{classification['sub_category']}")
    else:
        # 多用途应用匹配：匹配app和title
        key = ('multi', app.lower(), title.lower() if title else '')
        if key in processed_dict:
            classification = processed_dict[key]
            filtered_data.at[index, 'category'] = classification['category']
            filtered_data.at[index, 'sub_category'] = classification['sub_category']
            assigned_count += 1
            print(f"✅ 多用途应用分类成功: {app} - {title} -> {classification['category']}/{classification['sub_category']}")
    # 获取分类id

print(f"分类结果赋值完成！共赋值了 {assigned_count} 条记录")
print(f"filtered_data中总记录数: {len(filtered_data)}")
print(f"未分类记录数: {len(filtered_data[filtered_data['category'].isna()])}")
# 增加表中的category_id和sub_category_id
filtered_data['category_id'] = filtered_data['category'].map(category_id_dict)
filtered_data['sub_category_id'] = filtered_data['sub_category'].map(sub_category_id_dict)
# 保存到数据库

db_manager.save_user_app_behavior_log(filtered_data)




