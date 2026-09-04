# -*- coding: utf-8 -*-
"""
算法选择面板模块
"""

import bpy

from ..constants import (
    ALGORITHM_SIMPLE,
    ALGORITHM_CLUSTER,
    ALGORITHM_VOLUME,
)
from ..operators import OBJECT_OT_ResetPreferences


class VIEW3D_PT_AlgorithmPanel(bpy.types.Panel):
    """算法选择子面板"""

    bl_label = "算法选择"
    bl_idname = "VIEW3D_PT_algorithm_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"

    def draw(self, context: bpy.types.Context) -> None:
        """绘制算法选择区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        # 预设选择(按钮样式)
        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.5

        # 简单算法按钮
        is_simple = settings.pair_algorithm == ALGORITHM_SIMPLE
        row.operator("object.set_pair_algorithm_simple",
                    text="简单",
                    depress=is_simple,
                    icon='RADIOBUT_ON' if is_simple else 'RADIOBUT_OFF')

        # 聚类算法按钮
        is_cluster = settings.pair_algorithm == ALGORITHM_CLUSTER
        row.operator("object.set_pair_algorithm_cluster",
                    text="聚类",
                    depress=is_cluster,
                    icon='RADIOBUT_ON' if is_cluster else 'RADIOBUT_OFF')

        # 体积算法按钮
        row = col.row(align=True)
        row.scale_y = 1.5
        is_volume = settings.pair_algorithm == ALGORITHM_VOLUME
        row.operator("object.set_pair_algorithm_volume",
                    text="体积",
                    depress=is_volume,
                    icon='RADIOBUT_ON' if is_volume else 'RADIOBUT_OFF')

        # 算法说明
        layout.separator(factor=0.5)
        col = layout.column(align=True)

        if settings.pair_algorithm == ALGORITHM_SIMPLE:
            col.label(text="适用:物体分布均匀、数量较少", icon='INFO')
        elif settings.pair_algorithm == ALGORITHM_CLUSTER:
            col.label(text="适用:物体有聚类特征(多角色)", icon='INFO')
        elif settings.pair_algorithm == ALGORITHM_VOLUME:
            col.label(text="适用:需考虑体积相似度的场景", icon='INFO')

        # 重置按钮
        layout.separator(factor=0.5)
        row = layout.row(align=True)
        row.operator(OBJECT_OT_ResetPreferences.bl_idname,
                    text="重置算法参数",
                    icon='LOOP_BACK')
