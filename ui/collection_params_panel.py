# -*- coding: utf-8 -*-
"""
集合管理面板模块
"""

import bpy

from ..constants import BAKING_COLLECTION_NAME


class VIEW3D_PT_CollectionParamsPanel(bpy.types.Panel):
    """集合管理子面板"""

    bl_label = "集合管理"
    bl_idname = "VIEW3D_PT_collection_params_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: bpy.types.Context) -> None:
        """绘制集合管理区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False

        col.prop(settings, "pair_manage_collection", text="自动移动到Baking集合")

        # 显示Baking集合状态
        layout.separator(factor=0.5)
        if BAKING_COLLECTION_NAME in bpy.data.collections:
            obj_count = len(bpy.data.collections[BAKING_COLLECTION_NAME].objects)
            col.label(text=f"✓ Baking集合已存在 ({obj_count}个物体)", icon='CHECKMARK')
        else:
            col.label(text="⊗ Baking集合不存在(将自动创建)", icon='CANCEL')
