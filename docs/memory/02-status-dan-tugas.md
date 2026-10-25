# Status & Tugas — Jejak JKN
_Terakhir diperbarui: 2026-10-25_

## Posisi sekarang
- Proposal: bagian 1–5 selesai (draf), 6–9 belum.
- Repo: https://github.com/kikykurniady/jejak-jkn. PR #1 (generator + rule engine) sudah merge ke `main`.
- **Sudah ada:** generator data sintetis (6 skenario berlabel), validasi Pandera, rule engine R01–R10,
  evaluasi (P/R/F1, PR-AUC tie-aware, P@K, R@K).
- **Baru (branch `claude/project-thread-rgp8xj`, PR menunggu review):** process mining PM4Py (`process.py`),
  graph antar-klaim NetworkX (`graph.py`), 20 fitur (`features.py`), Isolation Forest + XGBoost + SHAP
  dengan alasan Bahasa Indonesia (`models.py`), eksperimen jujur (`experiment.py`), CLI `python -m jejak ml`,
  24 tes pytest.
- Hasil 20k klaim uji (seed 42), XGBoost dilatih di seed 1042 — PR-AUC: aturan 0,936 · process 0,444 ·
  graph 0,517 · Isolation Forest 0,877 · XGBoost 0,998 (sirkular). Leave-one-scenario-out: recall XGBoost
  pada skenario yang tidak dilatih hanya 0,03–0,37. Detail: README bagian "Engine lanjutan".

## Tugas berikutnya
- [ ] Review & merge PR model risiko / process mining / graph
- [ ] **Risk fusion**: gabungkan aturan + Isolation Forest + process + graph (+ XGBoost bila pola sudah dilabeli) jadi satu skor dan satu daftar alasan
- [ ] Skenario lebih sulit/variatif agar evaluasi tidak sirkular (cloning nominal sedikit beda, phantom dengan konsultasi FKTP palsu, episode suntikan yang menempel ke episode lama)
- [ ] Streamlit auditor workspace (risk queue, detail kasus, timeline proses, graf, reason code, keputusan auditor)
- [ ] Selaraskan kolom dengan data sampel resmi BPJS (FKRTL 55 variabel)
- [ ] Lengkapi proposal bagian 6–9, cakupan **Cloning**, dan tabel hasil evaluasi jujur
- [ ] Cari statistik publik JKN yang terverifikasi untuk proposal

## Pertanyaan terbuka
- Tenggat penjurian & format final? (cek `Panduan Project Final Healthkathon 2026.pdf`)
- Siapa saja anggota tim dan pembagian perannya?
