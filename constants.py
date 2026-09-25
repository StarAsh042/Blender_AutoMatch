# -*- coding: utf-8 -*-
"""常量定义模块"""

# ========== 版本信息 ==========
__version__ = "2.3.1"
__blender_min_version__ = (3, 0, 0)

# ========== 默认配置 ==========
DEFAULT_PAIRING_PREFIX = "BakePoly_"
DEFAULT_PREFIX_DIGITS = 3
DEFAULT_MAX_DISTANCE = 5.0
DEFAULT_MIN_RATIO = 0.0
DEFAULT_CLUSTER_RADIUS = 5.0
DEFAULT_VOLUME_MIN_RATIO = 0.5
DEFAULT_VOLUME_MAX_RATIO = 2.0

# ========== 算法枚举 ==========
ALGORITHM_SIMPLE = "SIMPLE"
ALGORITHM_CLUSTER = "CLUSTER"
ALGORITHM_VOLUME = "VOLUME"

ALGORITHM_DISPLAY_NAMES = {
    ALGORITHM_SIMPLE: "简单算法",
    ALGORITHM_CLUSTER: "聚类算法",
    ALGORITHM_VOLUME: "体积算法"
}

ALGORITHM_DESCRIPTIONS = {
    ALGORITHM_SIMPLE: "基于距离和面数的简单算法",
    ALGORITHM_CLUSTER: "先聚类再配对的算法",
    ALGORITHM_VOLUME: "考虑体积相似度的算法"
}

# ========== 集合名称 ==========
BAKING_COLLECTION_NAME = "Baking"

# ========== 后缀标记 ==========
HIGH_POLY_SUFFIX = "High"
LOW_POLY_SUFFIX = "Low"

# ========== 体积评分权重 ==========
VOLUME_SCORE_WEIGHT = 5.0

# ========== 错误消息 ==========
ERROR_MESSAGES = {
    "no_mesh_objects": "请先选中要处理的网格物体",
    "insufficient_objects": "需要至少选中2个网格物体",
    "no_pairs_found": "没有找到合适的配对。请尝试调整参数或更换算法。",
    "name_exists": "重命名失败，以下名称已被占用：",
    "origin_fix_failed": "设置原点失败: {error}",
    "origin_fix_success": "已为{count}个物体设置原点到包围盒中心"
}

# ========== 成功消息 ==========
SUCCESS_MESSAGES = {
    "processing_complete": "处理完成！耗时: {time:.2f}秒",
    "pairs_created": "成功配对: {count}对，重命名: {renamed}个物体",
    "objects_moved": "物体已移动到 '{collection}' 集合"
}
