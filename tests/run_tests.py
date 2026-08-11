# -*- coding: utf-8 -*-
"""高低模配对插件自动化测试(在 Blender 无头模式下运行)

用法:
    blender --background --factory-startup --python tests/run_tests.py

退出码 0 表示全部通过,1 表示有失败。
"""

import os
import sys
import unittest

import bpy

# 必须在导入被测包之前把插件父目录加入 sys.path
_PROJECT_PARENT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_PARENT not in sys.path:
    sys.path.insert(0, _PROJECT_PARENT)

from Blender_AutoMatch import (
    find_pairs,
    ALGORITHM_SIMPLE,
    ALGORITHM_CLUSTER,
    ALGORITHM_VOLUME,
)


# ========== 场景与工具函数 ==========
def clean_scene():
    """清空场景中的所有物体"""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def make_mesh(name, location, subdivisions=0, size=2.0, scale=None):
    """创建一个网格物体

    Args:
        name: 物体名称
        location: 创建位置
        subdivisions: 细分级数(0=6面立方体; >0 生成高面数UV球)
        size: 物体尺寸(包围盒跨度)
        scale: 物体缩放(影响包围盒体积)
    """
    if subdivisions > 0:
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=size / 2, location=location,
            segments=4 * (subdivisions + 1), ring_count=2 * (subdivisions + 1))
    else:
        bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    obj = bpy.context.active_object
    obj.name = name
    if scale is not None:
        obj.scale = scale
    # 刷新求值,确保 matrix_world / bound_box 反映缩放
    bpy.context.view_layer.update()
    return obj


def select_only(objects):
    """只选中指定物体并激活第一个"""
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


# ========== 测试用例 ==========
class TestARegistration(unittest.TestCase):
    """插件注册状态"""

    def test_scene_property_registered(self):
        self.assertTrue(hasattr(bpy.types.Scene, 'pair_rename_tool'))

    def test_operators_registered(self):
        # bpy.types 中操作符按 bl_idname 的 OT 形式注册
        for type_name in (
            'OBJECT_OT_pair_rename',
            'OBJECT_OT_pair_rename_reset',
            'OBJECT_OT_set_pair_algorithm_simple',
            'OBJECT_OT_set_pair_algorithm_cluster',
            'OBJECT_OT_set_pair_algorithm_volume',
        ):
            self.assertTrue(hasattr(bpy.types, type_name), f"missing {type_name}")

    def test_panels_registered(self):
        for type_name in ('VIEW3D_PT_pair_rename', 'VIEW3D_PT_main_action_panel'):
            self.assertTrue(hasattr(bpy.types, type_name), f"missing {type_name}")


class TestBFindingPairs(unittest.TestCase):
    """配对算法核心逻辑"""

    def setUp(self):
        clean_scene()

    def test_simple_pairs_high_with_low(self):
        high = make_mesh("High", (0, 0, 0), subdivisions=3)
        low = make_mesh("Low", (0, 0, 0))
        pairs = find_pairs(ALGORITHM_SIMPLE, [high, low], max_distance=5.0)
        self.assertEqual(len(pairs), 1)
        self.assertIs(pairs[0][0], high)
        self.assertIs(pairs[0][1], low)

    def test_simple_respects_max_distance(self):
        high = make_mesh("High", (0, 0, 0), subdivisions=3)
        low = make_mesh("Low", (100, 0, 0))
        pairs = find_pairs(ALGORITHM_SIMPLE, [high, low], max_distance=5.0)
        self.assertEqual(pairs, [])

    def test_cluster_splits_distant_groups(self):
        high_a = make_mesh("HighA", (-50, 0, 0), subdivisions=3)
        low_a = make_mesh("LowA", (-49, 0, 0))
        high_b = make_mesh("HighB", (50, 0, 0), subdivisions=3)
        low_b = make_mesh("LowB", (51, 0, 0))
        pairs = find_pairs(
            ALGORITHM_CLUSTER, [high_a, low_a, high_b, low_b],
            max_distance=5.0, cluster_radius=2.0)
        self.assertEqual(len(pairs), 2)
        members = {frozenset((p[0].name, p[1].name)) for p in pairs}
        self.assertEqual(members, {frozenset(("HighA", "LowA")), frozenset(("HighB", "LowB"))})

    def test_cluster_radius_prevents_cross_cluster_pair(self):
        # 距离3的两个物体:简单算法可配对,聚类半径1时被分入不同聚类而无法配对
        high = make_mesh("High", (0, 0, 0), subdivisions=3)
        low = make_mesh("Low", (3, 0, 0))
        self.assertEqual(
            len(find_pairs(ALGORITHM_SIMPLE, [high, low], max_distance=5.0)), 1)
        self.assertEqual(
            find_pairs(ALGORITHM_CLUSTER, [high, low],
                       max_distance=5.0, cluster_radius=1.0), [])

    def test_volume_respects_ratio_range(self):
        high = make_mesh("High", (0, 0, 0), subdivisions=3)
        low = make_mesh("Low", (0, 0, 0), scale=(3, 3, 3))  # 包围盒体积放大27倍
        self.assertEqual(
            find_pairs(ALGORITHM_VOLUME, [high, low], max_distance=5.0,
                       volume_ratio_range=(0.5, 2.0)), [])
        pairs = find_pairs(ALGORITHM_VOLUME, [high, low], max_distance=5.0,
                           volume_ratio_range=(0.01, 0.1))
        self.assertEqual(len(pairs), 1)

    def test_fewer_than_two_objects(self):
        a = make_mesh("A", (0, 0, 0))
        self.assertEqual(find_pairs(ALGORITHM_SIMPLE, [a], max_distance=5.0), [])


class TestEOperatorUnpair(unittest.TestCase):
    """撤销配对操作符"""

    def setUp(self):
        clean_scene()
        bpy.ops.object.pair_rename_reset()

    def _pair_simple(self):
        high = make_mesh("MyHigh", (0, 0, 0), subdivisions=3)
        low = make_mesh("MyLow", (0, 0, 0))
        select_only([high, low])
        self.assertEqual(bpy.ops.object.pair_rename(), {'FINISHED'})
        return high, low

    def test_unpair_restores_names(self):
        high, low = self._pair_simple()
        select_only([high, low])
        result = bpy.ops.object.unpair_selected()
        self.assertEqual(result, {'FINISHED'})
        self.assertEqual(high.name, "MyHigh")
        self.assertEqual(low.name, "MyLow")
        self.assertNotIn('original_name', high)
        self.assertNotIn('pairing_prefix', low)


# ========== 入口 ==========
def build_suite():
    """按声明顺序构建测试套件"""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for case in (
        TestARegistration,
        TestBFindingPairs,
        TestEOperatorUnpair,
    ):
        suite.addTests(loader.loadTestsFromTestCase(case))
    return suite


def main():
    import addon_utils
    try:
        addon_utils.enable("Blender_AutoMatch", default_set=False)
    except Exception as exc:
        print(f"addon_utils.enable failed: {exc}")

    if not hasattr(bpy.types.Scene, 'pair_rename_tool'):
        import Blender_AutoMatch
        Blender_AutoMatch.register()

    result = unittest.TextTestRunner(verbosity=2).run(build_suite())
    print(f"\nRan {result.testsRun} tests: "
          f"{len(result.failures)} failures, {len(result.errors)} errors")
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
