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
    SUCCESS_MESSAGES,
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

        # 执行配对算法
        try:
            pairs = find_pairs(
                algorithm=settings.pair_algorithm,
                objects=mesh_objects,
                max_distance=settings.pair_max_distance,
                min_ratio=settings.pair_min_ratio,
                cluster_radius=settings.pair_cluster_radius,
                volume_ratio_range=(settings.pair_volume_min_ratio, settings.pair_volume_max_ratio),
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
        max_number = get_max_number_in_baking_collection(settings.pair_prefix, settings.pair_digits)
        prefixes = generate_prefixes(
            settings.pair_prefix,
            settings.pair_digits,
            max_number + 1,
            len(pairs)
        )

        # 重命名物体
        renamed_count, rename_details, rename_errors = self._rename_pairs(pairs, prefixes)

        # 如果有重命名错误,报告并返回(此时未修改任何物体名称)
        if rename_errors:
            settings.last_operation = "重命名失败:名称冲突"
            error_message = ERROR_MESSAGES["name_exists"]
            for error in rename_errors[:5]:
                error_message += f"  {error}\n"
            if len(rename_errors) > 5:
                error_message += f"  ... 等{len(rename_errors)}项\n"
            self.report({'ERROR'}, error_message)
            return {'CANCELLED'}

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

        # 自动设置原点。
        # 放在重命名成功之后执行:配对使用世界空间包围盒,与原点无关,
        # 而提前执行会在配对失败(返回CANCELLED,无撤销步)时留下已改原点的半完成状态
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

        # 统计结果
        all_objects_set = set(mesh_objects)
        paired_objects_set = set()
        for obj1, obj2, _ in pairs:
            paired_objects_set.add(obj1)
            paired_objects_set.add(obj2)

        unpaired_objects = all_objects_set - paired_objects_set

        end_time = time.time()
        processing_time = end_time - start_time

        # 生成结果报告
        self._report_results(
            processing_time,
            settings.pair_algorithm,
            max_number,
            len(pairs),
            renamed_count,
            prefixes,
            baking_collection,
            rename_details,
            unpaired_objects
        )

        # 更新最后操作状态
        pairs_count = len(pairs)
        settings.last_operation = f"成功配对 {pairs_count} 对 ({renamed_count}个物体), 耗时 {processing_time:.2f}s"

        return {'FINISHED'}

    def _rename_pairs(
        self,
        pairs: List[Tuple[bpy.types.Object, bpy.types.Object, float]],
        prefixes: List[str]
    ) -> Tuple[int, List[Dict], List[str]]:
        """执行重命名操作

        分两阶段执行:先校验全部目标名称,全部通过后再统一改名,
        避免出现部分物体已改名、部分未改的半完成状态

        Args:
            pairs: 配对列表
            prefixes: 前缀列表

        Returns:
            Tuple[重命名数量, 重命名详情列表, 错误消息列表]
        """
        # 本批次中会被改名的物体,它们当前占用的名称可以被其他物体接管
        renaming_objects = set()
        for obj1, obj2, _ in pairs:
            renaming_objects.add(obj1)
            renaming_objects.add(obj2)

        # 阶段1:校验目标名称(要求全局唯一)
        planned = []
        rename_errors = []
        reserved_names = set()

        for idx, (obj1, obj2, score) in enumerate(pairs):
            high_obj, low_obj = identify_high_low(obj1, obj2)
            prefix_str = prefixes[idx]
            new_high_name, new_low_name = generate_pair_names(prefix_str)

            for new_name in (new_high_name, new_low_name):
                if new_name in reserved_names:
                    rename_errors.append(f"前缀 {prefix_str} 生成的名称重复: {new_name}")
                    continue

                reserved_names.add(new_name)
                holder = bpy.data.objects.get(new_name)
                if holder is not None and holder not in renaming_objects:
                    rename_errors.append(f"名称已被占用: {new_name}")

            planned.append({
                "prefix": prefix_str,
                "score": score,
                "high_obj": high_obj,
                "low_obj": low_obj,
                "high_faces": get_face_count(high_obj),
                "low_faces": get_face_count(low_obj),
                "high_original": high_obj.name,
                "low_original": low_obj.name,
                "high_new": new_high_name,
                "low_new": new_low_name,
            })

        if rename_errors:
            return 0, [], rename_errors

        # 阶段2:先统一改为临时名称,再改为目标名称。
        # 否则批内物体互相占用目标名称时,Blender 会静默追加 .001 后缀
        for idx, item in enumerate(planned):
            item["high_obj"].name = f"__pair_tmp_{idx}_High"
            item["low_obj"].name = f"__pair_tmp_{idx}_Low"

        rename_details = []
        for item in planned:
            high_obj = item["high_obj"]
            low_obj = item["low_obj"]

            # 保存原始名称到自定义属性(用于撤销功能)
            # 如果已经存在original_name(说明已经配对过),保留最初的原始名称
            if 'original_name' not in high_obj:
                high_obj['original_name'] = item["high_original"]
            if 'original_name' not in low_obj:
                low_obj['original_name'] = item["low_original"]
            high_obj['pairing_prefix'] = item["prefix"]
            low_obj['pairing_prefix'] = item["prefix"]

            high_obj.name = item["high_new"]
            low_obj.name = item["low_new"]

            rename_details.append({
                "prefix": item["prefix"],
                "score": item["score"],
                "high_faces": item["high_faces"],
                "low_faces": item["low_faces"],
                "high_original": item["high_original"],
                "low_original": item["low_original"],
                "high_new": item["high_new"],
                "low_new": item["low_new"]
            })

        return len(planned) * 2, rename_details, rename_errors

    def _report_results(
        self,
        processing_time: float,
        algorithm: str,
        max_number: int,
        pairs_count: int,
        renamed_count: int,
        prefixes: List[str],
        baking_collection: bpy.types.Collection,
        rename_details: List[Dict],
        unpaired_objects: Set[bpy.types.Object]
    ) -> None:
        """生成并显示结果报告

        Args:
            processing_time: 处理耗时(秒)
            algorithm: 使用的算法
            max_number: Baking集合最大序号
            pairs_count: 配对数量
            renamed_count: 重命名数量
            prefixes: 使用的前缀列表
            baking_collection: Baking集合对象
            rename_details: 重命名详情列表
            unpaired_objects: 未配对物体集合
        """
        # 基本信息
        result_message = SUCCESS_MESSAGES["processing_complete"].format(time=processing_time) + "\n"
        result_message += f"算法: {algorithm}\n"
        result_message += f"Baking集合中最大序号: {max_number}\n"

        # 配对信息
        result_message += SUCCESS_MESSAGES["pairs_created"].format(
            count=pairs_count,
            renamed=renamed_count
        ) + "\n"

        # 前缀信息
        if prefixes:
            prefix_list = ', '.join(prefixes[:3])
            if len(prefixes) > 3:
                prefix_list += f" 等{len(prefixes)}个"
            result_message += f"使用前缀: {prefix_list}\n"

        # 集合信息
        if baking_collection:
            msg = SUCCESS_MESSAGES["objects_moved"].format(collection=baking_collection.name)
            result_message += msg + "\n"

        # 配对详情
        if rename_details:
            result_message += "\n配对详情:\n"
            for detail in rename_details[:3]:
                result_message += (
                    f"  {detail['prefix']}: "
                    f"高模({detail['high_faces']}面→{detail['high_new']}) "
                    f"低模({detail['low_faces']}面→{detail['low_new']})\n"
                )
            if len(rename_details) > 3:
                result_message += f"  ... 等{len(rename_details)}对\n"

        # 未配对物体
        if unpaired_objects:
            result_message += f"\n未配对物体: {len(unpaired_objects)}个\n"
            for obj in list(unpaired_objects)[:3]:
                faces = get_face_count(obj)
                result_message += f"  {obj.name} ({faces}面)\n"
            if len(unpaired_objects) > 3:
                result_message += f"  ... 等{len(unpaired_objects)}个\n"

        self.report({'INFO'}, result_message)


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
        no_record_count = 0
        conflict_count = 0

        for obj in selected_objects:
            # 检查是否有原始名称记录
            if 'original_name' not in obj:
                no_record_count += 1
                continue

            original_name = obj['original_name']

            # 检查名称是否已被其他物体占用(物体自身占用不算冲突)
            holder = bpy.data.objects.get(original_name)
            if holder is not None and holder != obj:
                self.report(
                    {'WARNING'},
                    f"无法恢复 '{obj.name}' 的名称为 '{original_name}': 名称已被占用"
                )
                conflict_count += 1
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

        if conflict_count > 0:
            self.report(
                {'WARNING'},
                f"跳过 {conflict_count} 个物体(原始名称已被其他物体占用)"
            )

        if no_record_count > 0 and restored_count == 0 and conflict_count == 0:
            self.report({'WARNING'}, f"未找到可撤销的物体({no_record_count}个无配对记录)")
            return {'CANCELLED'}

        context.scene.pair_rename_tool.last_operation = (
            f"撤销配对: 恢复 {restored_count} 个, "
            f"跳过 {conflict_count + no_record_count} 个"
        )

        return {'FINISHED'}
