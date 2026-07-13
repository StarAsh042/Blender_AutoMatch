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
from mathutils import Vector
import re
from typing import List, Tuple, Optional, Set


# ========== 默认配置 ==========
DEFAULT_PAIRING_PREFIX = "BakePoly_"
DEFAULT_PREFIX_DIGITS = 3

# ========== 集合名称 ==========
BAKING_COLLECTION_NAME = "Baking"

# ========== 后缀标记 ==========
HIGH_POLY_SUFFIX = "High"
LOW_POLY_SUFFIX = "Low"


# ========== 基础几何函数 ==========
def get_face_count(obj: bpy.types.Object) -> int:
    """获取物体的面数

    Args:
        obj: Blender物体对象

    Returns:
        面数,非网格或无数据时返回0
    """
    if obj.type != 'MESH' or obj.data is None:
        return 0
    return len(obj.data.polygons)


def get_world_bbox(obj: bpy.types.Object) -> Tuple[Vector, Vector]:
    """计算物体世界坐标下的AABB最小/最大顶点

    Args:
        obj: Blender物体对象

    Returns:
        Tuple[最小顶点, 最大顶点],非网格物体返回原点
    """
    if obj.type != 'MESH':
        return Vector(obj.location), Vector(obj.location)

    min_co = Vector((float('inf'), float('inf'), float('inf')))
    max_co = Vector((-float('inf'), -float('inf'), -float('inf')))

    for corner in obj.bound_box:
        world_corner = obj.matrix_world @ Vector(corner)
        for i in range(3):
            if world_corner[i] < min_co[i]:
                min_co[i] = world_corner[i]
            if world_corner[i] > max_co[i]:
                max_co[i] = world_corner[i]

    return min_co, max_co


def get_object_bbox_center(obj: bpy.types.Object) -> Vector:
    """获取物体的包围盒中心(AABB中心)

    Args:
        obj: Blender物体对象

    Returns:
        包围盒中心的3D坐标向量
    """
    if obj.type != 'MESH':
        return Vector(obj.location)

    min_co, max_co = get_world_bbox(obj)
    return (min_co + max_co) * 0.5


def get_bbox_size(obj: bpy.types.Object) -> Vector:
    """获取包围盒尺寸

    Args:
        obj: Blender物体对象

    Returns:
        包围盒尺寸向量 (x, y, z)
    """
    if obj.type != 'MESH':
        return Vector((0.0, 0.0, 0.0))

    min_co, max_co = get_world_bbox(obj)
    return max_co - min_co


def calculate_distance(
    obj1: bpy.types.Object,
    obj2: bpy.types.Object
) -> float:
    """计算两个物体之间的距离

    Args:
        obj1: 第一个物体
        obj2: 第二个物体

    Returns:
        两物体包围盒中心点之间的距离
    """
    center1 = get_object_bbox_center(obj1)
    center2 = get_object_bbox_center(obj2)
    return (center1 - center2).length


# ========== 高低模识别函数 ==========
def identify_high_low(obj1: bpy.types.Object,
                      obj2: bpy.types.Object) -> Tuple[bpy.types.Object, bpy.types.Object]:
    """识别高模和低模

    Args:
        obj1: 第一个物体
        obj2: 第二个物体

    Returns:
        Tuple[高模对象, 低模对象]
    """
    faces1 = get_face_count(obj1)
    faces2 = get_face_count(obj2)

    if faces1 >= faces2:
        return obj1, obj2
    else:
        return obj2, obj1


# ========== 命名生成函数 ==========
def get_baking_collection() -> Optional[bpy.types.Collection]:
    """获取Baking集合

    Returns:
        Baking集合对象,不存在时返回None
    """
    return bpy.data.collections.get(BAKING_COLLECTION_NAME)


def get_max_number_in_baking_collection(
    prefix: str = DEFAULT_PAIRING_PREFIX,
    digits: int = DEFAULT_PREFIX_DIGITS
) -> int:
    """获取Baking集合中已使用的最大序号

    Args:
        prefix: 命名前缀,默认为"BakePoly_"
        digits: 序号数字位数,默认为3

    Returns:
        最大序号,不存在返回0
    """
    baking_collection = get_baking_collection()
    if baking_collection is None:
        return 0

    pattern = re.compile(rf"^{re.escape(prefix)}(\d{{{digits}}})_({HIGH_POLY_SUFFIX}|{LOW_POLY_SUFFIX})$")

    numbers = [
        int(match.group(1))
        for match in (pattern.match(obj.name) for obj in baking_collection.objects)
        if match
    ]
    return max(numbers, default=0)


def generate_prefixes(prefix: str, digits: int, start_number: int, count: int) -> List[str]:
    """生成指定起始序号的连续前缀列表

    Args:
        prefix: 命名前缀
        digits: 序号数字位数
        start_number: 起始序号
        count: 需要生成的数量

    Returns:
        前缀字符串列表
    """
    return [f"{prefix}{start_number + i:0{digits}d}" for i in range(count)]


def generate_pair_names(prefix: str) -> Tuple[str, str]:
    """根据前缀生成高低模的名称

    Args:
        prefix: 前缀字符串

    Returns:
        Tuple[高模名称, 低模名称]
    """
    high_name = f"{prefix}_{HIGH_POLY_SUFFIX}"
    low_name = f"{prefix}_{LOW_POLY_SUFFIX}"
    return high_name, low_name


# ========== 集合管理函数 ==========
def create_or_get_baking_collection() -> bpy.types.Collection:
    """创建或获取Baking集合

    Returns:
        Baking集合对象
    """
    baking_collection = get_baking_collection()
    if baking_collection is not None:
        return baking_collection

    baking_collection = bpy.data.collections.new(BAKING_COLLECTION_NAME)
    bpy.context.scene.collection.children.link(baking_collection)
    return baking_collection


def move_objects_to_collection(objects: List[bpy.types.Object],
                                collection: bpy.types.Collection) -> None:
    """将物体移动到指定集合

    Args:
        objects: 要移动的物体列表
        collection: 目标集合
    """
    for obj in objects:
        for coll in obj.users_collection:
            coll.objects.unlink(obj)
        collection.objects.link(obj)


# ========== 物体过滤函数 ==========
def filter_mesh_objects(objects: List[bpy.types.Object]) -> List[bpy.types.Object]:
    """过滤出网格类型的物体

    Args:
        objects: 物体列表

    Returns:
        网格类型的物体列表
    """
    return [obj for obj in objects if obj.type == 'MESH']


def filter_mesh_objects_with_faces(objects: List[bpy.types.Object]) -> List[bpy.types.Object]:
    """过滤出有面的网格物体

    Args:
        objects: 物体列表

    Returns:
        有面的网格物体列表
    """
    return [obj for obj in objects if obj.type == 'MESH' and get_face_count(obj) > 0]


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
