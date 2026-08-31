# -*- coding: utf-8 -*-
"""高低模配对重命名工具 - 主模块

本插件用于自动配对并重命名高低模物体,支持多种配对算法和灵活的命名配置。

主要功能:
    - 三种智能配对算法(简单/聚类/体积)
    - 自动识别高低模(基于面数)
    - 批量重命名(格式:BakePoly_001_High/Low)
    - 自动校正物体原点
    - 集合管理(移动到Baking集合)

版本:1.1.0
兼容性:Blender 3.4+
作者:StarAsh042
许可证:MIT License
"""

bl_info = {
    "name": "高低模匹配",
    "author": "StarAsh042",
    "version": (1, 1, 0),
    "blender": (3, 4, 0),
    "location": "3D视图 > 侧边栏 > 高低模匹配",
    "description": "智能配对并重命名高低模,支持多种算法和自动原点校正",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

import bpy
import time
from typing import List, Tuple, Set

from .constants import (
    __version__,
    __blender_min_version__,
    ALGORITHM_SIMPLE,
    ALGORITHM_CLUSTER,
    ALGORITHM_VOLUME,
    ALGORITHM_DISPLAY_NAMES,
    ALGORITHM_DESCRIPTIONS,
    DEFAULT_MAX_DISTANCE,
    DEFAULT_MIN_RATIO,
    DEFAULT_CLUSTER_RADIUS,
    DEFAULT_VOLUME_MIN_RATIO,
    DEFAULT_VOLUME_MAX_RATIO,
    DEFAULT_PAIRING_PREFIX,
    DEFAULT_PREFIX_DIGITS,
    BAKING_COLLECTION_NAME,
    ERROR_MESSAGES,
)

# 导入核心功能
from .core import find_pairs, ObjectMetadataCache

# 导入工具函数(操作符与面板仍内联于本文件,拆包过渡期显式导入)
from .utils import (
    get_face_count,
    identify_high_low,
    generate_prefixes,
    generate_pair_names,
    create_or_get_baking_collection,
    move_objects_to_collection,
    process_origins_to_bbox_center,
    filter_mesh_objects,
    filter_mesh_objects_with_faces,
    get_max_number_in_baking_collection,
)


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

    pair_fix_origins: bpy.props.BoolProperty(
        name="自动设置原点",
        description="先自动设置物体的原点到包围盒中心(推荐开启)",
        default=True
    )

    # ===== 聚类算法参数 =====
    pair_cluster_radius: bpy.props.FloatProperty(
        name="聚类半径",
        description="聚类算法的半径参数(仅聚类算法有效)",
        default=DEFAULT_CLUSTER_RADIUS,
        min=0.1,
        max=50.0,
        step=0.5,
        subtype='DISTANCE'
    )

    # ===== 体积算法参数 =====
    pair_volume_min_ratio: bpy.props.FloatProperty(
        name="最小体积比",
        description="体积算法的最小体积比例(仅体积算法有效)",
        default=DEFAULT_VOLUME_MIN_RATIO,
        min=0.1,
        max=5.0,
        step=0.1
    )

    pair_volume_max_ratio: bpy.props.FloatProperty(
        name="最大体积比",
        description="体积算法的最大体积比例(仅体积算法有效)",
        default=DEFAULT_VOLUME_MAX_RATIO,
        min=0.5,
        max=10.0,
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

    # ===== 集合管理 =====
    pair_manage_collection: bpy.props.BoolProperty(
        name="管理集合",
        description="将配对好的物体移动到Baking集合(推荐开启)",
        default=True
    )

    # ===== UI折叠状态 =====
    show_common_params: bpy.props.BoolProperty(
        name="显示通用参数",
        description="展开/收起通用参数面板",
        default=True
    )

    show_cluster_params: bpy.props.BoolProperty(
        name="显示聚类参数",
        description="展开/收起聚类参数面板",
        default=True
    )

    show_volume_params: bpy.props.BoolProperty(
        name="显示体积参数",
        description="展开/收起体积参数面板",
        default=True
    )

    show_naming_params: bpy.props.BoolProperty(
        name="显示命名参数",
        description="展开/收起命名参数面板",
        default=True
    )

    show_collection_params: bpy.props.BoolProperty(
        name="显示集合参数",
        description="展开/收起集合参数面板",
        default=True
    )

    # ===== 状态信息 =====
    last_operation: bpy.props.StringProperty(
        name="最后操作",
        description="最后一次操作的状态信息",
        default=""
    )


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


class VIEW3D_PT_AlgorithmPanel(bpy.types.Panel):
    """算法选择子面板"""

    bl_label = "算法选择"
    bl_idname = "VIEW3D_PT_algorithm_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"

    def draw(self, context: bpy.types.Context) -> None:
        """绘制算法选择区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        # 预设选择(按钮样式)
        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.5

        # 简单算法按钮
        is_simple = settings.pair_algorithm == ALGORITHM_SIMPLE
        row.operator("object.set_pair_algorithm_simple",
                    text="简单",
                    depress=is_simple,
                    icon='RADIOBUT_ON' if is_simple else 'RADIOBUT_OFF')

        # 聚类算法按钮
        is_cluster = settings.pair_algorithm == ALGORITHM_CLUSTER
        row.operator("object.set_pair_algorithm_cluster",
                    text="聚类",
                    depress=is_cluster,
                    icon='RADIOBUT_ON' if is_cluster else 'RADIOBUT_OFF')

        # 体积算法按钮
        row = col.row(align=True)
        row.scale_y = 1.5
        is_volume = settings.pair_algorithm == ALGORITHM_VOLUME
        row.operator("object.set_pair_algorithm_volume",
                    text="体积",
                    depress=is_volume,
                    icon='RADIOBUT_ON' if is_volume else 'RADIOBUT_OFF')

        # 算法说明
        layout.separator(factor=0.5)
        col = layout.column(align=True)

        if settings.pair_algorithm == ALGORITHM_SIMPLE:
            col.label(text="适用:物体分布均匀、数量较少", icon='INFO')
        elif settings.pair_algorithm == ALGORITHM_CLUSTER:
            col.label(text="适用:物体有聚类特征(多角色)", icon='INFO')
        elif settings.pair_algorithm == ALGORITHM_VOLUME:
            col.label(text="适用:需考虑体积相似度的场景", icon='INFO')

        # 重置按钮
        layout.separator(factor=0.5)
        row = layout.row(align=True)
        row.operator(OBJECT_OT_ResetPreferences.bl_idname,
                    text="重置算法参数",
                    icon='LOOP_BACK')


class VIEW3D_PT_CommonParamsPanel(bpy.types.Panel):
    """通用参数子面板"""

    bl_label = "通用参数"
    bl_idname = "VIEW3D_PT_common_params_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: bpy.types.Context) -> None:
        """绘制通用参数区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False

        col.prop(settings, "pair_fix_origins", text="自动设置原点到包围盒中心")
        col.prop(settings, "pair_max_distance", text="最大配对距离")
        col.prop(settings, "pair_min_ratio", text="面数比例阈值")


class VIEW3D_PT_ClusterParamsPanel(bpy.types.Panel):
    """聚类算法参数子面板"""

    bl_label = "聚类算法参数"
    bl_idname = "VIEW3D_PT_cluster_params_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        """仅在聚类算法被选中时显示"""
        return context.scene.pair_rename_tool.pair_algorithm == ALGORITHM_CLUSTER

    def draw(self, context: bpy.types.Context) -> None:
        """绘制聚类算法参数区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(settings, "pair_cluster_radius", text="聚类半径")


class VIEW3D_PT_VolumeParamsPanel(bpy.types.Panel):
    """体积算法参数子面板"""

    bl_label = "体积算法参数"
    bl_idname = "VIEW3D_PT_volume_params_panel"
    bl_parent_id = "VIEW3D_PT_pair_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "高低模匹配"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        """仅在体积算法被选中时显示"""
        return context.scene.pair_rename_tool.pair_algorithm == ALGORITHM_VOLUME

    def draw(self, context: bpy.types.Context) -> None:
        """绘制体积算法参数区域"""
        layout = self.layout
        settings = context.scene.pair_rename_tool

        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(settings, "pair_volume_min_ratio", text="最小体积比")
        col.prop(settings, "pair_volume_max_ratio", text="最大体积比")


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


class OBJECT_OT_PairRename(bpy.types.Operator):
    """配对重命名高低模"""

    bl_idname = "object.pair_rename"
    bl_label = "执行配对重命名"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """执行配对重命名操作

        完整的配对重命名流程:
        1. 验证选中物体
        2. 自动设置原点(可选)
        3. 执行配对算法
        4. 生成命名前缀
        5. 重命名物体
        6. 管理集合(可选)
        7. 生成结果报告

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

        # 自动设置原点(在配对前执行,保证距离计算基于校正后的状态)
        if settings.pair_fix_origins:
            try:
                success_count = process_origins_to_bbox_center(mesh_objects)
                if success_count > 0:
                    msg = ERROR_MESSAGES["origin_fix_success"].format(count=success_count)
                    self.report({'INFO'}, msg)
            except Exception as e:
                self.report(
                    {'WARNING'},
                    f"设置原点时发生非关键错误: {str(e)}，配对结果不受影响"
                )

        # 执行配对算法
        try:
            pairs = find_pairs(
                algorithm=settings.pair_algorithm,
                objects=mesh_objects,
                max_distance=settings.pair_max_distance,
                min_ratio=settings.pair_min_ratio,
                cluster_radius=settings.pair_cluster_radius,
                volume_ratio_range=(settings.pair_volume_min_ratio,
                                    settings.pair_volume_max_ratio),
                use_cache=True
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

        # 创建或获取Baking集合
        baking_collection = None
        if settings.pair_manage_collection:
            baking_collection = create_or_get_baking_collection()

            # 收集所有配对的物体
            paired_objects = []
            for obj1, obj2, _ in pairs:
                paired_objects.append(obj1)
                paired_objects.append(obj2)

            # 移动到Baking集合
            move_objects_to_collection(paired_objects, baking_collection)

        processing_time = time.time() - start_time
        report_message = (
            f"成功配对 {len(pairs)} 对,重命名 {renamed_count} 个物体,"
            f"耗时 {processing_time:.2f}秒"
        )
        if baking_collection:
            report_message += f",物体已移动到 {BAKING_COLLECTION_NAME} 集合"
        self.report({'INFO'}, report_message)
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

            # 保存原始名称到自定义属性(用于撤销功能)
            # 如果已经存在original_name(说明已经配对过),保留最初的原始名称
            if 'original_name' not in high_obj:
                high_obj['original_name'] = high_obj.name
            if 'original_name' not in low_obj:
                low_obj['original_name'] = low_obj.name
            high_obj['pairing_prefix'] = prefix_str
            low_obj['pairing_prefix'] = prefix_str

            high_obj.name = high_name
            low_obj.name = low_name
            count += 2

        return count


class OBJECT_OT_UnpairSelected(bpy.types.Operator):
    """撤销选中物体的配对命名"""

    bl_idname = "object.unpair_selected"
    bl_label = "撤销配对"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """撤销选中物体的配对命名,恢复原始名称

        从物体的自定义属性中读取 original_name,恢复原始名称,
        并清理配对相关的自定义属性

        Returns:
            {'FINISHED'} 或 {'CANCELLED'}
        """
        selected_objects = context.selected_objects

        if not selected_objects:
            self.report({'WARNING'}, "请先选择要撤销配对的物体")
            return {'CANCELLED'}

        restored_count = 0
        for obj in selected_objects:
            # 检查是否有原始名称记录
            if 'original_name' not in obj:
                continue

            original_name = obj['original_name']

            # 检查名称是否已被其他物体占用
            holder = bpy.data.objects.get(original_name)
            if holder is not None:
                self.report(
                    {'WARNING'},
                    f"无法恢复 '{obj.name}' 的名称为 '{original_name}': 名称已被占用"
                )
                continue

            # 恢复原始名称
            obj.name = original_name

            # 清理自定义属性
            if 'original_name' in obj:
                del obj['original_name']
            if 'pairing_prefix' in obj:
                del obj['pairing_prefix']

            restored_count += 1

        # 生成报告
        if restored_count > 0:
            self.report(
                {'INFO'},
                f"成功恢复 {restored_count} 个物体的原始名称"
            )
        else:
            self.report({'WARNING'}, "未找到可撤销的物体")
            return {'CANCELLED'}

        context.scene.pair_rename_tool.last_operation = (
            f"撤销配对: 恢复 {restored_count} 个"
        )
        return {'FINISHED'}


class OBJECT_OT_SetPairAlgorithm(bpy.types.Operator):
    """设置配对算法基类"""

    bl_idname = "object.set_pair_algorithm"
    bl_label = "设置配对算法"
    bl_options = {'REGISTER'}

    algorithm = ''

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """设置配对算法"""
        context.scene.pair_rename_tool.pair_algorithm = self.algorithm
        context.scene.pair_rename_tool.last_operation = f"已切换到 {self.algorithm} 算法"
        return {'FINISHED'}


class OBJECT_OT_SetPairAlgorithmSimple(OBJECT_OT_SetPairAlgorithm):
    """设置为简单算法"""

    bl_idname = "object.set_pair_algorithm_simple"
    bl_label = "简单算法"

    algorithm = ALGORITHM_SIMPLE


class OBJECT_OT_SetPairAlgorithmCluster(OBJECT_OT_SetPairAlgorithm):
    """设置为聚类算法"""

    bl_idname = "object.set_pair_algorithm_cluster"
    bl_label = "聚类算法"

    algorithm = ALGORITHM_CLUSTER


class OBJECT_OT_SetPairAlgorithmVolume(OBJECT_OT_SetPairAlgorithm):
    """设置为体积算法"""

    bl_idname = "object.set_pair_algorithm_volume"
    bl_label = "体积算法"

    algorithm = ALGORITHM_VOLUME


class OBJECT_OT_ResetPreferences(bpy.types.Operator):
    """重置插件参数到默认值"""

    bl_idname = "object.pair_rename_reset"
    bl_label = "重置参数"
    bl_options = {'REGISTER'}

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """重置参数到默认值"""
        settings = context.scene.pair_rename_tool

        settings.pair_algorithm = ALGORITHM_SIMPLE
        settings.pair_max_distance = DEFAULT_MAX_DISTANCE
        settings.pair_min_ratio = DEFAULT_MIN_RATIO
        settings.pair_fix_origins = True
        settings.pair_cluster_radius = DEFAULT_CLUSTER_RADIUS
        settings.pair_volume_min_ratio = DEFAULT_VOLUME_MIN_RATIO
        settings.pair_volume_max_ratio = DEFAULT_VOLUME_MAX_RATIO
        settings.pair_prefix = DEFAULT_PAIRING_PREFIX
        settings.pair_digits = DEFAULT_PREFIX_DIGITS
        settings.pair_manage_collection = True

        settings.last_operation = "参数已重置为默认值"
        self.report({'INFO'}, "参数已重置为默认值")
        return {'FINISHED'}
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


# 菜单项函数
def menu_func(self, context: bpy.types.Context) -> None:
    """在3D视口对象菜单中添加菜单项"""
    layout = self.layout
    layout.separator()
    layout.operator("object.pair_rename", icon='GROUP_VERTEX')


def register() -> None:
    """注册插件

    注册所有必要的类、属性和菜单项
    """
    print("=" * 60)
    print(f"开始注册高低模配对重命名插件 v{__version__}...")
    print("=" * 60)

    # 注册所有类
    for cls in classes:
        bpy.utils.register_class(cls)
    print(f"✓ 已注册 {len(classes)} 个类")

    # 添加 Scene 属性
    bpy.types.Scene.pair_rename_tool = bpy.props.PointerProperty(
        type=PairRenameSettings
    )
    print("✓ Scene属性注册成功")

    # 添加到菜单
    bpy.types.VIEW3D_MT_object.append(menu_func)
    print("✓ 菜单项添加成功")

    print(f"✓ 插件注册成功!版本: {__version__}")


def unregister() -> None:
    """注销插件

    清理所有注册的类、属性和菜单项
    """
    print("=" * 60)
    print("开始注销插件...")
    print("=" * 60)

    # 从菜单中移除
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    print("✓ 菜单项移除成功")

    # 删除 Scene 属性
    if hasattr(bpy.types.Scene, 'pair_rename_tool'):
        del bpy.types.Scene.pair_rename_tool
        print("✓ Scene属性注销成功")

    # 反向注销所有类
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print(f"✓ 已注销 {len(classes)} 个类")

    print("=" * 60)
    print("✓ 插件注销完成")
    print("=" * 60)
    print()


# ========== 命令行执行支持 ==========
if __name__ == "__main__":
    """当直接运行此文件时执行注册"""
    try:
        unregister()
    except Exception as e:
        print(f"注销旧实例时出错: {e}")

    register()
