# -*- coding: utf-8 -*-
"""性能基准脚本(在 Blender 无头模式下运行)

用法:
    blender --background --factory-startup --python tests/bench.py

在确定性合成场景上对比 元数据缓存开启/关闭 的配对耗时,
用于验证 perf 提交的性能优化效果。场景由固定公式生成,结果可复现。

退出码 0 表示基准运行完成。
"""

import os
import sys
import time

import bpy

# 必须在导入被测包之前把插件父目录加入 sys.path
_PROJECT_PARENT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_PARENT not in sys.path:
    sys.path.insert(0, _PROJECT_PARENT)

from Blender_AutoMatch import find_pairs, ALGORITHM_SIMPLE, ALGORITHM_CLUSTER


# ========== 场景构建 ==========
def clean_scene():
    """清空场景中的所有物体"""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def build_scene(pair_count):
    """构建确定性合成场景:每对为一个高面数球体 + 一个低面数立方体

    Args:
        pair_count: 配对数(总物体数 = pair_count * 2)

    Returns:
        物体列表
    """
    objects = []
    for i in range(pair_count):
        x = i * 3.0
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=1.0, location=(x, 0, 0), segments=8, ring_count=4)
        high = bpy.context.active_object
        high.name = f"High_{i:03d}"
        objects.append(high)

        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(x + 1.0, 0, 0))
        low = bpy.context.active_object
        low.name = f"Low_{i:03d}"
        objects.append(low)
    bpy.context.view_layer.update()
    return objects


# ========== 基准 ==========
def run_once(objects, use_cache, algorithm):
    """执行一次配对并返回 (耗时秒, 配对数)"""
    start = time.perf_counter()
    pairs = find_pairs(
        algorithm, objects,
        max_distance=5.0,
        use_cache=use_cache,
    )
    elapsed = time.perf_counter() - start
    return elapsed, len(pairs)


def bench(label, objects, algorithm, use_cache, repeat=3):
    """重复执行取最小值,降低单次抖动"""
    best = None
    pair_count = 0
    for _ in range(repeat):
        elapsed, pair_count = run_once(objects, use_cache, algorithm)
        if best is None or elapsed < best:
            best = elapsed
    print(f"  {label:<28} {best * 1000:9.1f} ms   pairs={pair_count}")
    return best


def main():
    pair_count = 100  # 200 个物体
    repeat = 3
    print("=" * 60)
    print(f"性能基准: {pair_count * 2} 个物体(每项取 {repeat} 次最小值)")
    print("=" * 60)

    clean_scene()
    objects = build_scene(pair_count)
    print(f"场景构建完成: {len(objects)} 个物体\n")

    print("[简单算法 SIMPLE]")
    t_off = bench("use_cache=False", objects, ALGORITHM_SIMPLE, False, repeat)
    t_on = bench("use_cache=True", objects, ALGORITHM_SIMPLE, True, repeat)

    print("\n[聚类算法 CLUSTER]")
    c_off = bench("use_cache=False", objects, ALGORITHM_CLUSTER, False, repeat)
    c_on = bench("use_cache=True", objects, ALGORITHM_CLUSTER, True, repeat)

    print("\n" + "=" * 60)
    print("汇总(耗时越低越好;降幅为正表示缓存带来提升)")
    print("=" * 60)
    for label, off, on in (
        ("SIMPLE", t_off, t_on),
        ("CLUSTER", c_off, c_on),
    ):
        delta = (off - on) / off * 100 if off > 0 else 0.0
        print(f"  {label:<8} 关缓存 {off * 1000:8.1f} ms -> "
              f"开缓存 {on * 1000:8.1f} ms  ({delta:+.1f}%)")
    sys.exit(0)


if __name__ == "__main__":
    main()
