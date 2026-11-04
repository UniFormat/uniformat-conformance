//! Harnais de tests d'intégration sur le corpus de `corpus/MANIFEST.md` (`docs/architecture.md` §6.1).
//!
//! Les fichiers du corpus produits par le SAS complet ne sont pas redistribués (ADR 0007) :
//! les tests s'activent par `UNIFORMAT_CORPUS=<dossier corpus>` et se sautent sinon.
#![forbid(unsafe_code)]

pub mod compare;
pub mod corpus;
pub mod csv;

pub use compare::{values_equal, REL_TOL};
pub use corpus::{Corpus, CorpusFile};
pub use csv::ReferenceTable;
