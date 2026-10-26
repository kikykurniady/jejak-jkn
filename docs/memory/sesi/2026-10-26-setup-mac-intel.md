# Sesi 2026-10-26 — Setup laptop MacBook Intel
- **AI/alat:** Claude Code (desktop)
- **Peserta:** pemilik laptop

## Tujuan sesi
Mengetahui apa yang perlu dipasang agar proyek jalan di laptop ini.

## Yang dikerjakan / dibahas
- Cek awal: Python 3.15, Git, `.venv` berisi semua paket proyek; 27/30 tes lulus, 3 gagal karena XGBoost tidak bisa memuat `libomp.dylib`.
- Homebrew gagal dipasang: "only supported on Apple Silicon".
- libomp bawaan scikit-learn (LLVM OMP 2014) terlalu lama: tidak ada simbol `__kmpc_dispatch_deinit`.
- Unduh `llvm-openmp-23.1.3-h8c1e6b9_0.conda` (osx-64) dari conda-forge (md5 cocok), ekstrak `libomp.dylib` ke `.venv/lib/`, tambah rpath di `libxgboost.dylib` + codesign ad-hoc.

## Keputusan (salin juga ke 01-keputusan.md)
- K022: sumber libomp untuk Mac Intel = conda-forge `llvm-openmp`, dipasang di `.venv/lib/`.

## Hasil & tautan (file, artefak, commit)
- 30/30 tes pytest lulus.
- README bagian "Mac Intel (tanpa Homebrew)" berisi langkah ulang.

## Tugas lanjutan (salin juga ke 02-status-dan-tugas.md)
- [ ] Ulangi langkah rpath bila XGBoost dipasang ulang atau venv dibuat ulang.
