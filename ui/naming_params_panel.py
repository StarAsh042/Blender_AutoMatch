# -*- coding: utf-8 -*-
"""
命名设置面板模块
"""

import bpy


class VIEW3D_PT_NamingParamsPanel(bpy.types.Panel):
    """命名设置子面板"""

    bl_label = "命名设置"
    bl_idname = "VIEW3D_PT_naming_params_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: bpy.types.Context) -> None:
        """绘制命名设置区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False

        col.prop(settings, "pair_prefix", text="前缀")
        col.prop(settings, "pair_digits", text="数字位数")
