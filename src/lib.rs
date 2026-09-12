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
//! 已迁入:简单配对算法(#20)。聚类/体积算法随后续提交迁入。

use pyo3::prelude::*;

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
}
