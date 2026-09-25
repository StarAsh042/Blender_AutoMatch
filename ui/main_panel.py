# -*- coding: utf-8 -*-
"""
主面板UI模块

主面板作为容器,仅显示状态信息。
所有功能内容由子面板承载。
"""

import bpy


class VIEW3D_PT_PairRename(bpy.types.Panel):
    """主面板 - 高低模匹配"""

    bl_label = "高低模匹配"
    bl_idname = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_context = "objectmode"

    def draw(self, context: bpy.types.Context) -> None:
        """绘制主面板UI(仅显示状态信息)

        Args:
            context: Blender上下文
        """
        layout = self.layout
        settings = context.scene.pair_rename_tool

        # 显示最后操作状态(如果有)
        if settings.last_operation:
            row = layout.row()
            row.alignment = 'LEFT'
            row.label(text=settings.last_operation, icon='INFO')
