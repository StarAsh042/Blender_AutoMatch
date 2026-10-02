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

from Blender_AutoMatch import find_pairs
from Blender_AutoMatch.constants import (
    ALGORITHM_SIMPLE,
    ALGORITHM_CLUSTER,
    ALGORITHM_VOLUME,
)


# ========== 场景与工具函数 ==========
def clean_scene():
    """清空场景中的所有物体与非场景集合"""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)


def make_mesh(name, location, subdivisions=0, size=2.0, scale=None, shift_verts_x=0.0):
    """创建一个网格物体

    Args:
        name: 物体名称
        location: 创建位置
        subdivisions: 细分级数(0=6面立方体; >0 生成高面数UV球)
        size: 物体尺寸(包围盒跨度)
        scale: 物体缩放(影响包围盒体积)
        shift_verts_x: 网格顶点沿X轴偏移(用于让原点偏离包围盒中心)
    """
    active = bpy.context.view_layer.objects.active
    if active is not None and active.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    if subdivisions > 0:
        # Blender 3.4 的 primitive_cube_add 没有 subdivisions 参数,用 UV 球生成高面数网格
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=size / 2, location=location,
            segments=4 * (subdivisions + 1), ring_count=2 * (subdivisions + 1))
    else:
        bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    obj = bpy.context.active_object
    obj.name = name
    if scale is not None:
        obj.scale = scale
    if shift_verts_x:
        for vert in obj.data.vertices:
            vert.co.x += shift_verts_x
        obj.data.update()
    # 刷新求值,确保 matrix_world / bound_box 反映缩放与顶点偏移
    bpy.context.view_layer.update()
    return obj


def select_only(objects):
    """只选中指定物体并激活第一个"""
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def get_settings():
    return bpy.context.scene.pair_rename_tool


# ========== 测试用例 ==========
class TestARegistration(unittest.TestCase):
    """插件注册状态"""

    def test_scene_property_registered(self):
        self.assertTrue(hasattr(bpy.types.Scene, 'pair_rename_tool'))

    def test_operators_registered(self):
        # bpy.types 中操作符按 bl_idname 的 OT 形式注册
        for type_name in (
            'OBJECT_OT_pair_rename',
            'OBJECT_OT_unpair_selected',
            'OBJECT_OT_pair_rename_reset',
        ):
            self.assertTrue(hasattr(bpy.types, type_name), f"missing {type_name}")

    def test_panels_registered(self):
        for type_name in ('VIEW3D_PT_pair_rename', 'VIEW3D_PT_main_action_panel'):
            self.assertTrue(hasattr(bpy.types, type_name), f"missing {type_name}")


class TestBFindingPairs(unittest.TestCase):
    """三种配对算法的核心逻辑"""

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

    def test_simple_respects_min_ratio(self):
        # 面数相同的两个物体,比例为1
        a = make_mesh("A", (0, 0, 0))
        b = make_mesh("B", (0.5, 0, 0))
        self.assertEqual(
            find_pairs(ALGORITHM_SIMPLE, [a, b], max_distance=5.0, min_ratio=2.0), [])
        self.assertEqual(
            len(find_pairs(ALGORITHM_SIMPLE, [a, b], max_distance=5.0, min_ratio=1.0)), 1)

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

    def test_invalid_algorithm_raises(self):
        a = make_mesh("A", (0, 0, 0))
        b = make_mesh("B", (0.5, 0, 0))
        with self.assertRaises(RuntimeError):
            find_pairs("NOT_EXIST", [a, b], max_distance=5.0)

    def test_fewer_than_two_objects(self):
        a = make_mesh("A", (0, 0, 0))
        self.assertEqual(find_pairs(ALGORITHM_SIMPLE, [a], max_distance=5.0), [])


class TestCUtils(unittest.TestCase):
    """工具函数"""

    def setUp(self):
        clean_scene()

    def test_max_number_in_baking_collection(self):
        from Blender_AutoMatch.utils import get_max_number_in_baking_collection
        coll = bpy.data.collections.new("Baking")
        bpy.context.scene.collection.children.link(coll)
        for name in ("BakePoly_007_High", "BakePoly_003_Low",
                     "BakePoly_010_High", "Other", "BakePoly_12_High"):
            obj = make_mesh(name, (0, 0, 0))
            coll.objects.link(obj)
        # 位数不同的序号(12是2位)不算,取3位序号最大值10
        self.assertEqual(get_max_number_in_baking_collection("BakePoly_", 3), 10)

    def test_no_baking_collection_returns_zero(self):
        from Blender_AutoMatch.utils import get_max_number_in_baking_collection
        self.assertEqual(get_max_number_in_baking_collection("BakePoly_", 3), 0)

    def test_generate_prefixes(self):
        from Blender_AutoMatch.utils import generate_prefixes
        self.assertEqual(
            generate_prefixes("BakePoly_", 3, 8, 2),
            ["BakePoly_008", "BakePoly_009"])


