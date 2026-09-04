# -*- coding: utf-8 -*-
"""
通用参数面板模块
"""

import bpy

from ..constants import (
    ALGORITHM_CLUSTER,
    ALGORITHM_VOLUME,
)


class VIEW3D_PT_CommonParamsPanel(bpy.types.Panel):
    """通用参数子面板"""

    bl_label = "通用参数"
    bl_idname = "VIEW3D_PT_common_params_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: bpy.types.Context) -> None:
        """绘制通用参数区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False

        col.prop(settings, "pair_fix_origins", text="自动设置原点到包围盒中心")
        col.prop(settings, "pair_max_distance", text="最大配对距离")
        col.prop(settings, "pair_min_ratio", text="面数比例阈值")
