# -*- coding: utf-8 -*-
"""
聚类算法参数面板模块
"""

import bpy

from ..constants import ALGORITHM_CLUSTER


class VIEW3D_PT_ClusterParamsPanel(bpy.types.Panel):
    """聚类算法参数子面板"""

    bl_label = "聚类算法参数"
    bl_idname = "VIEW3D_PT_cluster_params_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        """仅在聚类算法被选中时显示"""
        return context.scene.pair_rename_tool.pair_algorithm == ALGORITHM_CLUSTER

    def draw(self, context: bpy.types.Context) -> None:
        """绘制聚类算法参数区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(settings, "pair_cluster_radius", text="聚类半径")
