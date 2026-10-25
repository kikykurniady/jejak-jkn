# Sesi 2026-10-25 — Model risiko (XGBoost, Isolation Forest, SHAP), process mining, graph antar-klaim
- **AI/alat:** Claude Code (thread proyek "Bangun model risiko dan graph klaim")
- **Peserta:** pemilik proyek

## Tujuan sesi
Membangun engine berikutnya di atas generator + rule engine: model risiko dengan penjelasan SHAP,
process mining PM4Py, dan graph antar-klaim NetworkX, lalu membandingkannya secara jujur dengan baseline aturan.

## Yang dikerjakan / dibahas
- Modul baru di `src/jejak/`: `process.py`, `graph.py`, `features.py`, `models.py`, `experiment.py`; CLI `ml`.
- Dependensi baru: scikit-learn, xgboost, shap, networkx, pm4py.
- Ditemukan artefak generator: skenario suntikan selalu episode baru berisi 1 klaim dan peserta jarang datang
  ke faskes itu. XGBoost langsung memakai `episode_n_claims` sebagai alasan teratas → fitur struktur dikeluarkan (K013).
- Bug yang ditemukan tes: fitur frekuensi prosedur dan R03 bergantung urutan baris saat waktu layanan sama
  (kini tie-break `claim_id`); edge `hampir_duplikat` membuat baris kosong saat tidak ada pasangan.
- PR-AUC lama bergantung urutan baris pada skor yang sama; kini tie-aware (K017).

## Keputusan
K012–K017 (lihat `01-keputusan.md`).

## Hasil & tautan
- Branch `claude/project-thread-rgp8xj`, PR ke `main`.
- 20k klaim uji seed 42 / latih seed 1042, PR-AUC: aturan 0,936, process 0,444, graph 0,517, Isolation Forest 0,877,
  XGBoost 0,998. Leave-one-scenario-out XGBoost: recall 0,03–0,37 → XGBoost hanya andal untuk pola yang sudah dilabeli.
- Process mining kuat di `process_deviation` (recall 0,69); graph di duplikat + kloning (recall 1,00).

## Tugas lanjutan
Lihat `02-status-dan-tugas.md` (risk fusion, skenario lebih sulit, Streamlit).
