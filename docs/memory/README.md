# Memori Proyek Jejak JKN

Folder ini adalah **ingatan jangka panjang** proyek, berupa file Markdown biasa supaya bisa dibaca
oleh AI mana pun dan oleh manusia, serta aman disimpan di Git.

| File | Isi | Kapan diperbarui |
|---|---|---|
| `00-konteks-proyek.md` | Tujuan, arsitektur, stack, data, metrik | Saat desain berubah |
| `01-keputusan.md` | Log keputusan (siapa/kapan/kenapa) | Setiap ada keputusan |
| `02-status-dan-tugas.md` | Status terkini + daftar tugas mingguan | Akhir setiap sesi |
| `sesi/` | Ringkasan per sesi percakapan | Akhir setiap sesi |
| `PROMPT-HANDOFF.md` | Prompt siap-tempel untuk AI di luar folder ini | Jarang |

## Cara pakai
- **AI yang bisa membaca folder** (Claude Code, Cursor, Codex, Gemini CLI): otomatis membaca `AGENTS.md`/`CLAUDE.md`.
  Cukup minta: *"Baca memori proyek lalu lanjutkan."* dan di akhir: *"Perbarui memori proyek."*
- **AI berbasis chat** (ChatGPT, Claude.ai, Claude Design): pakai prompt di `PROMPT-HANDOFF.md` —
  tempel konteks di awal, minta ringkasan sesi di akhir, lalu simpan hasilnya ke `sesi/`.

## Prinsip
- Satu file per topik, ringkas, tanggal absolut.
- Keputusan tidak dihapus; yang usang ditandai *Digantikan oleh KXXX*.
- Tanpa data pribadi dan tanpa rahasia.
