# Prompt Handoff untuk AI berbasis chat

Pakai ini di ChatGPT, Claude.ai, Claude Design, atau AI lain yang tidak bisa membaca folder.

## 1. Awal sesi — tempel ini, lalu lampirkan/tempel isi file memori
```
Kamu membantu proyek JEJAK-JKN (BPJS Healthkathon 2026). Berikut memori proyek:
AGENTS.md, 00-konteks-proyek.md, 01-keputusan.md, 02-status-dan-tugas.md, dan ringkasan sesi terakhir.
Baca semuanya dulu. Ikuti keputusan yang sudah ada kecuali saya minta mengubahnya.
Jawab dalam Bahasa Indonesia. Gunakan data sintetis saja.
Tugas hari ini: <isi>
```

## 2. Akhir sesi — minta ringkasan, lalu simpan ke `docs/memory/sesi/`
```
Ringkas sesi ini untuk memori proyek dengan format persis berikut (Markdown):
# Sesi <YYYY-MM-DD> — <topik>
- AI/alat: <nama>
## Tujuan sesi
## Yang dikerjakan / dibahas
## Keputusan (format tabel: ID | Tanggal | Keputusan | Alasan | Status, lanjutkan nomor K terakhir)
## Hasil & tautan
## Tugas lanjutan (checklist)
Hanya fakta penting, tanpa transkrip. Tanggal absolut.
```
Lalu: simpan sebagai `sesi/YYYY-MM-DD-topik.md`, tambahkan baris keputusan ke `01-keputusan.md`,
dan perbarui `02-status-dan-tugas.md`.
