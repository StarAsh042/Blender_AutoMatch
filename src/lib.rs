//! 高低模配对内核(Rust)
//!
//! 本 crate 通过 PyO3 以稳定 ABI(abi3)向 Python 侧暴露配对算法,
//! 编译产物为 `_core.pyd`,由插件 `core/matching.py` 薄壳调用。
//!
//! 边界约定:
//!   - Python 侧负责 bpy 交互,并经 `ObjectMetadataCache` 提取
//!     (center, faces, volume) 平铺数据后调用本内核;
//!   - 本内核不认识 bpy,只做纯计算,返回索引对(索引对应入参顺序);
//!   - 计算过程经 `py.detach` 释放 GIL,避免阻塞 Blender 界面。
//!
//! 三种配对算法均已迁入内核,Python 侧只保留薄壳与 bpy 交互。

use pyo3::prelude::*;
use std::collections::VecDeque;

/// 计算两个包围盒中心点之间的欧氏距离
///
/// 内核各算法共用的纯函数。
fn center_distance(a: [f64; 3], b: [f64; 3]) -> f64 {
    let dx = a[0] - b[0];
    let dy = a[1] - b[1];
    let dz = a[2] - b[2];
    (dx * dx + dy * dy + dz * dz).sqrt()
}

/// 算法1:基于距离和面数的简单配对(纯计算实现)
///
/// 入参为平铺数据(由 Python 侧从 `ObjectMetadataCache` 提取):
///   - `centers`: 每个物体的包围盒中心
///   - `faces`:   每个物体的面数
///
/// 返回 `(obj1 索引, obj2 索引, 距离)` 列表;obj1 为面数较多者
/// (调用方仍按原流程做高低模识别与重命名)。
fn find_pairs_simple_impl(
    centers: &[[f64; 3]],
    faces: &[i64],
    max_distance: f64,
    min_ratio: f64,
) -> Vec<(usize, usize, f64)> {
    // 按面数降序(稳定排序,与 Python sorted(reverse=True) 的稳定性一致)
    let mut order: Vec<usize> = (0..centers.len()).collect();
    order.sort_by(|&a, &b| faces[b].cmp(&faces[a]));

    let mut used = vec![false; centers.len()];
    let mut pairs = Vec::new();

    for (i, &o1) in order.iter().enumerate() {
        if used[o1] {
            continue;
        }
        let faces1 = faces[o1];
        // 面数为0的物体不参与配对(薄壳已过滤,内核作为边界防线:
        // 避免0面物体经直接调用内核时进入比例计算)
        if faces1 <= 0 {
            continue;
        }
        let mut best_match: Option<usize> = None;
        let mut best_distance = f64::INFINITY;

        for &o2 in &order[i + 1..] {
            if used[o2] {
                continue;
            }
            let faces2 = faces[o2];
            if faces2 <= 0 {
                continue;
            }
            // 检查面数比例
            if min_ratio > 0.0 && (faces1 as f64 / faces2 as f64) < min_ratio {
                continue;
            }
            let distance = center_distance(centers[o1], centers[o2]);
            if distance > max_distance {
                continue;
            }
            if distance < best_distance {
                best_match = Some(o2);
                best_distance = distance;
            }
        }

        if let Some(o2) = best_match {
            pairs.push((o1, o2, best_distance));
            used[o1] = true;
            used[o2] = true;
        }
    }

    pairs
}

