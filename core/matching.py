# -*- coding: utf-8 -*-
"""
配对算法模块

提供三种配对算法:
    - SIMPLE: 基于距离和面数的简单配对
    - CLUSTER: 聚类配对算法
    - VOLUME: 体积相似度配对算法

三种算法均由 Rust 内核(_core)实现,本模块为薄壳:
负责 bpy 交互与元数据提取,纯计算交还内核。
"""

import bpy
from typing import Dict, List, Optional, Tuple

from ..constants import (
    ALGORITHM_SIMPLE,
    ALGORITHM_CLUSTER,
    ALGORITHM_VOLUME,
    VOLUME_SCORE_WEIGHT,
)
from .cache import ObjectMetadataCache
from ..utils import get_face_count

try:
    from .. import _core
except ImportError as exc:
    raise ImportError(
        "未找到 Rust 内核模块 _core.pyd。请在仓库根目录执行:"
        "cargo build --release,然后把 target/release/_core.dll "
        "复制为插件目录下的 _core.pyd"
        "(或执行 maturin build --release 后从 wheel 中提取)"
    ) from exc


def _collect_face_counts(objects: List[bpy.types.Object]) -> Dict[bpy.types.Object, int]:
    """一次性统计所有物体的面数

    避免在 O(n^2) 的配对循环中反复查询 polygon 数量
    """
    return {obj: get_face_count(obj) for obj in objects}


