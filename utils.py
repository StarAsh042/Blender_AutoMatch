# -*- coding: utf-8 -*-
"""工具函数模块

提供辅助函数,用于配对算法、UI面板和操作符
"""

import bpy
from mathutils import Vector
import re
import contextlib
from typing import List, Tuple, Optional, TYPE_CHECKING

from .constants import (
    BAKING_COLLECTION_NAME,
    HIGH_POLY_SUFFIX,
    LOW_POLY_SUFFIX,
    DEFAULT_PAIRING_PREFIX,
    DEFAULT_PREFIX_DIGITS,
    ERROR_MESSAGES
)

if TYPE_CHECKING:
    from .core.cache import ObjectMetadataCache


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


def calculate_bbox_volume(
    obj: bpy.types.Object,
    cache: Optional['ObjectMetadataCache'] = None
) -> float:
    """计算包围盒体积

    Args:
        obj: Blender物体对象
        cache: 可选的元数据缓存,传入时直接复用缓存结果

    Returns:
        包围盒体积
    """
    if cache is not None:
        return cache.get_volume(obj)

    size = get_bbox_size(obj)
    return size.x * size.y * size.z


def calculate_distance(
    obj1: bpy.types.Object,
    obj2: bpy.types.Object,
    cache: Optional['ObjectMetadataCache'] = None
) -> float:
    """计算两个物体之间的距离

    Args:
        obj1: 第一个物体
        obj2: 第二个物体
        cache: 可选的元数据缓存

    Returns:
        两物体中心点之间的距离
    """
    if cache:
        center1 = cache.get_center(obj1)
        center2 = cache.get_center(obj2)
    else:
        center1 = get_object_bbox_center(obj1)
        center2 = get_object_bbox_center(obj2)

    return (center1 - center2).length


# ========== 原点处理函数 ==========
@contextlib.contextmanager
def _selection_guard(objects: List[bpy.types.Object]):
    """临时接管选中状态与交互模式,退出时恢复

    使用数据API恢复选中状态,避免 bpy.ops 的 poll 失败影响后续操作
    """
    view_layer = bpy.context.view_layer
    previous_selection = list(bpy.context.selected_objects)
    previous_active = view_layer.objects.active
    previous_mode = previous_active.mode if previous_active else 'OBJECT'

    try:
        if previous_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        for obj in previous_selection:
            obj.select_set(False)
        for obj in objects:
            obj.select_set(True)
        view_layer.objects.active = objects[0]

        yield
    finally:
        for obj in objects:
            obj.select_set(False)
        for obj in previous_selection:
            obj.select_set(True)
        view_layer.objects.active = previous_active

        if previous_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode=previous_mode)


def fix_origin_to_bbox_center(obj: bpy.types.Object) -> Tuple[bool, str]:
    """将物体的原点设置到包围盒中心

    Args:
        obj: Blender物体对象

    Returns:
        Tuple[bool, str]: (是否成功, 错误信息/成功信息)
    """
    if obj.type != 'MESH':
        return False, f"物体类型不是MESH: {obj.name}"

    try:
        with _selection_guard([obj]):
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        return True, "原点设置成功"
    except Exception as e:
        return False, ERROR_MESSAGES["origin_fix_failed"].format(error=str(e))


def process_origins_to_bbox_center(objects: List[bpy.types.Object]) -> int:
    """批量处理所有物体的原点

    一次性选中全部物体后执行单次 origin_set,避免逐物体调用操作符的开销

    Args:
        objects: Blender物体列表

    Returns:
        成功设置的物体数量
    """
    mesh_objects = [obj for obj in objects if obj.type == 'MESH']
    if not mesh_objects:
        return 0

    with _selection_guard(mesh_objects):
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

    return len(mesh_objects)


# ========== 高低模识别函数 ==========
def identify_high_low(obj1: bpy.types.Object, obj2: bpy.types.Object) -> Tuple[bpy.types.Object, bpy.types.Object]:
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
