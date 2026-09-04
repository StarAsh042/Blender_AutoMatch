# -*- coding: utf-8 -*-
"""
操作符模块

包含所有操作符的定义,按功能分类
"""

from .pair_ops import (
    OBJECT_OT_PairRename,
    OBJECT_OT_UnpairSelected,
)
from .algorithm_ops import (
    OBJECT_OT_SetPairAlgorithmSimple,
    OBJECT_OT_SetPairAlgorithmCluster,
    OBJECT_OT_SetPairAlgorithmVolume,
)
from .settings_ops import OBJECT_OT_ResetPreferences

__all__ = [
    'OBJECT_OT_PairRename',
    'OBJECT_OT_UnpairSelected',
    'OBJECT_OT_SetPairAlgorithmSimple',
    'OBJECT_OT_SetPairAlgorithmCluster',
    'OBJECT_OT_SetPairAlgorithmVolume',
    'OBJECT_OT_ResetPreferences',
]
