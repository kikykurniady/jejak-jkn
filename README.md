# jejak-jkn

**JEJAK-JKN: Process-Aware Graph Intelligence for Smarter JKN Protection** — entri BPJS Healthkathon 2026.

Membantu auditor JKN memprioritaskan klaim berisiko (Phantom Billing, Repeat Billing, Cloning)
dengan risk score dan alasan yang bisa dijelaskan. Semua data di repo ini **sintetis**.

Untuk asisten AI: mulai dari [`AGENTS.md`](AGENTS.md) dan [`docs/memory/`](docs/memory/).

## Menjalankan

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m jejak pipeline --n 20000 --seed 42 --out data   # generate → validate → rules → evaluate
.venv/bin/python -m pytest
```

Perintah terpisah: `generate`, `validate`, `rules`, `evaluate` (lihat `python -m jejak -h`).
Hasil di `data/` (tidak di-commit): `claims.csv`, `labels.csv`, `facilities.csv`, `participants.csv`,
`rule_hits.csv` (satu baris per alasan), `rule_scores.csv` (satu baris per klaim, terurut skor).

## Data sintetis (`src/jejak/generator.py`)

Klaim normal dibentuk dari episode layanan: kunjungan tunggal FKTP, kontrol kronis, seri fisioterapi
dan hemodialisis, serta konsultasi FKTP lalu rujukan ke FKRTL. Derau realistis ditambahkan
(±1,5% klaim sah tanpa bukti, ±1% FKRTL tanpa rujukan) supaya aturan tidak sempurna.

| Kolom | Isi |
|---|---|
| `claim_id`, `episode_id` | ID klaim dan episode layanan |
| `participant_token` | token pseudonim peserta (bukan NIK/no. kartu) |
| `facility_id`, `facility_type` | faskes `FKTP-xxxx` / `FKRTL-xxxx` |
| `diagnosis_code`, `procedure_code` | ICD-10 dan ICD-9-CM dari katalog kecil (`catalog.py`) |
| `service_type`, `los_days`, `referral_flag` | RJ/RI, lama rawat, ada rujukan |
| `service_timestamp`, `claim_timestamp` | waktu layanan dan waktu pengajuan klaim |
| `claim_amount`, `evidence_flag` | nominal (rupiah) dan kelengkapan bukti layanan |

Skenario yang disuntikkan (label di `labels.csv`, terpisah dari klaim):

| Skenario | Jenis | Cara dibuat |
|---|---|---|
| `exact_duplicate` | repeat | salinan persis klaim lain, diajukan belakangan |
| `near_duplicate` | repeat | salinan dengan geser 1–2 hari dan nominal ±3% |
| `repeated_procedure` | repeat | prosedur jarang (apendektomi, katarak, dll.) ditagih melebihi batas wajar 90 hari |
| `missing_evidence` | phantom | klaim FKRTL tanpa bukti dengan nominal digelembungkan |
| `process_deviation` | phantom | klaim sebelum layanan, FKRTL tanpa rujukan, atau prosedur FKRTL ditagih FKTP |
| `cloning` | cloning | satu template klaim dipakai 6–12 peserta di faskes dan hari yang sama |

## Validasi (`schema.py`)

Pandera memeriksa struktur dan domain nilai saja. Klaim yang janggal secara bisnis tetap lolos
supaya bisa dinilai oleh rule engine.

## Rule engine (`rules.py`)

| Kode | Jenis | Bobot | Aturan |
|---|---|---|---|
| R01_EXACT_DUP | repeat | 0.90 | identik dengan klaim yang diajukan lebih dulu |
| R02_NEAR_DUP | repeat | 0.70 | peserta, faskes, prosedur sama; ≤3 hari (lebih rapat untuk prosedur rutin); nominal ±5% |
| R03_REPEAT_PROC | repeat | 0.60 | frekuensi prosedur per peserta melewati batas 90 hari |
| R04_NO_EVIDENCE | phantom | 0.40 | bukti layanan tidak ada |
| R05_NO_EVIDENCE_HIGH_AMT | phantom | 0.40 | tanpa bukti dan nominal di atas P90 prosedur |
| R06_CLAIM_BEFORE_SERVICE | phantom | 0.85 | klaim diajukan sebelum layanan |
| R07_NO_REFERRAL | phantom | 0.50 | FKRTL tanpa rujukan |
| R08_LEVEL_MISMATCH | phantom | 0.70 | prosedur tingkat FKRTL ditagih FKTP |
| R09_CLONE_TEMPLATE | cloning | 0.75 | ≥5 peserta berbeda, faskes/hari/diagnosis/prosedur/nominal identik |
| R10_AMOUNT_OUTLIER | phantom | 0.25 | nominal > Q3 + 3·IQR prosedur |

`rule_score = 1 − Π(1 − bobot)` (noisy-OR). Setiap klaim membawa `reason_codes` dan `top_reason`
berbahasa Indonesia, mis. *"Prosedur 47.09 ke-3 dalam 90 hari (batas wajar 1)"*.

**Catatan jujur:** aturan dan skenario dirancang oleh tim yang sama, jadi skor pada data sintetis
(PR-AUC ±0,94 pada 20k klaim, seed 42) adalah batas atas, bukan perkiraan kinerja di data nyata.
