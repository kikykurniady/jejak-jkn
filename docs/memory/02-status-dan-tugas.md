# Status & Tugas — Jejak JKN
_Terakhir diperbarui: 2026-10-25_

## Posisi sekarang
- Proposal: bagian 1–5 selesai (draf), 6–9 belum.
- Repo: https://github.com/kikykurniady/jejak-jkn (memori di `main`; kode di branch `feat/generator-rule-engine`).
- **Sudah ada:** generator data sintetis (10k–50k klaim, 6 skenario berlabel), validasi Pandera,
  rule engine R01–R10 dengan reason code, evaluasi (P/R/F1, PR-AUC, P@K, R@K), 10 tes pytest.
- Hasil awal (20k klaim, seed 42): precision 0,94, recall 0,93 pada ambang 0,5, PR-AUC 0,95.
  Ini batas atas karena aturan dan skenario dibuat tim yang sama.

## Tugas berikutnya
- [ ] Push branch dan merge PR generator + rule engine
- [ ] Similarity berbasis fitur untuk cloning/near-dup yang lebih halus (bukan hanya nominal identik)
- [ ] Graf NetworkX peserta–faskes–episode + fitur graf
- [ ] Isolation Forest untuk anomali; risk fusion (aturan + anomali + graf)
- [ ] Skenario lebih sulit/variatif agar evaluasi tidak sirkular (mis. cloning dengan nominal sedikit berbeda)
- [ ] Selaraskan kolom dengan data sampel resmi BPJS (FKRTL 55 variabel)
- [ ] Streamlit auditor workspace (risk queue, detail kasus, reason code)
- [ ] Lengkapi proposal bagian 6–9 dan tambahkan cakupan **Cloning**
- [ ] Cari statistik publik JKN yang terverifikasi untuk proposal

## Pertanyaan terbuka
- Tenggat penjurian & format final? (cek `Panduan Project Final Healthkathon 2026.pdf`)
- Siapa saja anggota tim dan pembagian perannya?
