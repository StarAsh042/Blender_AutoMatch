# -*- coding: utf-8 -*-
"""
体积算法参数面板模块
"""

import bpy

from ..constants import ALGORITHM_VOLUME


class VIEW3D_PT_VolumeParamsPanel(bpy.types.Panel):
    """体积算法参数子面板"""

    bl_label = "体积算法参数"
    bl_idname = "VIEW3D_PT_volume_params_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        """仅在体积算法被选中时显示"""
        return context.scene.pair_rename_tool.pair_algorithm == ALGORITHM_VOLUME

    def draw(self, context: bpy.types.Context) -> None:
        """绘制体积算法参数区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(settings, "pair_volume_min_ratio", text="最小体积比")
        col.prop(settings, "pair_volume_max_ratio", text="最大体积比")
