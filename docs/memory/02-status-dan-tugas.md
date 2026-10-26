# Status & Tugas — Jejak JKN
_Terakhir diperbarui: 2026-10-26_

- 2026-10-26: laptop MacBook Intel siap dipakai (Python 3.15, `.venv` lengkap, 30/30 tes lulus). XGBoost memakai
  libomp dari conda-forge di `.venv/lib/` (K022, langkah di README "Mac Intel").

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
- **Baru (branch `claude/project-thread-453ct5`, bercabang dari PR #2):** auditor workspace Streamlit —
  antrean prioritas, detail kasus (reason code aturan + SHAP + process + graph), timeline, graf hubungan,
  keputusan auditor tersimpan lokal. Satu perintah: `python -m jejak demo` (±30 detik dari nol). Skor yang dipakai
  masih **skor gabungan sementara** (K019). 30 tes pytest.

## Tugas berikutnya
- [ ] Review & merge PR model risiko / process mining / graph
- [ ] **Risk fusion**: gabungkan aturan + Isolation Forest + process + graph (+ XGBoost bila pola sudah dilabeli) jadi satu skor dan satu daftar alasan
- [ ] Skenario lebih sulit/variatif agar evaluasi tidak sirkular (cloning nominal sedikit beda, phantom dengan konsultasi FKTP palsu, episode suntikan yang menempel ke episode lama)
- [x] Streamlit auditor workspace (risk queue, detail kasus, timeline proses, graf, reason code, keputusan auditor) — PR dashboard
- [ ] Merge PR dashboard setelah PR #2 (PR dashboard bercabang dari PR #2)
- [ ] Ganti skor gabungan sementara dengan risk fusion; pakai log keputusan auditor sebagai label umpan balik
- [ ] Latihan demo: skenario cerita 3 kasus (repeat, phantom, cloning) untuk presentasi juri
- [ ] Selaraskan kolom dengan data sampel resmi BPJS (FKRTL 55 variabel)
- [ ] Lengkapi proposal bagian 6–9, cakupan **Cloning**, dan tabel hasil evaluasi jujur
- [ ] Cari statistik publik JKN yang terverifikasi untuk proposal

## Pertanyaan terbuka
- Tenggat penjurian & format final? (cek `Panduan Project Final Healthkathon 2026.pdf`)
- Siapa saja anggota tim dan pembagian perannya?
