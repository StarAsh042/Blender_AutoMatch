# -*- coding: utf-8 -*-
"""
算法设置操作符模块

包含切换配对算法的操作符
"""

import bpy
from typing import Set
from ..constants import (
    ALGORITHM_SIMPLE,
    ALGORITHM_CLUSTER,
    ALGORITHM_VOLUME,
)


class OBJECT_OT_SetPairAlgorithm(bpy.types.Operator):
    """设置配对算法基类"""

    bl_idname = "object.set_pair_algorithm"
    bl_label = "设置配对算法"
    bl_options = {'REGISTER'}

    algorithm = ''

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """设置配对算法"""
        context.scene.pair_rename_tool.pair_algorithm = self.algorithm
        context.scene.pair_rename_tool.last_operation = f"已切换到 {self.algorithm} 算法"
        return {'FINISHED'}


class OBJECT_OT_SetPairAlgorithmSimple(OBJECT_OT_SetPairAlgorithm):
    """设置为简单算法"""

    bl_idname = "object.set_pair_algorithm_simple"
    bl_label = "简单算法"

    algorithm = ALGORITHM_SIMPLE


class OBJECT_OT_SetPairAlgorithmCluster(OBJECT_OT_SetPairAlgorithm):
    """设置为聚类算法"""

    bl_idname = "object.set_pair_algorithm_cluster"
    bl_label = "聚类算法"

    algorithm = ALGORITHM_CLUSTER


class OBJECT_OT_SetPairAlgorithmVolume(OBJECT_OT_SetPairAlgorithm):
    """设置为体积算法"""

    bl_idname = "object.set_pair_algorithm_volume"
    bl_label = "体积算法"

    algorithm = ALGORITHM_VOLUME
