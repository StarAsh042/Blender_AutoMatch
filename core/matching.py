# -*- coding: utf-8 -*-
"""
配对算法模块

提供三种配对算法:
    - SIMPLE: 基于距离和面数的简单配对
    - CLUSTER: 聚类配对算法
    - VOLUME: 体积相似度配对算法
"""

import bpy
from typing import Dict, List, Optional, Tuple
from collections import deque

from ..constants import (
    ALGORITHM_SIMPLE,
    ALGORITHM_CLUSTER,
    ALGORITHM_VOLUME,
    VOLUME_SCORE_WEIGHT,
)
from .cache import ObjectMetadataCache
from ..utils import (
    get_face_count,
    calculate_distance,
    calculate_bbox_volume,
)


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
        cluster_radius: 聚类半径（聚类算法用）
        volume_ratio_range: 体积比例范围（体积算法用）
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
    """算法1:基于距离和面数的简单配对
    
    适用于物体分布均匀、数量较少的场景
    
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
            distance = calculate_distance(obj1, obj2, cache)
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


def find_pairs_by_clustering(
    objects: List[bpy.types.Object],
    max_distance: float = 5.0,
    min_ratio: float = 0.0,
    cluster_radius: float = 5.0,
    use_cache: bool = True,
    cache: Optional[ObjectMetadataCache] = None
) -> List[Tuple[bpy.types.Object, bpy.types.Object, float]]:
    """算法2:聚类配对算法
    
    先按空间位置聚类,然后在每个聚类内进行配对。
    适用于物体分布有明显聚类特征的场景(如多个角色)
    
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
    
    # 聚类
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
    """算法3:体积相似度配对算法
    
    考虑物体体积相似度的配对算法。
    适用于需要考虑体积相似度的场景
    
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
    volumes = {obj: calculate_bbox_volume(obj, cache) for obj in objects}
    
    # 按面数降序,保证每个物体只与面数不多于自己的物体配对
    sorted_objects = sorted(objects, key=face_counts.__getitem__, reverse=True)
    pairs = []
    used_objects = set()
    
    min_volume_ratio, max_volume_ratio = volume_ratio_range
    
    for i, obj1 in enumerate(sorted_objects):
        if obj1 in used_objects:
            continue
        
        faces1 = face_counts[obj1]
        volume1 = volumes[obj1]
        best_match = None
        best_distance = float('inf')
        best_score = 0.0
        
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
            
            # 检查体积比例
            volume2 = volumes[obj2]
            if volume2 == 0:
                continue
            
            volume_ratio = volume1 / volume2
            if volume_ratio < min_volume_ratio or volume_ratio > max_volume_ratio:
                continue
            
            # 计算距离并检查阈值
            distance = calculate_distance(obj1, obj2, cache)
            if distance > max_distance:
                continue
            
            # 计算综合评分 (距离 + 体积相似度)
            distance_score = 1.0 / (1.0 + distance)
            
            # 体积相似度评分 (比例越接近1越好)
            volume_similarity = 1.0 - abs(volume_ratio - 1.0)
            volume_score = volume_similarity * VOLUME_SCORE_WEIGHT
            
            score = distance_score + volume_score
            
            if score > best_score:
                best_match = obj2
                best_distance = distance
                best_score = score
        
        if best_match is not None:
            pairs.append((obj1, best_match, best_distance))
            used_objects.add(obj1)
            used_objects.add(best_match)
    
    return pairs


def cluster_objects(
    objects: List[bpy.types.Object],
    radius: float,
    cache: Optional[ObjectMetadataCache] = None
) -> List[List[bpy.types.Object]]:
    """将物体按空间位置聚类
    
    Args:
        objects: 物体列表
        radius: 聚类半径
        cache: 元数据缓存对象,传入可避免重复计算包围盒
        
    Returns:
        聚类列表,每个聚类是一个物体列表
    """
    if not objects:
        return []
    
    clusters = []
    used_objects = set()
    
    for obj in objects:
        if obj in used_objects:
            continue
        
        # 创建新聚类
        cluster = [obj]
        used_objects.add(obj)
        
        # 使用BFS寻找邻近物体
        queue = deque([obj])
        
        while queue:
            current = queue.popleft()
            
            for other in objects:
                if other in used_objects:
                    continue
                
                # 如果在聚类半径内,加入聚类
                if calculate_distance(current, other, cache) <= radius:
                    cluster.append(other)
                    used_objects.add(other)
                    queue.append(other)
        
        clusters.append(cluster)
    
    return clusters
