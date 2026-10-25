# AGENTS.md — Jejak JKN

> File ini adalah pintu masuk untuk **semua asisten AI** (Claude Code, Cursor, Codex, Gemini, ChatGPT, Copilot, dll).
> Baca file ini dulu, lalu baca `docs/memory/` sebelum mulai bekerja.

## Proyek singkat
**JEJAK-JKN: Process-Aware Graph Intelligence for Smarter JKN Protection** — entri lomba BPJS Healthkathon 2026.
Membantu auditor JKN **memprioritaskan klaim berisiko** lewat analisis proses layanan, hubungan antar-klaim,
pola pengulangan, dan anomali. Output: **risk score + alasan yang bisa dijelaskan** per klaim untuk
Phantom Billing, Repeat Billing, dan Cloning. Sistem **mendukung, tidak menggantikan**, keputusan auditor.

## Wajib dibaca (urut)
1. `docs/memory/00-konteks-proyek.md` — tujuan, arsitektur, stack, data, metrik
2. `docs/memory/01-keputusan.md` — keputusan yang sudah diambil (jangan diulang-debat tanpa alasan baru)
3. `docs/memory/02-status-dan-tugas.md` — posisi terakhir dan tugas berikutnya
4. File terbaru di `docs/memory/sesi/` — ringkasan percakapan terakhir

## Aturan kerja untuk AI
- Pengguna menulis dalam **Bahasa Indonesia**; jawab dalam Bahasa Indonesia kecuali diminta lain.
- Gunakan **data sintetis saja**. Jangan pernah memasukkan data peserta JKN asli/PII.
- Jangan ubah keputusan di `01-keputusan.md` diam-diam. Jika perlu berubah, tambahkan entri baru yang menggantikan entri lama.
- **Di akhir setiap sesi kerja**, perbarui memori:
  - buat ringkasan sesi baru di `docs/memory/sesi/YYYY-MM-DD-topik.md` (pakai `sesi/_TEMPLATE.md`),
  - tambahkan keputusan baru ke `01-keputusan.md`,
  - perbarui `02-status-dan-tugas.md`.
- Tulis fakta, bukan transkrip lengkap. Ringkas, tanggal absolut (YYYY-MM-DD), sebut sumber/tautan.
- Jangan simpan rahasia (API key, password, token) di folder memori.