def find_pairs(
    algorithm: str,
    objects: List[bpy.types.Object],
    max_distance: float = 5.0,
    min_ratio: float = 0.0,
    cluster_radius: float = 5.0,
    volume_ratio_range: Tuple[float, float] = (0.5, 2.0),
    use_cache: bool = True
) -> List[Tuple[bpy.types.Object, bpy.types.Object, float]]:
    """根据指定算法查找高低模配对
    
    Args:
        algorithm: 算法类型 (SIMPLE/CLUSTER/VOLUME)
        objects: 要配对的物体列表
        max_distance: 最大配对距离
        min_ratio: 高模与低模的最小面数比例
        cluster_radius: 聚类半径(聚类算法用)
        volume_ratio_range: 体积比例范围(体积算法用)
        use_cache: 是否使用缓存优化性能
        
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
    
    if cluster_radius <= 0:
        raise ValueError(f"cluster_radius 必须为正数, 当前值: {cluster_radius}")
    
    if not isinstance(volume_ratio_range, (tuple, list)) or len(volume_ratio_range) != 2:
        raise ValueError("volume_ratio_range 必须是包含两个元素的元组或列表")
    
    min_vol, max_vol = volume_ratio_range
    if min_vol <= 0 or max_vol <= 0:
        raise ValueError("volume_ratio_range 的值必须为正数")
    if min_vol > max_vol:
        raise ValueError(f"volume_ratio_range 的最小值不能大于最大值: {min_vol} > {max_vol}")
    
    if len(objects) < 2:
        return []
    
    # 整个配对过程共享同一份元数据缓存
    cache = ObjectMetadataCache() if use_cache else None
    
    # 根据算法类型调用相应的实现(共享同一份缓存)
    try:
        if algorithm == ALGORITHM_SIMPLE:
            return find_pairs_by_distance_and_faces(
                objects, max_distance, min_ratio, use_cache, cache
            )
        elif algorithm == ALGORITHM_CLUSTER:
            return find_pairs_by_clustering(
                objects, max_distance, min_ratio, cluster_radius, use_cache, cache
            )
        elif algorithm == ALGORITHM_VOLUME:
            return find_pairs_by_volume(
                objects, max_distance, min_ratio, volume_ratio_range, use_cache, cache
            )
        else:
            raise ValueError(f"不支持的算法类型: {algorithm}")
    except Exception as e:
        # 捕获并包装底层异常，提供更清晰的错误信息
        raise RuntimeError(f"配对算法执行失败: {str(e)}") from e


def find_pairs_by_distance_and_faces(
    objects: List[bpy.types.Object],
    max_distance: float = 5.0,
    min_ratio: float = 0.0,
    use_cache: bool = True,
    cache: Optional[ObjectMetadataCache] = None
) -> List[Tuple[bpy.types.Object, bpy.types.Object, float]]:
    """算法1:基于距离和面数的简单配对(Rust 内核实现)

    薄壳职责:提取 (center, faces) 平铺数据 → 调用内核 → 索引对映射回 bpy 对象。
    纯计算逻辑位于 Rust 内核(src/lib.rs),此处不再重复实现。

    Args:
        objects: 要配对的物体列表
        max_distance: 最大配对距离阈值
        min_ratio: 高模与低模的最小面数比例(0表示不限制)
        use_cache: 是否使用元数据缓存优化性能
        cache: 调用方共享的缓存,传入时优先于 use_cache
        
    Returns:
        配对列表,每项为 (高模对象, 低模对象, 距离评分)
    """
    if len(objects) < 2:
        return []
    
    if cache is None and use_cache:
        cache = ObjectMetadataCache()
    
    face_counts = _collect_face_counts(objects)
    centers = [tuple(cache.get_center(obj)) for obj in objects]
    faces = [face_counts[obj] for obj in objects]
    
    index_pairs = _core.find_pairs_simple(centers, faces, max_distance, min_ratio)
    
    return [(objects[i], objects[j], score) for i, j, score in index_pairs]


def find_pairs_by_clustering(
    objects: List[bpy.types.Object],
    max_distance: float = 5.0,
    min_ratio: float = 0.0,
    cluster_radius: float = 5.0,
    use_cache: bool = True,
    cache: Optional[ObjectMetadataCache] = None
) -> List[Tuple[bpy.types.Object, bpy.types.Object, float]]:
    """算法2:聚类配对算法(Rust 内核实现)

    聚类划分由内核完成,聚类内的配对复用简单配对内核。
    
    Args:
        objects: 要配对的物体列表
        max_distance: 最大配对距离阈值
        min_ratio: 高模与低模的最小面数比例
        cluster_radius: 聚类半径
        use_cache: 是否使用元数据缓存优化性能
        cache: 调用方共享的缓存,传入时优先于 use_cache
        
    Returns:
        配对列表,每项为 (高模对象, 低模对象, 距离评分)
    """
    if len(objects) < 2:
        return []
    
    if cache is None and use_cache:
        cache = ObjectMetadataCache()
    
    # 聚类(内核实现)
    clusters = cluster_objects(objects, cluster_radius, cache)
    
    # 在每个聚类内进行配对(共享同一份缓存)
    all_pairs = []
    for cluster in clusters:
        if len(cluster) >= 2:
            cluster_pairs = find_pairs_by_distance_and_faces(
                cluster, max_distance, min_ratio, use_cache, cache
            )
            all_pairs.extend(cluster_pairs)
    
    return all_pairs


def find_pairs_by_volume(
    objects: List[bpy.types.Object],
    max_distance: float = 5.0,
    min_ratio: float = 0.0,
    volume_ratio_range: Tuple[float, float] = (0.5, 2.0),
    use_cache: bool = True,
    cache: Optional[ObjectMetadataCache] = None
) -> List[Tuple[bpy.types.Object, bpy.types.Object, float]]:
    """算法3:体积相似度配对算法(Rust 内核实现)

    薄壳职责:提取 (center, faces, volume) 平铺数据 → 调用内核
    → 索引对映射回 bpy 对象。评分权重由 constants 传入内核。

    Args:
        objects: 要配对的物体列表
        max_distance: 最大配对距离阈值
        min_ratio: 高模与低模的最小面数比例
        volume_ratio_range: 体积比例范围 (最小, 最大)
        use_cache: 是否使用元数据缓存优化性能
        cache: 调用方共享的缓存,传入时优先于 use_cache
        
    Returns:
        配对列表,每项为 (高模对象, 低模对象, 距离评分)
    """
    if len(objects) < 2:
        return []
    
    if cache is None and use_cache:
        cache = ObjectMetadataCache()
    
    face_counts = _collect_face_counts(objects)
    centers = [tuple(cache.get_center(obj)) for obj in objects]
    faces = [face_counts[obj] for obj in objects]
    volumes = [cache.get_volume(obj) for obj in objects]
    
    min_volume_ratio, max_volume_ratio = volume_ratio_range
    index_pairs = _core.find_pairs_volume(
        centers, faces, volumes,
        max_distance, min_ratio,
        min_volume_ratio, max_volume_ratio,
        VOLUME_SCORE_WEIGHT,
    )
    
    return [(objects[i], objects[j], score) for i, j, score in index_pairs]


def cluster_objects(
    objects: List[bpy.types.Object],
    radius: float,
    cache: Optional[ObjectMetadataCache] = None
) -> List[List[bpy.types.Object]]:
    """将物体按空间位置聚类(Rust 内核实现)

    薄壳职责:提取中心点平铺数据 → 调用内核 → 索引聚类映射回 bpy 对象。

    Args:
        objects: 物体列表
        radius: 聚类半径
        cache: 元数据缓存对象,传入可避免重复计算包围盒

    Returns:
        聚类列表,每个聚类是一个物体列表
    """
    if not objects:
        return []
    
    if cache is None:
        cache = ObjectMetadataCache()
    
    centers = [tuple(cache.get_center(obj)) for obj in objects]
    index_clusters = _core.cluster_objects(centers, radius)
    
    return [[objects[i] for i in cluster] for cluster in index_clusters]
