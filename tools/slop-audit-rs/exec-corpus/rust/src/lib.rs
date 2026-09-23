//! Two branches, one of them exercised, so coverage is a fraction rather than nought or one.

pub fn band(n: i32) -> &'static str {
    if n < 0 {
        "neg"
    } else {
        "pos"
    }
}

/// Never called by a test, so the run has a region it did not reach.
pub fn halve_or_climb(n: i32) -> i32 {
    if n % 2 == 0 {
        n / 2
    } else {
        n * 3 + 1
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_positive_number_is_positive() {
        assert_eq!(band(3), "pos");
    }
}
