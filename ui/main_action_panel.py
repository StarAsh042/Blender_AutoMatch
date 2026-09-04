# -*- coding: utf-8 -*-
"""
主要操作面板模块
"""

import bpy

from ..operators import OBJECT_OT_PairRename, OBJECT_OT_UnpairSelected


class VIEW3D_PT_MainActionPanel(bpy.types.Panel):
    """主要操作子面板"""

    bl_label = "主要操作"
    bl_idname = "VIEW3D_PT_main_action_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"

    def draw(self, context: bpy.types.Context) -> None:
        """绘制主要操作区域"""
        layout = self.layout
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        selected_count = len(selected_objects)

        # 选中物体状态
        col = layout.column(align=True)
        row = col.row(align=True)
        row.alignment = 'CENTER'
        if selected_count >= 2:
            row.label(text=f"已选中 {selected_count} 个网格物体", icon='CHECKMARK')
        else:
            row.label(text=f"请选中至少2个网格物体", icon='ERROR')

        # 主执行按钮
        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 2.0
        row.enabled = selected_count >= 2
        row.operator(OBJECT_OT_PairRename.bl_idname,
                     text="执行配对重命名",
                     icon='FILE_REFRESH')

        # 撤销按钮
        row = col.row(align=True)
        row.operator(OBJECT_OT_UnpairSelected.bl_idname,
                    text="撤销配对",
                    icon='CANCEL')
