# -*- coding: utf-8 -*-
"""
设置操作符模块

包含重置设置等操作符
"""

import bpy
from typing import Set

from ..constants import (
    DEFAULT_MAX_DISTANCE,
    DEFAULT_MIN_RATIO,
    DEFAULT_CLUSTER_RADIUS,
    DEFAULT_VOLUME_MIN_RATIO,
    DEFAULT_VOLUME_MAX_RATIO,
    DEFAULT_PAIRING_PREFIX,
    DEFAULT_PREFIX_DIGITS,
    ALGORITHM_SIMPLE,
)


class OBJECT_OT_ResetPreferences(bpy.types.Operator):
    """重置插件参数到默认值"""

    bl_idname = "object.pair_rename_reset"
    bl_label = "重置参数"
    bl_options = {'REGISTER'}

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """重置参数到默认值"""
        settings = context.scene.pair_rename_tool

        settings.pair_algorithm = ALGORITHM_SIMPLE
        settings.pair_max_distance = DEFAULT_MAX_DISTANCE
        settings.pair_min_ratio = DEFAULT_MIN_RATIO
        settings.pair_fix_origins = True
        settings.pair_cluster_radius = DEFAULT_CLUSTER_RADIUS
        settings.pair_volume_min_ratio = DEFAULT_VOLUME_MIN_RATIO
        settings.pair_volume_max_ratio = DEFAULT_VOLUME_MAX_RATIO
        settings.pair_prefix = DEFAULT_PAIRING_PREFIX
        settings.pair_digits = DEFAULT_PREFIX_DIGITS
        settings.pair_manage_collection = True

        settings.last_operation = "参数已重置为默认值"
        self.report({'INFO'}, "参数已重置为默认值")
        return {'FINISHED'}
