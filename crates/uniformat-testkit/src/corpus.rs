//! Découverte des fichiers du corpus (`UNIFORMAT_CORPUS`) et de leurs références.

use std::fs;
use std::io;
use std::path::{Path, PathBuf};

/// Variable d'environnement qui active les tests d'intégration sur le corpus.
pub const ENV_CORPUS: &str = "UNIFORMAT_CORPUS";
/// Former name of [`ENV_CORPUS`], still accepted.
pub const LEGACY_ENV_CORPUS: &str = "SAS7BDAT_CORPUS";

/// Un fichier `.sas7bdat` du corpus et ses références voisines.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CorpusFile {
    /// Chemin du `.sas7bdat`.
    pub path: PathBuf,
    /// Dossier racine (`files` ou `external`) puis sous-dossier : la famille (`base`, `compression`, `datareader`…).
    pub family: String,
    /// CSV de référence de même nom, s'il existe.
    pub csv: Option<PathBuf>,
    /// Sortie `PROC CONTENTS` de même nom (`<nom>.contents.txt`), si elle existe.
    pub contents: Option<PathBuf>,
}

impl CorpusFile {
    /// Nom du fichier sans extension.
    pub fn stem(&self) -> String {
        self.path
            .file_stem()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_default()
    }
}

/// Le corpus de référence, tel que `corpus/MANIFEST.md` le décrit.
#[derive(Debug, Clone)]
pub struct Corpus {
    root: PathBuf,
}

impl Corpus {
    /// Corpus désigné par `UNIFORMAT_CORPUS`, ou `None` si la variable est absente ou si le dossier n'existe pas.
    pub fn from_env() -> Option<Self> {
        let root = PathBuf::from(
            std::env::var_os(ENV_CORPUS).or_else(|| std::env::var_os(LEGACY_ENV_CORPUS))?,
        );
        root.is_dir().then_some(Self { root })
    }

    /// Corpus ouvert depuis un dossier explicite.
    pub fn open(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    /// Dossier racine.
    pub fn root(&self) -> &Path {
        &self.root
    }

    /// Fichiers `.sas7bdat` de `files/` (SAS complet) et `external/` (fichiers publics), triés par chemin.
    ///
    /// Les dossiers `files_sas_small`, `files_complement*` ne font pas partie des 232 fichiers analysés par `10` §9.
    pub fn files(&self) -> io::Result<Vec<CorpusFile>> {
        let mut out = Vec::new();
        for top in ["files", "external"] {
            let dir = self.root.join(top);
            if dir.is_dir() {
                collect(&dir, top, &mut out)?;
            }
        }
        out.sort_by(|a, b| a.path.cmp(&b.path));
        self.attach_shared_csv(&mut out);
        Ok(out)
    }

    /// Les fichiers publics `datareader/testN` partagent le CSV de leur jeu de données (`dataset A (test1.csv)`
    /// dans la colonne `note` de `external/EXTERNAL.tsv`). Cette indication prime sur le CSV de même nom :
    /// `test2.sas7bdat` est du jeu A alors que `test2.csv` est le CSV du jeu B.
    fn attach_shared_csv(&self, files: &mut [CorpusFile]) {
        let Ok(tsv) = fs::read_to_string(self.root.join("external").join("EXTERNAL.tsv")) else {
            return;
        };
        for line in tsv.lines().skip(1) {
            let cols: Vec<&str> = line.split('\t').collect();
            let (Some(rel), Some(note)) = (cols.first(), cols.get(8)) else {
                continue;
            };
            let Some(csv_name) = note
                .split('(')
                .skip(1)
                .find_map(|part| part.split(')').next().filter(|n| n.ends_with(".csv")))
            else {
                continue;
            };
            let path = self.root.join(rel);
            if let Some(f) = files.iter_mut().find(|f| f.path == path) {
                let csv = path.with_file_name(csv_name);
                f.csv = csv.is_file().then_some(csv);
            }
        }
    }
}

fn collect(dir: &Path, family: &str, out: &mut Vec<CorpusFile>) -> io::Result<()> {
    for entry in fs::read_dir(dir)? {
        let path = entry?.path();
        if path.is_dir() {
            let sub = path
                .file_name()
                .map(|s| s.to_string_lossy().into_owned())
                .unwrap_or_default();
            collect(&path, &sub, out)?;
        } else if path.extension().is_some_and(|e| e == "sas7bdat") {
            let sibling = |ext: &str| {
                let p = path.with_extension(ext);
                p.is_file().then_some(p)
            };
            let contents = path.file_stem().and_then(|stem| {
                let p = path.with_file_name(format!("{}.contents.txt", stem.to_string_lossy()));
                p.is_file().then_some(p)
            });
            out.push(CorpusFile {
                csv: sibling("csv"),
                contents,
                family: family.to_owned(),
                path,
            });
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmpdir(tag: &str) -> PathBuf {
        let d =
            std::env::temp_dir().join(format!("uniformat-testkit-{tag}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn finds_files_and_siblings() {
        let root = tmpdir("find");
        fs::create_dir_all(root.join("files/base")).unwrap();
        fs::create_dir_all(root.join("external/pandas")).unwrap();
        fs::create_dir_all(root.join("files_complement")).unwrap();
        fs::write(root.join("files/base/a.sas7bdat"), b"x").unwrap();
        fs::write(root.join("files/base/a.csv"), b"i\n").unwrap();
        fs::write(root.join("files/base/a.contents.txt"), b"c").unwrap();
        fs::write(root.join("external/pandas/b.sas7bdat"), b"x").unwrap();
        fs::write(root.join("files_complement/c.sas7bdat"), b"x").unwrap();
        let files = Corpus::open(&root).files().unwrap();
        assert_eq!(files.len(), 2);
        assert_eq!(files[0].family, "pandas");
        assert!(files[0].csv.is_none());
        assert_eq!(files[1].family, "base");
        assert!(files[1].csv.is_some() && files[1].contents.is_some());
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn missing_dirs_give_empty_inventory() {
        let root = tmpdir("empty");
        assert!(Corpus::open(&root).files().unwrap().is_empty());
        let _ = fs::remove_dir_all(&root);
    }
}