/// 算法3:体积相似度配对(纯计算实现)
///
/// 在简单配对的基础上增加体积比例筛选与综合评分:
/// `score = 距离分 + 体积相似度 * volume_weight`。
/// 评分权重由 Python 侧传入,避免同一常量两处定义。
#[allow(clippy::too_many_arguments)]
fn find_pairs_volume_impl(
    centers: &[[f64; 3]],
    faces: &[i64],
    volumes: &[f64],
    max_distance: f64,
    min_ratio: f64,
    min_volume_ratio: f64,
    max_volume_ratio: f64,
    volume_weight: f64,
) -> Vec<(usize, usize, f64)> {
    // 按面数降序(稳定排序,与 Python sorted(reverse=True) 的稳定性一致)
    let mut order: Vec<usize> = (0..centers.len()).collect();
    order.sort_by(|&a, &b| faces[b].cmp(&faces[a]));

    let mut used = vec![false; centers.len()];
    let mut pairs = Vec::new();

    for (i, &o1) in order.iter().enumerate() {
        if used[o1] {
            continue;
        }
        let faces1 = faces[o1];
        let volume1 = volumes[o1];
        // 面数为0的物体不参与配对(同简单算法的边界防线)
        if faces1 <= 0 {
            continue;
        }
        let mut best_match: Option<usize> = None;
        let mut best_distance = f64::INFINITY;
        let mut best_score = 0.0;

        for &o2 in &order[i + 1..] {
            if used[o2] {
                continue;
            }
            let faces2 = faces[o2];
            if faces2 <= 0 {
                continue;
            }
            // 检查面数比例
            if min_ratio > 0.0 && (faces1 as f64 / faces2 as f64) < min_ratio {
                continue;
            }
            // 检查体积比例
            let volume2 = volumes[o2];
            if volume2 == 0.0 {
                continue;
            }
            let volume_ratio = volume1 / volume2;
            if volume_ratio < min_volume_ratio || volume_ratio > max_volume_ratio {
                continue;
            }
            let distance = center_distance(centers[o1], centers[o2]);
            if distance > max_distance {
                continue;
            }
            // 计算综合评分 (距离 + 体积相似度)
            let distance_score = 1.0 / (1.0 + distance);
            let volume_similarity = 1.0 - (volume_ratio - 1.0).abs();
            let score = distance_score + volume_similarity * volume_weight;
            if score > best_score {
                best_match = Some(o2);
                best_distance = distance;
                best_score = score;
            }
        }

        if let Some(o2) = best_match {
            pairs.push((o1, o2, best_distance));
            used[o1] = true;
            used[o2] = true;
        }
    }

    pairs
}

/// 聚类划分:按空间位置将物体分入不同聚类(BFS,纯计算实现)
///
/// 返回聚类列表,每个聚类是索引列表;索引对应入参顺序。
fn cluster_objects_impl(centers: &[[f64; 3]], radius: f64) -> Vec<Vec<usize>> {
    let n = centers.len();
    let mut used = vec![false; n];
    let mut clusters = Vec::new();

    for start in 0..n {
        if used[start] {
            continue;
        }
        // 创建新聚类,使用 BFS 寻找邻近物体
        let mut cluster = vec![start];
        used[start] = true;
        let mut queue = VecDeque::new();
        queue.push_back(start);

        while let Some(current) = queue.pop_front() {
            for (other, used_flag) in used.iter_mut().enumerate() {
                if *used_flag {
                    continue;
                }
                // 如果在聚类半径内,加入聚类
                if center_distance(centers[current], centers[other]) <= radius {
                    cluster.push(other);
                    *used_flag = true;
                    queue.push_back(other);
                }
            }
        }

        clusters.push(cluster);
    }

    clusters
}

/// Python 绑定:简单配对(计算期间释放 GIL)
#[pyfunction]
fn find_pairs_simple(
    py: Python<'_>,
    centers: Vec<[f64; 3]>,
    faces: Vec<i64>,
    max_distance: f64,
    min_ratio: f64,
) -> Vec<(usize, usize, f64)> {
    py.detach(|| find_pairs_simple_impl(&centers, &faces, max_distance, min_ratio))
}

/// Python 绑定:聚类划分(计算期间释放 GIL)
#[pyfunction]
fn cluster_objects(py: Python<'_>, centers: Vec<[f64; 3]>, radius: f64) -> Vec<Vec<usize>> {
    py.detach(|| cluster_objects_impl(&centers, radius))
}

/// Python 绑定:体积配对(计算期间释放 GIL)
///
/// 参数较多:薄壳只做数据搬运,调参项(含评分权重)全部由 Python 侧常量提供。
#[allow(clippy::too_many_arguments)]
#[pyfunction]
fn find_pairs_volume(
    py: Python<'_>,
    centers: Vec<[f64; 3]>,
    faces: Vec<i64>,
    volumes: Vec<f64>,
    max_distance: f64,
    min_ratio: f64,
    min_volume_ratio: f64,
    max_volume_ratio: f64,
    volume_weight: f64,
) -> Vec<(usize, usize, f64)> {
    py.detach(|| {
        find_pairs_volume_impl(
            &centers,
            &faces,
            &volumes,
            max_distance,
            min_ratio,
            min_volume_ratio,
            max_volume_ratio,
            volume_weight,
        )
    })
}

