"""
功能描述: 分类入口模块
date : 2025.12.17
"""
from lifeprism.llm.classify.classify_graph import ClassifyGraph
from lifeprism.llm.classify.classify_simple import ClassifySimple
import logging

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
            logger.warning("classify_mode: %s 无效，必须为 %s 中的一项", classify_mode, available)
            return None
        
        classifier_class = CLASSIFIER_REGISTRY[classify_mode]
        return classifier_class(goal=self.goal, category_tree=self.category_tree)
    
    async def classify(self, state):
        """执行分类"""
        if self.classifier is None:
            logger.error("分类器未初始化")
            return None
        return await self.classifier.classify(state)

