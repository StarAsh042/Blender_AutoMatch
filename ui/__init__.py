# -*- coding: utf-8 -*-
"""
UI面板模块

包含所有UI面板的定义,按功能分类
"""

from .main_panel import VIEW3D_PT_PairRename
from .usage_panel import VIEW3D_PT_UsagePanel
from .main_action_panel import VIEW3D_PT_MainActionPanel
from .algorithm_panel import VIEW3D_PT_AlgorithmPanel
from .common_params_panel import VIEW3D_PT_CommonParamsPanel
from .cluster_params_panel import VIEW3D_PT_ClusterParamsPanel
from .volume_params_panel import VIEW3D_PT_VolumeParamsPanel
from .naming_params_panel import VIEW3D_PT_NamingParamsPanel
from .collection_params_panel import VIEW3D_PT_CollectionParamsPanel
from .statistics_panel import VIEW3D_PT_StatisticsPanel

__all__ = [
    'VIEW3D_PT_PairRename',
    'VIEW3D_PT_UsagePanel',
    'VIEW3D_PT_MainActionPanel',
    'VIEW3D_PT_AlgorithmPanel',
    'VIEW3D_PT_CommonParamsPanel',
    'VIEW3D_PT_ClusterParamsPanel',
    'VIEW3D_PT_VolumeParamsPanel',
    'VIEW3D_PT_NamingParamsPanel',
    'VIEW3D_PT_CollectionParamsPanel',
    'VIEW3D_PT_StatisticsPanel',
]
