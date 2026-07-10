# -*- coding: utf-8 -*-
"""高低模配对重命名工具 - 主模块

本插件用于自动配对并重命名高低模物体。

版本:0.2.0
兼容性:Blender 3.4+
作者:StarAsh042
许可证:MIT License
"""

bl_info = {
    "name": "高低模匹配",
    "author": "StarAsh042",
    "version": (0, 2, 0),
    "blender": (3, 4, 0),
    "location": "3D视图 > 侧边栏 > 高低模匹配",
    "description": "智能配对并重命名高低模",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

import bpy
from typing import Set


class VIEW3D_PT_PairRename(bpy.types.Panel):
    """主面板 - 高低模匹配"""

    bl_label = "高低模匹配"
    bl_idname = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_context = "objectmode"

    def draw(self, context: bpy.types.Context) -> None:
        """绘制主面板UI(仅显示标题)"""
        layout = self.layout
        layout.label(text="高低模匹配 v0.2.0")


class OBJECT_OT_PairRename(bpy.types.Operator):
    """配对重命名高低模"""

    bl_idname = "object.pair_rename"
    bl_label = "执行配对重命名"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """执行配对重命名操作"""
        self.report({'WARNING'}, "配对功能开发中,敬请期待")
        return {'CANCELLED'}


# 所有需要注册的类列表(按依赖顺序)
classes = [
    VIEW3D_PT_PairRename,
    OBJECT_OT_PairRename,
]


# 菜单项函数
def menu_func(self, context: bpy.types.Context) -> None:
    """在3D视口对象菜单中添加菜单项"""
    layout = self.layout
    layout.separator()
    layout.operator("object.pair_rename", icon='GROUP_VERTEX')


def register() -> None:
    """注册插件"""
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_object.append(menu_func)
    print("✓ 高低模匹配插件注册成功 v0.2.0")


def unregister() -> None:
    """注销插件"""
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("✓ 高低模匹配插件注销完成")
