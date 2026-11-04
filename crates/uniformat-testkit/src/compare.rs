//! Comparaison valeur à valeur avec la tolérance de la spécification.

/// Tolérance relative sur les flottants : les CSV de référence portent 14 chiffres significatifs (`10` §5.2).
pub const REL_TOL: f64 = 1e-13;

/// Égalité de deux cellules de CSV : texte identique, ou nombres égaux à `REL_TOL` près.
///
/// Les manquants SAS (`.`, `_`, `A`-`Z`) se comparent comme du texte.
pub fn values_equal(expected: &str, got: &str) -> bool {
    if expected == got {
        return true;
    }
    match (expected.trim().parse::<f64>(), got.trim().parse::<f64>()) {
        (Ok(a), Ok(b)) => {
            if a == b {
                return true;
            }
            let scale = a.abs().max(b.abs());
            (a - b).abs() <= REL_TOL * scale
        }
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identical_text() {
        assert!(values_equal("abc", "abc"));
        assert!(values_equal(".", "."));
    }

    #[test]
    fn numbers_within_tolerance() {
        assert!(values_equal("1.00000000000000", "1"));
        assert!(values_equal("3.14159265358979", "3.141592653589790001"));
        assert!(!values_equal("1.0", "1.0001"));
    }

    #[test]
    fn text_and_numbers_do_not_mix() {
        assert!(!values_equal("a", "1"));
        assert!(!values_equal(".", "0"));
    }
}
