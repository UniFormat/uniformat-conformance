//! CSV de référence produit par SAS, relu **par nom de colonne** (l'ordre du CSV n'est pas celui du fichier, `10` §0).

use std::collections::HashMap;
use std::fmt;

/// Erreur de lecture d'un CSV de référence.
#[derive(Debug, PartialEq, Eq)]
pub enum CsvError {
    /// Guillemet ouvert jamais refermé.
    UnterminatedQuote,
    /// Entête absente.
    Empty,
    /// Ligne dont le nombre de cellules diffère de l'entête (numéro 1-base, ligne de données).
    RaggedRow {
        /// Numéro (base 1) de la ligne de données.
        row: usize,
        /// Nombre de cellules de l'entête.
        expected: usize,
        /// Nombre de cellules de la ligne.
        got: usize,
    },
    /// Deux colonnes portent le même nom (comparaison par nom impossible).
    DuplicateColumn(String),
}

impl fmt::Display for CsvError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnterminatedQuote => write!(f, "guillemet non refermé"),
            Self::Empty => write!(f, "CSV sans entête"),
            Self::RaggedRow { row, expected, got } => {
                write!(f, "ligne {row} : {got} cellules au lieu de {expected}")
            }
            Self::DuplicateColumn(c) => write!(f, "nom de colonne en double : {c}"),
        }
    }
}

impl std::error::Error for CsvError {}

/// Table de référence : entête et lignes de cellules textuelles.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReferenceTable {
    columns: Vec<String>,
    rows: Vec<Vec<String>>,
    index: HashMap<String, usize>,
}

impl ReferenceTable {
    /// Lit un CSV depuis des octets. Les CSV de `files/` suivent l'encodage de la table (latin1, Shift-JIS…) :
    /// si le contenu n'est pas de l'UTF-8 valide, chaque octet devient le caractère Unicode de même valeur
    /// (Latin-1), ce qui est sans perte — `str.chars().map(|c| c as u8)` redonne les octets d'origine.
    pub fn parse_bytes(bytes: &[u8]) -> Result<Self, CsvError> {
        match std::str::from_utf8(bytes) {
            Ok(text) => Self::parse(text),
            Err(_) => Self::parse(&bytes.iter().map(|&b| char::from(b)).collect::<String>()),
        }
    }

    /// Analyse un CSV (RFC 4180 : guillemets doublés, fins de ligne `\n` ou `\r\n`, sauts de ligne dans les guillemets).
    pub fn parse(text: &str) -> Result<Self, CsvError> {
        let mut records = parse_records(text)?;
        if records.is_empty() {
            return Err(CsvError::Empty);
        }
        let columns = records.remove(0);
        let mut index = HashMap::with_capacity(columns.len());
        for (i, name) in columns.iter().enumerate() {
            if index.insert(name.clone(), i).is_some() {
                return Err(CsvError::DuplicateColumn(name.clone()));
            }
        }
        for (r, row) in records.iter().enumerate() {
            if row.len() != columns.len() {
                return Err(CsvError::RaggedRow {
                    row: r + 1,
                    expected: columns.len(),
                    got: row.len(),
                });
            }
        }
        Ok(Self {
            columns,
            rows: records,
            index,
        })
    }

    /// Noms de colonnes, dans l'ordre du CSV.
    pub fn columns(&self) -> &[String] {
        &self.columns
    }

    /// Nombre de lignes de données.
    pub fn row_count(&self) -> usize {
        self.rows.len()
    }

    /// Cellule `(ligne, colonne par nom)`.
    pub fn cell(&self, row: usize, column: &str) -> Option<&str> {
        let c = *self.index.get(column)?;
        self.rows.get(row)?.get(c).map(String::as_str)
    }
}

fn parse_records(text: &str) -> Result<Vec<Vec<String>>, CsvError> {
    let mut records = Vec::new();
    let mut row: Vec<String> = Vec::new();
    let mut cell = String::new();
    let mut in_quotes = false;
    let mut chars = text.chars().peekable();
    let mut pending = false; // une ligne est en cours (cellule vide finale comprise)
    while let Some(ch) = chars.next() {
        if in_quotes {
            if ch == '"' {
                if chars.peek() == Some(&'"') {
                    cell.push('"');
                    chars.next();
                } else {
                    in_quotes = false;
                }
            } else {
                cell.push(ch);
            }
            continue;
        }
        match ch {
            '"' => {
                in_quotes = true;
                pending = true;
            }
            ',' => {
                row.push(std::mem::take(&mut cell));
                pending = true;
            }
            '\r' => {}
            '\n' => {
                if pending || !cell.is_empty() {
                    row.push(std::mem::take(&mut cell));
                    records.push(std::mem::take(&mut row));
                }
                pending = false;
            }
            other => {
                cell.push(other);
                pending = true;
            }
        }
    }
    if in_quotes {
        return Err(CsvError::UnterminatedQuote);
    }
    if pending || !cell.is_empty() {
        row.push(cell);
        records.push(row);
    }
    Ok(records)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_by_column_name_not_position() {
        let t = ReferenceTable::parse("i,x,c\n1,2.5,abc\n2,.,\"a,b\"\n").unwrap();
        assert_eq!(t.row_count(), 2);
        assert_eq!(t.cell(0, "c"), Some("abc"));
        assert_eq!(t.cell(1, "x"), Some("."));
        assert_eq!(t.cell(1, "c"), Some("a,b"));
        assert_eq!(t.cell(2, "c"), None);
        assert_eq!(t.cell(0, "z"), None);
    }

    #[test]
    fn header_only_table_has_zero_rows() {
        let t = ReferenceTable::parse("i,x,c\n").unwrap();
        assert_eq!(t.row_count(), 0);
        assert_eq!(t.columns(), ["i", "x", "c"]);
    }

    #[test]
    fn quoted_newline_and_doubled_quote() {
        let t = ReferenceTable::parse("a\r\n\"x\r\ny\"\"z\"\r\n").unwrap();
        assert_eq!(t.cell(0, "a"), Some("x\r\ny\"z"));
    }

    #[test]
    fn empty_trailing_cell_is_kept() {
        let t = ReferenceTable::parse("a,b\n1,\n").unwrap();
        assert_eq!(t.cell(0, "b"), Some(""));
    }

    #[test]
    fn non_utf8_bytes_are_kept_losslessly() {
        let t = ReferenceTable::parse_bytes(b"a\n\xe9\x82\n").unwrap();
        let cell = t.cell(0, "a").unwrap();
        assert_eq!(
            cell.chars().map(|c| c as u8).collect::<Vec<_>>(),
            [0xe9, 0x82]
        );
        let t = ReferenceTable::parse_bytes("a\n\u{e9}\n".as_bytes()).unwrap();
        assert_eq!(t.cell(0, "a"), Some("\u{e9}"));
    }

    #[test]
    fn errors() {
        assert_eq!(ReferenceTable::parse("").unwrap_err(), CsvError::Empty);
        assert_eq!(
            ReferenceTable::parse("a\n\"x").unwrap_err(),
            CsvError::UnterminatedQuote
        );
        assert_eq!(
            ReferenceTable::parse("a,b\n1\n").unwrap_err(),
            CsvError::RaggedRow {
                row: 1,
                expected: 2,
                got: 1
            }
        );
        assert_eq!(
            ReferenceTable::parse("a,a\n").unwrap_err(),
            CsvError::DuplicateColumn("a".into())
        );
    }
}
