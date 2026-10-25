# Log Keputusan — Jejak JKN

Format: `K###` · tanggal · keputusan · alasan · status. Jangan hapus entri; tandai yang usang.

| ID | Tanggal | Keputusan | Alasan | Status |
|---|---|---|---|---|
| K001 | 2026-10-25 | Gunakan **data sintetis saja** (10k–50k klaim, skenario disuntikkan) | Tidak ada akses data asli; privasi peserta | Aktif |
| K002 | 2026-10-25 | **Tidak pakai Agile/Scrum penuh**; cukup daftar tugas mingguan | Tim kecil, waktu lomba terbatas | Aktif |
| K003 | 2026-10-25 | Mulai implementasi dari **generator data sintetis + rule engine** | Fondasi untuk semua engine lain dan bisa didemokan cepat | Aktif |
| K004 | 2026-10-25 | Bangun kode di **Claude Code**; Claude Design opsional untuk mockup UI | Claude Code bisa langsung kerja di folder proyek | Aktif |
| K005 | 2026-10-25 | Cakupan MVP mengikuti dokumen rekomendasi (lihat `00-konteks-proyek.md`); Neo4j/Postgres/Next.js ke roadmap | Fokus pada prototipe fungsional sebelum penjurian | Aktif |
| K006 | 2026-10-25 | Memori proyek disimpan sebagai Markdown di `docs/memory/` + `AGENTS.md` sebagai pintu masuk semua AI | Agar riwayat tidak hilang dan bisa dibaca AI mana pun | Aktif |
| K007 | 2026-10-25 | Repo GitHub: `kikykurniady/jejak-jkn`; memori di `main`, kode lewat branch + PR | Riwayat rapi, review sebelum merge | Aktif |
| K008 | 2026-10-25 | Kode Python di `src/jejak/` (pandas + Pandera), CLI `python -m jejak`; data hasil generate tidak di-commit (`data/` di .gitignore) | Data bisa dibuat ulang dari seed; repo tetap kecil | Aktif |
| K009 | 2026-10-25 | Label ground truth disimpan terpisah (`labels.csv`) dari klaim | Mencegah aturan/model "mengintip" label | Aktif |
| K010 | 2026-10-25 | Pandera hanya cek struktur/domain; kejanggalan bisnis ditangani rule engine | Klaim berisiko tidak boleh terbuang saat validasi | Aktif |
| K011 | 2026-10-25 | Skor aturan digabung noisy-OR `1 − Π(1 − bobot)`, tiap hit punya reason code + detail berbahasa Indonesia | Sederhana, terbatas 0–1, mudah dijelaskan ke auditor | Aktif |
| K012 | 2026-10-25 | XGBoost dilatih pada dataset sintetis **seed terpisah** dari data uji; eksperimen ditolak bila ada token peserta yang sama. Evaluasi juga *leave-one-scenario-out* | Mencegah kebocoran baris/peserta dan menunjukkan kinerja pada pola fraud yang belum dilabeli | Aktif |
| K013 | 2026-10-25 | XGBoost dan Isolation Forest default **tanpa fitur struktur** (`episode_n_claims`, `pf_visits`, `participant_n_facilities`); versi dengan fitur itu hanya ablasi | Generator membuat klaim suntikan sebagai episode baru 1 klaim (artefak); kinerja hampir sama dan alasan SHAP lebih bermakna | Aktif |
| K014 | 2026-10-25 | SHAP XGBoost lewat TreeSHAP bawaan (`pred_contribs`); SHAP Isolation Forest (`shap.TreeExplainer`) hanya untuk 1.000 klaim teratas; 3 kontribusi terbesar diubah ke kalimat Bahasa Indonesia | Cepat untuk semua klaim; SHAP IF lambat (±3 ms/klaim) | Aktif |
| K015 | 2026-10-25 | Process mining: case = episode, event `Rujukan FKTP` / `Layanan <tingkat>: <prosedur>` / `Klaim diajukan`; skor = 0,7·kelangkaan transisi + 0,3·(1 − fitness token replay Inductive Miner) | Bisa dijelaskan sebagai transisi langka; PM4Py berlisensi AGPL v3 (oke untuk lomba, catat bila dikomersialkan) | Aktif |
| K016 | 2026-10-25 | Graph antar-klaim: node = klaim, edge `duplikat` / `hampir_duplikat` / `kloning` (peserta berbeda, nominal ±2%) via blocking; klaim asal dari pasangan duplikat diberi skor konteks 0,3 | Salinan yang dinilai, bukan klaim aslinya; auditor tetap melihat pasangannya | Aktif |
| K017 | 2026-10-25 | PR-AUC dihitung **tie-aware** (skor sama = satu ambang); metrik selalu diurutkan per `claim_id` | Angka lama bergantung urutan baris; baseline aturan 20k seed 42 kini 0,936 (bukan 0,946) | Aktif |
