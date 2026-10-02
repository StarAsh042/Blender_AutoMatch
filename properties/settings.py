# -*- coding: utf-8 -*-
"""
插件设置数据模型

定义所有插件属性,使用PropertyGroup进行组织,更符合Blender规范
"""

import bpy

from ..constants import (
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
)


def _update_volume_min_ratio(self, context: bpy.types.Context) -> None:
    """最小体积比变化时,带动最大体积比,保持 min <= max"""
    if self.pair_volume_min_ratio > self.pair_volume_max_ratio:
        self.pair_volume_max_ratio = self.pair_volume_min_ratio


def _update_volume_max_ratio(self, context: bpy.types.Context) -> None:
    """最大体积比变化时,带动最小体积比,保持 min <= max"""
    if self.pair_volume_max_ratio < self.pair_volume_min_ratio:
        self.pair_volume_min_ratio = self.pair_volume_max_ratio


class PairRenameSettings(bpy.types.PropertyGroup):
    """
    插件设置 - 存储插件的所有配置参数

    分类:
        - 算法设置: 配对算法选择和参数
        - 通用参数: 通用配置选项
        - 命名设置: 命名相关参数
        - 集合管理: Baking集合管理
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
        step=0.1,
        update=_update_volume_min_ratio
    )

    pair_volume_max_ratio: bpy.props.FloatProperty(
        name="最大体积比",
        description="体积算法的最大体积比例(仅体积算法有效)",
        default=DEFAULT_VOLUME_MAX_RATIO,
        min=0.5,
        max=10.0,
        step=0.1,
        update=_update_volume_max_ratio
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
