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
//! 当前为骨架提交:仅模块初始化与共用的纯数学函数,
//! 三种配对算法随后续提交逐一迁入。

use pyo3::prelude::*;

/// 计算两个包围盒中心点之间的欧氏距离
///
/// 内核各算法共用的纯函数,置于骨架提交以便独立单测。
/// 骨架期只有测试引用它;#20 起被各算法内核调用后此允许即可移除。
#[allow(dead_code)]
fn center_distance(a: [f64; 3], b: [f64; 3]) -> f64 {
    let dx = a[0] - b[0];
    let dy = a[1] - b[1];
    let dz = a[2] - b[2];
    (dx * dx + dy * dy + dz * dz).sqrt()
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
}
