//! L1.16 trailing-whitespace density: percentage of non-blank lines with trailing
//! whitespace. Ported from l1_analyzer.indicators._trailing_whitespace; validated equal.

use crate::{band, py_round2, py_splitlines, source_files, Indicator};
use std::path::Path;

const WS_EXTS: &[&str] = &[
    "py", "rs", "c", "h", "js", "jsx", "mjs", "cjs", "ts", "tsx", "java", "cs", "rb", "go",
];

pub fn analyze(repo: &Path) -> Indicator {
    let mut ws_lines = 0usize;
    let mut total = 0usize;
    for (_path, text) in source_files(repo, WS_EXTS) {
        for line in py_splitlines(&text) {
            total += 1;
            if line.trim_end() != line && !line.trim().is_empty() {
                ws_lines += 1;
            }
        }
    }
    let pct = if total > 0 { ws_lines as f64 / total as f64 * 100.0 } else { 0.0 };
    Indicator {
        code: "L1.16".into(),
        label: "trailing-whitespace".into(),
        value: py_round2(pct),
        band: band(pct, 0.5, 3.0, false).into(),
        details: format!("{ws_lines} lines with trailing ws"),
    }
}
