"""
功能描述: 分类入口模块
date : 2025.12.17
"""
from lifewatch.llm.llm_classify.classify.classify_graph import ClassifyGraph
from lifewatch.llm.llm_classify.classify.classify_simple import ClassifySimple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 分类器名称到类的映射
CLASSIFIER_REGISTRY = {
    "classify_graph": ClassifyGraph,
    "classify_simple": ClassifySimple,
}


class LLMClassify:
    def __init__(self, classify_mode: str, goal: list, category_tree: dict):
        """
        初始化分类器
        
        Args:
            classify_mode: 分类器模式，"classify_graph" 或 "classify_simple"
            goal: 用户目标列表
            category_tree: 分类树字典
        """
        self.goal = goal
        self.category_tree = category_tree
        self.classifier = self._create_classifier(classify_mode)
    
    def _create_classifier(self, classify_mode: str):
        """根据名称创建分类器实例"""
        if classify_mode not in CLASSIFIER_REGISTRY:
            available = list(CLASSIFIER_REGISTRY.keys())
            logger.warning(f"classify_mode: {classify_mode} 无效，必须为 {available} 中的一项")
            return None
        
        classifier_class = CLASSIFIER_REGISTRY[classify_mode]
        return classifier_class(goal=self.goal, category_tree=self.category_tree)
    
    def classify(self, state):
        """执行分类"""
        if self.classifier is None:
            logger.error("分类器未初始化")
            return None
        return self.classifier.classify(state)


if __name__ == "__main__":
    from lifewatch.llm.llm_classify.classify.data_loader import (
        get_real_data,
        filter_by_duration,
        deduplicate_log_items
    )
    
    # 获取数据
    state, goals, category_tree = get_real_data(hours=18)
    state = filter_by_duration(state, min_duration=60)
    state = deduplicate_log_items(state)
    
    # 使用 classify_simple 模式
    llm_classify = LLMClassify(
        classify_mode="classify_graph",
        goal=goals,
        category_tree=category_tree
    )
    
    output = llm_classify.classify(state)
    
    if output and output.get("result_items"):
        result_items = output["result_items"]
        print("\n" + "="*80)
        print("📝 分类结果")
        print("="*80)
        print(f"  共 {len(result_items)} 条记录")
        print("-"*80)
        for item in result_items:
            goal_str = f"🎯 {item.link_to_goal}" if item.link_to_goal else ""
            category_str = f"{item.category or '未分类'}/{item.sub_category or '-'}"
            print(f"  [{item.id}] {item.app:<15} | {category_str:<20} | {item.duration:>5}s | {goal_str}")
        print("="*80)