# -*- coding: utf-8 -*-
"""高低模配对重命名工具 - 主模块

本插件用于自动配对并重命名高低模物体,支持多种配对算法和灵活的命名配置。

主要功能:
    - 基于距离和面数的简单配对算法
    - 批量重命名(格式:BakePoly_001_High/Low)

版本:0.4.0
兼容性:Blender 3.4+
作者:StarAsh042
许可证:MIT License
"""

bl_info = {
    "name": "高低模匹配",
    "author": "StarAsh042",
    "version": (0, 4, 0),
    "blender": (3, 4, 0),
    "location": "3D视图 > 侧边栏 > 高低模匹配",
    "description": "智能配对并重命名高低模,支持多种算法和自动原点校正",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

import bpy
from mathutils import Vector
import re
import time
from typing import Dict, List, Tuple, Optional, Set


# ========== 默认配置 ==========
DEFAULT_PAIRING_PREFIX = "BakePoly_"
DEFAULT_PREFIX_DIGITS = 3
DEFAULT_MAX_DISTANCE = 5.0
DEFAULT_MIN_RATIO = 0.0

# ========== 集合名称 ==========
BAKING_COLLECTION_NAME = "Baking"

# ========== 后缀标记 ==========
HIGH_POLY_SUFFIX = "High"
LOW_POLY_SUFFIX = "Low"

# ========== 算法枚举 ==========
ALGORITHM_SIMPLE = "SIMPLE"
ALGORITHM_CLUSTER = "CLUSTER"
ALGORITHM_VOLUME = "VOLUME"

ALGORITHM_DISPLAY_NAMES = {
    ALGORITHM_SIMPLE: "简单算法",
    ALGORITHM_CLUSTER: "聚类算法",
    ALGORITHM_VOLUME: "体积算法"
}

ALGORITHM_DESCRIPTIONS = {
    ALGORITHM_SIMPLE: "基于距离和面数的简单算法",
    ALGORITHM_CLUSTER: "先聚类再配对的算法",
    ALGORITHM_VOLUME: "考虑体积相似度的算法"
}

# ========== 错误消息 ==========
ERROR_MESSAGES = {
    "no_mesh_objects": "请先选中要处理的网格物体",
    "insufficient_objects": "需要至少选中2个网格物体",
    "no_pairs_found": "没有找到合适的配对。请尝试调整参数或更换算法。",
}


# ========== 插件设置 ==========
class PairRenameSettings(bpy.types.PropertyGroup):
    """
    插件设置 - 存储插件的所有配置参数

    分类:
        - 算法设置: 配对算法选择和参数
        - 通用参数: 通用配置选项
        - 命名设置: 命名相关参数
        - 状态信息: 显示操作状态
    """

    # ===== 算法选择 =====
    pair_algorithm: bpy.props.EnumProperty(
        name="配对算法",
        description="选择配对算法",
        items=[
            (ALGORITHM_SIMPLE,
             ALGORITHM_DISPLAY_NAMES[ALGORITHM_SIMPLE],
             ALGORITHM_DESCRIPTIONS[ALGORITHM_SIMPLE]),
            (ALGORITHM_CLUSTER,
             ALGORITHM_DISPLAY_NAMES[ALGORITHM_CLUSTER],
             ALGORITHM_DESCRIPTIONS[ALGORITHM_CLUSTER]),
            (ALGORITHM_VOLUME,
             ALGORITHM_DISPLAY_NAMES[ALGORITHM_VOLUME],
             ALGORITHM_DESCRIPTIONS[ALGORITHM_VOLUME]),
        ],
        default=ALGORITHM_SIMPLE
    )

    # ===== 通用参数 =====
    pair_max_distance: bpy.props.FloatProperty(
        name="最大距离",
        description="配对的最大距离限制(世界坐标单位)",
        default=DEFAULT_MAX_DISTANCE,
        min=0.1,
        max=100.0,
        step=0.5,
        subtype='DISTANCE'
    )

    pair_min_ratio: bpy.props.FloatProperty(
        name="最小比例",
        description="高模与低模的最小面数比例(0表示不限制)",
        default=DEFAULT_MIN_RATIO,
        min=0.0,
        max=100.0,
        step=0.1
    )

    # ===== 命名设置 =====
    pair_prefix: bpy.props.StringProperty(
        name="前缀",
        description="命名的前缀部分,例如 'BakePoly_'",
        default=DEFAULT_PAIRING_PREFIX
    )

    pair_digits: bpy.props.IntProperty(
        name="数字位数",
        description="序号数字的位数,例如3表示 '001'",
        default=DEFAULT_PREFIX_DIGITS,
        min=1,
        max=6
    )

    # ===== 状态信息 =====
    last_operation: bpy.props.StringProperty(
        name="最后操作",
        description="最后一次操作的状态信息",
        default=""
    )


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
    """获取物体的包围盒中心(AABB中心)"""
    if obj.type != 'MESH':
        return Vector(obj.location)

    min_co, max_co = get_world_bbox(obj)
    return (min_co + max_co) * 0.5


def get_bbox_size(obj: bpy.types.Object) -> Vector:
    """获取包围盒尺寸"""
    if obj.type != 'MESH':
        return Vector((0.0, 0.0, 0.0))

    min_co, max_co = get_world_bbox(obj)
    return max_co - min_co


def calculate_distance(
    obj1: bpy.types.Object,
    obj2: bpy.types.Object
) -> float:
    """计算两个物体之间的距离(包围盒中心点间)"""
    center1 = get_object_bbox_center(obj1)
    center2 = get_object_bbox_center(obj2)
    return (center1 - center2).length


# ========== 高低模识别函数 ==========
def identify_high_low(obj1: bpy.types.Object,
                      obj2: bpy.types.Object) -> Tuple[bpy.types.Object, bpy.types.Object]:
    """识别高模和低模(面数多者为高模)"""
    faces1 = get_face_count(obj1)
    faces2 = get_face_count(obj2)

    if faces1 >= faces2:
        return obj1, obj2
    else:
        return obj2, obj1


# ========== 命名生成函数 ==========
def get_baking_collection() -> Optional[bpy.types.Collection]:
    """获取Baking集合,不存在时返回None"""
    return bpy.data.collections.get(BAKING_COLLECTION_NAME)


def get_max_number_in_baking_collection(
    prefix: str = DEFAULT_PAIRING_PREFIX,
    digits: int = DEFAULT_PREFIX_DIGITS
) -> int:
    """获取Baking集合中已使用的最大序号"""
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
    """生成指定起始序号的连续前缀列表"""
    return [f"{prefix}{start_number + i:0{digits}d}" for i in range(count)]


def generate_pair_names(prefix: str) -> Tuple[str, str]:
    """根据前缀生成高低模的名称"""
    high_name = f"{prefix}_{HIGH_POLY_SUFFIX}"
    low_name = f"{prefix}_{LOW_POLY_SUFFIX}"
    return high_name, low_name


# ========== 集合管理函数 ==========
def create_or_get_baking_collection() -> bpy.types.Collection:
    """创建或获取Baking集合"""
    baking_collection = get_baking_collection()
    if baking_collection is not None:
        return baking_collection

    baking_collection = bpy.data.collections.new(BAKING_COLLECTION_NAME)
    bpy.context.scene.collection.children.link(baking_collection)
    return baking_collection


def move_objects_to_collection(objects: List[bpy.types.Object],
                                collection: bpy.types.Collection) -> None:
    """将物体移动到指定集合"""
    for obj in objects:
        for coll in obj.users_collection:
            coll.objects.unlink(obj)
        collection.objects.link(obj)


# ========== 物体过滤函数 ==========
def filter_mesh_objects(objects: List[bpy.types.Object]) -> List[bpy.types.Object]:
    """过滤出网格类型的物体"""
    return [obj for obj in objects if obj.type == 'MESH']


def filter_mesh_objects_with_faces(objects: List[bpy.types.Object]) -> List[bpy.types.Object]:
    """过滤出有面的网格物体"""
    return [obj for obj in objects if obj.type == 'MESH' and get_face_count(obj) > 0]


# ========== 配对算法 ==========
def _collect_face_counts(objects: List[bpy.types.Object]) -> Dict[bpy.types.Object, int]:
    """一次性统计所有物体的面数

    避免在 O(n^2) 的配对循环中反复查询 polygon 数量
    """
    return {obj: get_face_count(obj) for obj in objects}


def find_pairs(
    algorithm: str,
    objects: List[bpy.types.Object],
    max_distance: float = 5.0,
    min_ratio: float = 0.0
) -> List[Tuple[bpy.types.Object, bpy.types.Object, float]]:
    """根据指定算法查找高低模配对

    Args:
        algorithm: 算法类型
        objects: 要配对的物体列表
        max_distance: 最大配对距离
        min_ratio: 高模与低模的最小面数比例(0表示不限制)

    Returns:
        配对列表,每项为 (高模对象, 低模对象, 距离评分)

    Raises:
        ValueError: 当算法类型不支持或参数无效时
        TypeError: 当objects不是列表或包含非物体对象时
    """
    # 参数验证
    if not isinstance(objects, list):
        raise TypeError("objects 必须是列表类型")

    if not all(isinstance(obj, bpy.types.Object) for obj in objects):
        raise TypeError("objects 列表必须包含 Blender 物体对象")

    if not isinstance(algorithm, str):
        raise TypeError("algorithm 必须是字符串类型")

    if max_distance <= 0:
        raise ValueError(f"max_distance 必须为正数, 当前值: {max_distance}")

    if min_ratio < 0:
        raise ValueError(f"min_ratio 不能为负数, 当前值: {min_ratio}")

    if len(objects) < 2:
        return []

    # 根据算法类型调用相应的实现
    try:
        if algorithm == ALGORITHM_SIMPLE:
            return find_pairs_by_distance_and_faces(
                objects, max_distance, min_ratio
            )
        else:
            raise ValueError(f"不支持的算法类型: {algorithm}")
    except Exception as e:
        # 捕获并包装底层异常，提供更清晰的错误信息
        raise RuntimeError(f"配对算法执行失败: {str(e)}") from e


def find_pairs_by_distance_and_faces(
    objects: List[bpy.types.Object],
    max_distance: float = 5.0,
    min_ratio: float = 0.0
) -> List[Tuple[bpy.types.Object, bpy.types.Object, float]]:
    """算法1:基于距离和面数的简单配对

    适用于物体分布均匀、数量较少的场景

    Args:
        objects: 要配对的物体列表
        max_distance: 最大配对距离阈值
        min_ratio: 高模与低模的最小面数比例(0表示不限制)

    Returns:
        配对列表,每项为 (高模对象, 低模对象, 距离评分)
    """
    if len(objects) < 2:
        return []

    face_counts = _collect_face_counts(objects)

    # 按面数降序,保证每个物体只与面数不多于自己的物体配对
    sorted_objects = sorted(objects, key=face_counts.__getitem__, reverse=True)
    pairs = []
    used_objects = set()

    # 遍历所有物体进行配对
    for i, obj1 in enumerate(sorted_objects):
        if obj1 in used_objects:
            continue

        faces1 = face_counts[obj1]
        best_match = None
        best_distance = float('inf')

        # 寻找最近的未使用物体
        for j in range(i + 1, len(sorted_objects)):
            obj2 = sorted_objects[j]
            if obj2 in used_objects:
                continue

            faces2 = face_counts[obj2]
            if faces2 <= 0:
                continue

            # 检查面数比例
            if min_ratio > 0 and faces1 / faces2 < min_ratio:
                continue

            # 计算距离并检查阈值
            distance = calculate_distance(obj1, obj2)
            if distance > max_distance:
                continue

            if distance < best_distance:
                best_match = obj2
                best_distance = distance

        if best_match is not None:
            pairs.append((obj1, best_match, best_distance))
            used_objects.add(obj1)
            used_objects.add(best_match)

    return pairs


class VIEW3D_PT_PairRename(bpy.types.Panel):
    """主面板 - 高低模匹配"""

    bl_label = "高低模匹配"
    bl_idname = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_context = "objectmode"

    def draw(self, context: bpy.types.Context) -> None:
        """绘制主面板UI(仅显示状态信息)"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        # 显示最后操作状态(如果有)
        if settings.last_operation:
            row = layout.row()
            row.alignment = 'LEFT'
            row.label(text=settings.last_operation, icon='INFO')


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


class OBJECT_OT_PairRename(bpy.types.Operator):
    """配对重命名高低模"""

    bl_idname = "object.pair_rename"
    bl_label = "执行配对重命名"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """执行配对重命名操作

        完整的配对重命名流程:
        1. 验证选中物体
        2. 执行配对算法
        3. 生成命名前缀
        4. 重命名物体
        5. 生成结果报告

        Returns:
            {'FINISHED'} 或 {'CANCELLED'}
        """
        start_time = time.time()
        scene = context.scene
        settings = scene.pair_rename_tool

        # 验证选中物体
        selected_objects = context.selected_objects

        # 基础验证:是否有选中物体
        if not selected_objects:
            settings.last_operation = "未选中任何物体"
            self.report({'WARNING'}, "请先选中要处理的物体")
            return {'CANCELLED'}

        # 验证:是否为网格物体
        mesh_objects = filter_mesh_objects(selected_objects)
        if not mesh_objects:
            non_mesh_count = len(selected_objects) - len(mesh_objects)
            settings.last_operation = f"选中的{len(selected_objects)}个物体中没有网格类型"
            self.report(
                {'WARNING'},
                f"{ERROR_MESSAGES['no_mesh_objects']} (选中了{non_mesh_count}个非网格物体)"
            )
            return {'CANCELLED'}

        # 验证:网格物体数量是否足够
        if len(mesh_objects) < 2:
            settings.last_operation = f"仅选中{len(mesh_objects)}个网格物体，需要至少2个"
            self.report(
                {'WARNING'},
                ERROR_MESSAGES["insufficient_objects"] + f" (当前: {len(mesh_objects)}个)"
            )
            return {'CANCELLED'}

        # 过滤有面的物体并验证
        mesh_objects = filter_mesh_objects_with_faces(mesh_objects)
        if len(mesh_objects) < 2:
            settings.last_operation = f"有效网格物体不足(有{len(mesh_objects)}个有面的物体)"
            self.report(
                {'WARNING'},
                f"需要至少2个有面的网格物体 (当前有效: {len(mesh_objects)}个)"
            )
            return {'CANCELLED'}

        # 执行配对算法
        try:
            pairs = find_pairs(
                algorithm=settings.pair_algorithm,
                objects=mesh_objects,
                max_distance=settings.pair_max_distance,
                min_ratio=settings.pair_min_ratio,
            )
        except ValueError as e:
            # 参数验证错误
            settings.last_operation = f"参数错误: {str(e)}"
            self.report({'ERROR'}, f"参数验证失败: {str(e)}")
            return {'CANCELLED'}
        except RuntimeError as e:
            # 算法执行错误
            settings.last_operation = f"算法执行失败: {str(e)}"
            self.report({'ERROR'}, f"配对算法执行失败: {str(e)}")
            return {'CANCELLED'}
        except Exception as e:
            # 未知错误
            settings.last_operation = f"未知错误: {str(e)}"
            self.report({'ERROR'}, f"发生未知错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        if not pairs:
            settings.last_operation = "未找到任何配对"
            self.report({'WARNING'}, ERROR_MESSAGES["no_pairs_found"])
            return {'CANCELLED'}

        # 从Baking集合的最大序号开始生成前缀
        max_number = get_max_number_in_baking_collection(
            settings.pair_prefix, settings.pair_digits)
        prefixes = generate_prefixes(
            settings.pair_prefix,
            settings.pair_digits,
            max_number + 1,
            len(pairs)
        )

        # 重命名物体
        renamed_count = self._rename_pairs(pairs, prefixes)

        processing_time = time.time() - start_time
        self.report(
            {'INFO'},
            f"成功配对 {len(pairs)} 对,重命名 {renamed_count} 个物体,"
            f"耗时 {processing_time:.2f}秒"
        )
        settings.last_operation = (
            f"成功配对 {len(pairs)} 对 ({renamed_count}个物体), "
            f"耗时 {processing_time:.2f}s"
        )
        return {'FINISHED'}

    def _rename_pairs(
        self,
        pairs: List[Tuple[bpy.types.Object, bpy.types.Object, float]],
        prefixes: List[str]
    ) -> int:
        """执行重命名操作

        Args:
            pairs: 配对列表
            prefixes: 前缀列表

        Returns:
            重命名物体数量
        """
        count = 0
        for idx, (obj1, obj2, score) in enumerate(pairs):
            high_obj, low_obj = identify_high_low(obj1, obj2)
            prefix_str = prefixes[idx]
            high_name, low_name = generate_pair_names(prefix_str)

            high_obj.name = high_name
            low_obj.name = low_name
            count += 2

        return count


# 所有需要注册的类列表(按依赖顺序)
classes = [
    # PropertyGroup 类(无依赖,先注册)
    PairRenameSettings,

    # 主面板(必须在子面板之前注册)
    VIEW3D_PT_PairRename,

    # 子面板(依赖主面板)
    VIEW3D_PT_MainActionPanel,

    # Operators
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
    bpy.types.Scene.pair_rename_tool = bpy.props.PointerProperty(
        type=PairRenameSettings
    )
    bpy.types.VIEW3D_MT_object.append(menu_func)
    print("✓ 高低模匹配插件注册成功 v0.4.0")


def unregister() -> None:
    """注销插件"""
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    if hasattr(bpy.types.Scene, 'pair_rename_tool'):
        del bpy.types.Scene.pair_rename_tool
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("✓ 高低模匹配插件注销完成")


# ========== 命令行执行支持 ==========
if __name__ == "__main__":
    """当直接运行此文件时执行注册"""
    try:
        unregister()
    except Exception as e:
        print(f"注销旧实例时出错: {e}")

    register()
