# -*- coding: utf-8 -*-
"""
统计信息面板模块
"""

import bpy

from ..utils import get_face_count, get_max_number_in_baking_collection


class VIEW3D_PT_StatisticsPanel(bpy.types.Panel):
    """统计信息子面板"""

    bl_label = "统计信息"
    bl_idname = "VIEW3D_PT_statistics_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: bpy.types.Context) -> None:
        """绘制统计信息区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        # 选中物体统计
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        selected_count = len(selected_objects)

        col = layout.column(align=True)
        col.label(text="选中物体统计", icon='USER')

        col = layout.column(align=True)
        col.label(text=f"选中的网格物体: {selected_count}个")

        if selected_count > 0:
            face_counts = [get_face_count(obj) for obj in selected_objects]
            max_faces = max(face_counts) if face_counts else 0
            min_faces = min(face_counts) if face_counts else 0
            avg_faces = sum(face_counts) / len(face_counts) if face_counts else 0

            col.label(text=f"最大面数: {max_faces}")
            col.label(text=f"最小面数: {min_faces}")
            col.label(text=f"平均面数: {int(avg_faces)}")

        # Baking集合信息
        layout.separator(factor=0.5)
        col = layout.column(align=True)
        col.label(text="Baking集合信息", icon='GROUP')

        col = layout.column(align=True)
        baking_max_number = get_max_number_in_baking_collection(
            settings.pair_prefix,
            settings.pair_digits
        )
        col.label(text=f"当前最大序号: {baking_max_number}")
        col.label(text=f"下次起始序号: {baking_max_number + 1}")