class TestDOperatorPair(unittest.TestCase):
    """配对重命名操作符"""

    def setUp(self):
        clean_scene()
        bpy.ops.object.pair_rename_reset()

    def _make_pair_objects(self, shift_verts_x=0.0):
        high = make_mesh("MyHigh", (0, 0, 0), subdivisions=3, shift_verts_x=shift_verts_x)
        low = make_mesh("MyLow", (0, 0, 0), shift_verts_x=shift_verts_x)
        return high, low

    def test_rename_flow(self):
        high, low = self._make_pair_objects()
        select_only([high, low])
        result = bpy.ops.object.pair_rename()
        self.assertEqual(result, {'FINISHED'})
        self.assertEqual(high.name, "BakePoly_001_High")
        self.assertEqual(low.name, "BakePoly_001_Low")
        self.assertEqual(high['original_name'], "MyHigh")
        self.assertEqual(low['original_name'], "MyLow")
        baking = bpy.data.collections.get("Baking")
        self.assertIsNotNone(baking)
        self.assertIn(high.name, baking.objects)
        self.assertIn(low.name, baking.objects)

    def test_name_conflict_cancels_without_changes(self):
        high, low = self._make_pair_objects()
        make_mesh("BakePoly_001_High", (100, 100, 0))  # 冲突名称占用者
        select_only([high, low])
        # 操作符 report({'ERROR'}) 会让 bpy.ops 调用抛 RuntimeError
        with self.assertRaises(RuntimeError):
            bpy.ops.object.pair_rename()
        self.assertEqual(high.name, "MyHigh")
        self.assertEqual(low.name, "MyLow")
        self.assertNotIn('original_name', high)
        self.assertNotIn('original_name', low)
        self.assertIsNone(bpy.data.collections.get("Baking"))

    def test_origin_not_touched_when_conflict_cancels(self):
        # 回归测试:配对失败返回CANCELLED时不留下已改原点的半完成状态
        high, low = self._make_pair_objects(shift_verts_x=2.0)
        self.assertEqual(high.location.x, 0.0)
        make_mesh("BakePoly_001_High", (100, 100, 0))
        select_only([high, low])
        with self.assertRaises(RuntimeError):
            bpy.ops.object.pair_rename()
        self.assertAlmostEqual(high.location.x, 0.0, places=5)
        self.assertAlmostEqual(low.location.x, 0.0, places=5)

    def test_origin_fixed_to_bbox_center_on_success(self):
        high, low = self._make_pair_objects(shift_verts_x=2.0)
        select_only([high, low])
        result = bpy.ops.object.pair_rename()
        self.assertEqual(result, {'FINISHED'})
        self.assertAlmostEqual(high.location.x, 2.0, places=4)
        self.assertAlmostEqual(low.location.x, 2.0, places=4)

    def test_repair_preserves_first_original_name(self):
        high, low = self._make_pair_objects()
        select_only([high, low])
        self.assertEqual(bpy.ops.object.pair_rename(), {'FINISHED'})
        self.assertEqual(high.name, "BakePoly_001_High")
        select_only([high, low])
        self.assertEqual(bpy.ops.object.pair_rename(), {'FINISHED'})
        self.assertEqual(high.name, "BakePoly_002_High")
        self.assertEqual(low.name, "BakePoly_002_Low")
        # 二次配对保留最初的原始名称
        self.assertEqual(high['original_name'], "MyHigh")
        self.assertEqual(low['original_name'], "MyLow")

    def test_no_mesh_selected_cancels(self):
        select_only([make_mesh("A", (0, 0, 0))])
        self.assertEqual(bpy.ops.object.pair_rename(), {'CANCELLED'})


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

    def test_unpair_with_self_held_original_name(self):
        # 回归测试:物体自身占用了原名称时不应被误判为冲突
        high, low = self._pair_simple()
        high.name = "MyHigh"  # 用户手动改回原名称
        select_only([high, low])
        result = bpy.ops.object.unpair_selected()
        self.assertEqual(result, {'FINISHED'})
        self.assertEqual(high.name, "MyHigh")
        self.assertNotIn('original_name', high)

    def test_unpair_skips_when_name_taken_by_other(self):
        high, low = self._pair_simple()
        make_mesh("MyHigh", (100, 100, 0))  # 原名称被其他物体占用
        select_only([high, low])
        result = bpy.ops.object.unpair_selected()
        self.assertEqual(result, {'FINISHED'})  # low 仍可恢复
        self.assertEqual(high.name, "BakePoly_001_High")  # high 被跳过
        self.assertEqual(low.name, "MyLow")

    def test_unpair_without_record_cancels(self):
        obj = make_mesh("Plain", (0, 0, 0))
        select_only([obj])
        self.assertEqual(bpy.ops.object.unpair_selected(), {'CANCELLED'})


class TestFSettingsClamp(unittest.TestCase):
    """设置项联动钳制"""

    def test_volume_ratio_clamp(self):
        settings = get_settings()
        settings.pair_volume_min_ratio = 3.0
        self.assertGreaterEqual(settings.pair_volume_max_ratio,
                                settings.pair_volume_min_ratio)
        settings.pair_volume_max_ratio = 1.5
        self.assertLessEqual(settings.pair_volume_min_ratio,
                             settings.pair_volume_max_ratio)
        # 还原默认,避免影响其他测试
        bpy.ops.object.pair_rename_reset()


class TestZRegisterCycle(unittest.TestCase):
    """注销/再注册循环(放在最后执行)"""

    def test_disable_then_enable(self):
        import addon_utils
        addon_utils.disable("Blender_AutoMatch")
        self.assertFalse(hasattr(bpy.types.Scene, 'pair_rename_tool'))
        mod = addon_utils.enable("Blender_AutoMatch", default_set=False)
        self.assertIsNotNone(mod)
        self.assertTrue(hasattr(bpy.types.Scene, 'pair_rename_tool'))


# ========== 入口 ==========
def build_suite():
    """按声明顺序构建测试套件"""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for case in (
        TestARegistration,
        TestBFindingPairs,
        TestCUtils,
        TestDOperatorPair,
        TestEOperatorUnpair,
        TestFSettingsClamp,
        TestZRegisterCycle,
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
