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
