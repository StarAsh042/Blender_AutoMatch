# -*- coding: utf-8 -*-
"""
配对操作符模块

包含主要的配对和撤销操作符
"""

import bpy
import time
from typing import List, Tuple, Dict, Set

from ..utils import (
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
from ..core import find_pairs
from ..constants import (
    ERROR_MESSAGES,
    BAKING_COLLECTION_NAME,
)


class OBJECT_OT_PairRename(bpy.types.Operator):
    """配对重命名高低模"""

    bl_idname = "object.pair_rename"
    bl_label = "执行配对重命名"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """执行配对重命名操作

        完整的配对重命名流程：
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

        # 基础验证：是否有选中物体
        if not selected_objects:
            settings.last_operation = "未选中任何物体"
            self.report({'WARNING'}, "请先选中要处理的物体")
            return {'CANCELLED'}

        # 验证：是否为网格物体
        mesh_objects = filter_mesh_objects(selected_objects)
        if not mesh_objects:
            non_mesh_count = len(selected_objects) - len(mesh_objects)
            settings.last_operation = f"选中的{len(selected_objects)}个物体中没有网格类型"
            self.report(
                {'WARNING'},
                f"{ERROR_MESSAGES['no_mesh_objects']} (选中了{non_mesh_count}个非网格物体)"
            )
            return {'CANCELLED'}

        # 验证：网格物体数量是否足够
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
