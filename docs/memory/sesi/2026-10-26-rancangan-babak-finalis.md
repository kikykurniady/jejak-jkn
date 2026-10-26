# Sesi 2026-10-26 — Rancangan perbaikan menuju kurasi 20 finalis
- **AI/alat:** Claude Code (desktop)
- **Peserta:** pemilik laptop

## Tujuan sesi
Pengguna merasa sistem belum layak lolos babak berikutnya; minta rancangan yang cocok.

## Yang dikerjakan / dibahas
- Baca `Doc/Healthkathon 2026 - Alur Kegiatan Healthkathon.pdf` dan `Doc/Panduan Project Final Healthkathon 2026.pdf`.
  - Tenggat video + demo: **2026-11-01** (YouTube unlisted/private, maks. 10 menit, demo harus aplikasi berjalan).
  - 145 tim → 20 finalis (kurasi 2–4 Nov) → coaching 5–13 Nov → submit final 14–15 Nov → 5 tim Demo Day 21 Nov.
  - Kriteria: Kreativitas & Keunikan (GenAI/ML), Model Bisnis, Dampak terukur, Presentasi, Kesiapan Produk.
- Analisis celah: belum ada GenAI, skor masih "sementara" (K019), belum ada angka dampak (Rupiah/beban kerja),
  belum bisa menerima data berformat data sampel BPJS, tidak ada API/Docker, belum ada tampilan tingkat faskes.
- Usulan rancangan 6 hari (menunggu persetujuan pengguna): adapter data sampel BPJS, risk fusion final,
  halaman dampak, profil risiko faskes, asisten auditor GenAI (ringkasan kasus + draf surat klarifikasi, dengan guardrail),
  FastAPI + Docker, lalu naskah demo + rekam video.

- Pengguna menerima data sampel resmi BPJS dengan syarat: hanya untuk Healthkathon, tidak disebarluaskan,
  jangan identifikasi individu/faskes/badan usaha, publikasi hanya agregat atau sintetis.
- Pemindaian kode (ruff, bandit, pip-audit, pytest-cov): tidak ada celah keamanan/dependensi rentan;
  cakupan tes 63%, `app.py` dan `cli.py` 0%.
- Dibahas alat fraud tambahan (DuckDB, Splink, PyOD, Benford, SDV, EBM, igraph, Claude API).

## Keputusan (salin juga ke 01-keputusan.md)
- K023 metode Hybrid Lean + Kanban · K024 alat perancangan · K025 alat fraud tambahan · K026 aturan data BPJS.

## Tugas lanjutan (salin juga ke 02-status-dan-tugas.md)
- [ ] Buat papan GitHub Projects dengan kartu MoSCoW (21 kartu sudah dirancang; tertunda karena token gh belum
      punya scope `project` → pemilik perlu `gh auth refresh -s project`)
- [x] Perketat `.gitignore` (xlsx, zip, folder `*bpjs*/`, model, notebook). Catatan: repo `kikykurniady/jejak-jkn` **PUBLIK**.
- [ ] Profil kolom data BPJS (agregat saja)
