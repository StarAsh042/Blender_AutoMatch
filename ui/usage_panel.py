# -*- coding: utf-8 -*-
"""
使用说明面板模块
"""

import bpy


class VIEW3D_PT_UsagePanel(bpy.types.Panel):
    """使用说明子面板"""

    bl_label = "使用说明"
    bl_idname = "VIEW3D_PT_usage_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: bpy.types.Context) -> None:
        """绘制使用说明区域"""
        layout = self.layout

        col = layout.column(align=True)
        col.label(text="1. 选中要处理的网格物体", icon='DOT')
        col.label(text="2. 选择算法(默认简单模式)", icon='DOT')
        col.label(text="3. 点击执行配对", icon='DOT')
