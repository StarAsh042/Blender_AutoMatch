# -*- coding: utf-8 -*-
"""高低模配对重命名工具 - 主模块

本插件用于自动配对并重命名高低模物体,支持多种配对算法和灵活的命名配置。

主要功能:
    - 三种智能配对算法(简单/聚类/体积)
    - 自动识别高低模(基于面数)
    - 批量重命名(格式:BakePoly_001_High/Low)
    - 自动校正物体原点
    - 集合管理(移动到Baking集合)

版本:2.3.2
兼容性:Blender 3.0+
作者:StarAsh042
许可证:MIT License
"""

bl_info = {
    "name": "高低模匹配",
    "author": "StarAsh042",
    "version": (2, 3, 2),
    "blender": (3, 0, 0),
    "location": "3D视图 > 侧边栏 > 高低模匹配",
    "description": "智能配对并重命名高低模,支持多种算法和自动原点校正",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

import bpy

from .constants import __version__, __blender_min_version__

# 导入 PropertyGroup 数据模型
from .properties import PairRenameSettings

# 导入 UI 面板
from .ui import (
    VIEW3D_PT_PairRename,
    VIEW3D_PT_UsagePanel,
    VIEW3D_PT_MainActionPanel,
    VIEW3D_PT_AlgorithmPanel,
    VIEW3D_PT_CommonParamsPanel,
    VIEW3D_PT_ClusterParamsPanel,
    VIEW3D_PT_VolumeParamsPanel,
    VIEW3D_PT_NamingParamsPanel,
    VIEW3D_PT_CollectionParamsPanel,
    VIEW3D_PT_StatisticsPanel,
)

# 导入 Operators
from .operators import (
    OBJECT_OT_PairRename,
    OBJECT_OT_UnpairSelected,
    OBJECT_OT_SetPairAlgorithmSimple,
    OBJECT_OT_SetPairAlgorithmCluster,
    OBJECT_OT_SetPairAlgorithmVolume,
    OBJECT_OT_ResetPreferences,
)

# 导入核心功能
from .core import find_pairs, ObjectMetadataCache


# 所有需要注册的类列表(按依赖顺序)
classes = [
    # PropertyGroup 类(无依赖,先注册)
    PairRenameSettings,

    # 主面板(必须在子面板之前注册)
    VIEW3D_PT_PairRename,

    # 子面板(依赖主面板,按显示顺序注册)
    VIEW3D_PT_UsagePanel,
    VIEW3D_PT_MainActionPanel,
    VIEW3D_PT_AlgorithmPanel,
    VIEW3D_PT_CommonParamsPanel,
    VIEW3D_PT_ClusterParamsPanel,
    VIEW3D_PT_VolumeParamsPanel,
    VIEW3D_PT_NamingParamsPanel,
    VIEW3D_PT_CollectionParamsPanel,
    VIEW3D_PT_StatisticsPanel,

    # Operators
    OBJECT_OT_PairRename,
    OBJECT_OT_UnpairSelected,
    OBJECT_OT_SetPairAlgorithmSimple,
    OBJECT_OT_SetPairAlgorithmCluster,
    OBJECT_OT_SetPairAlgorithmVolume,
    OBJECT_OT_ResetPreferences,
]


# 公开类和函数(用于外部访问)
__all__ = [
    '__version__',
    '__blender_min_version__',
    'register',
    'unregister',
    'find_pairs',
    'ObjectMetadataCache',
]


def register() -> None:
    """注册插件

    注册所有必要的类、属性和菜单项
    """
    print("=" * 60)
    print(f"开始注册高低模配对重命名插件 v{__version__}...")
    print("=" * 60)

    # 注册所有类
    registered_classes = []
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            registered_classes.append(cls)
        except Exception as e:
            print(f"✗ 注册类 {cls.__name__} 失败: {e}")
            # 回滚已注册的类
            for registered_cls in reversed(registered_classes):
                try:
                    bpy.utils.unregister_class(registered_cls)
                except Exception:
                    pass
            return

    print(f"✓ 已注册 {len(classes)} 个类")

    # 添加 Scene 属性
    bpy.types.Scene.pair_rename_tool = bpy.props.PointerProperty(
        type=PairRenameSettings
    )
    print("✓ Scene属性注册成功")

    # 添加到菜单
    try:
        bpy.types.VIEW3D_MT_object.append(menu_func)
        print("✓ 菜单项添加成功")
    except Exception as e:
        print(f"✗ 菜单添加失败: {e}")

    print("=" * 60)
    print(f"✓ 插件注册成功!版本: {__version__}")
    print("=" * 60)
    print()


def unregister() -> None:
    """注销插件

    清理所有注册的类、属性和菜单项
    """
    print("=" * 60)
    print("开始注销插件...")
    print("=" * 60)

    # 从菜单中移除
    try:
        bpy.types.VIEW3D_MT_object.remove(menu_func)
        print("✓ 菜单项移除成功")
    except Exception as e:
        print(f"✗ 菜单移除失败: {e}")

    # 删除 Scene 属性
    if hasattr(bpy.types.Scene, 'pair_rename_tool'):
        del bpy.types.Scene.pair_rename_tool
        print("✓ Scene属性注销成功")

    # 反向注销所有类
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"✗ 注销类 {cls.__name__} 失败: {e}")

    print(f"✓ 已注销 {len(classes)} 个类")

    print("=" * 60)
    print("✓ 插件注销完成")
    print("=" * 60)
    print()


# 菜单项函数
def menu_func(self, context: bpy.types.Context) -> None:
    """在3D视口对象菜单中添加菜单项

    Args:
        self: 菜单对象
        context: Blender上下文
    """
    layout = self.layout
    layout.separator()
    layout.operator("object.pair_rename", icon='GROUP_VERTEX')


# ========== 命令行执行支持 ==========
if __name__ == "__main__":
    """当直接运行此文件时执行注册"""
    try:
        unregister()
    except Exception as e:
        print(f"注销旧实例时出错: {e}")

    register()