/// 内核版本号(与 `CARGO_PKG_VERSION` 同步,供导入自检)
#[pyfunction]
fn kernel_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

/// Python 模块入口:`_core`
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(kernel_version, m)?)?;
    m.add_function(wrap_pyfunction!(find_pairs_simple, m)?)?;
    m.add_function(wrap_pyfunction!(cluster_objects, m)?)?;
    m.add_function(wrap_pyfunction!(find_pairs_volume, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn center_distance_is_zero_for_identical_points() {
        assert_eq!(center_distance([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 0.0);
    }

    #[test]
    fn center_distance_matches_3_4_5_triangle() {
        let d = center_distance([0.0, 0.0, 0.0], [3.0, 4.0, 0.0]);
        assert!((d - 5.0).abs() < 1e-12);
    }

    #[test]
    fn find_pairs_simple_pairs_nearest_within_distance() {
        let centers = vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [100.0, 0.0, 0.0]];
        let faces = vec![10, 4, 100];
        let pairs = find_pairs_simple_impl(&centers, &faces, 5.0, 0.0);
        // 面数降序:100面(远,无同伴)→ 10面与4面距离1 → 配对
        assert_eq!(pairs, vec![(0, 1, 1.0)]);
    }

    #[test]
    fn find_pairs_simple_respects_min_ratio() {
        let centers = vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]];
        let faces = vec![10, 9];
        // 比例 10/9 ≈ 1.11 < 2.0 → 拒绝配对
        assert!(find_pairs_simple_impl(&centers, &faces, 5.0, 2.0).is_empty());
    }

    #[test]
    fn find_pairs_simple_skips_zero_face_objects() {
        // 0面物体不参与配对:既不做"高模"也不做候选
        let centers = vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]];
        let faces = vec![0, 4];
        assert!(find_pairs_simple_impl(&centers, &faces, 5.0, 0.0).is_empty());
        // 仅有0面物体时同样无配对(且不 panic)
        assert!(find_pairs_simple_impl(&centers, &[0, 0], 5.0, 0.0).is_empty());
    }

    #[test]
    fn cluster_objects_splits_distant_groups() {
        let centers = vec![
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [100.0, 0.0, 0.0],
            [101.0, 0.0, 0.0],
        ];
        let clusters = cluster_objects_impl(&centers, 2.0);
        assert_eq!(clusters, vec![vec![0, 1], vec![2, 3]]);
    }

    #[test]
    fn cluster_objects_radius_prevents_cross_cluster_pair() {
        let centers = vec![[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]];
        let clusters = cluster_objects_impl(&centers, 1.0);
        assert_eq!(clusters, vec![vec![0], vec![1]]);
    }

    #[test]
    fn find_pairs_volume_respects_ratio_range() {
        // 同位置,体积比 8/216 ≈ 0.037
        let centers = vec![[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]];
        let faces = vec![100, 6];
        let volumes = vec![8.0, 216.0];
        // 默认范围 (0.5, 2.0) 拒绝
        assert!(
            find_pairs_volume_impl(&centers, &faces, &volumes, 5.0, 0.0, 0.5, 2.0, 5.0).is_empty()
        );
        // 放宽到 (0.01, 0.1) 后配对,面数多者为 obj1
        let pairs = find_pairs_volume_impl(&centers, &faces, &volumes, 5.0, 0.0, 0.01, 0.1, 5.0);
        assert_eq!(pairs.len(), 1);
        assert_eq!(pairs[0].0, 0);
        assert_eq!(pairs[0].1, 1);
    }

    #[test]
    fn find_pairs_volume_skips_zero_face_objects() {
        // 0面物体同样不进入体积配对(边界防线,比例计算不会出现 0/0)
        let centers = vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]];
        let faces = vec![0, 4];
        let volumes = vec![1.0, 1.0];
        assert!(
            find_pairs_volume_impl(&centers, &faces, &volumes, 5.0, 0.0, 0.5, 2.0, 5.0).is_empty()
        );
    }
}
