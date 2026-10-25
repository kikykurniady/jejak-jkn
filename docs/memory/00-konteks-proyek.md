# Konteks Proyek — Jejak JKN
_Terakhir diperbarui: 2026-10-25_

## Lomba
- **BPJS Healthkathon 2026**. Kategori: *Efisiensi Risiko Fasilitas Kesehatan*, subkategori *Phantom & Repeat Billing*.
- Dokumen resmi lomba ada di folder `hackathon/Doc/` (Panduan Project Final, Template Project Final, Materi Data Sample, dll).

## Masalah & tujuan
Auditor JKN tidak bisa memeriksa semua klaim. JEJAK-JKN memberi **antrian prioritas klaim berisiko**
dengan **risk score + reason code** yang bisa dijelaskan, untuk tiga pola:
- **Phantom Billing** — klaim untuk layanan yang tidak pernah terjadi.
- **Repeat Billing** — layanan yang sama ditagih berulang.
- **Cloning** — klaim yang disalin/mirip berlebihan antar-peserta atau antar-episode.
  _Catatan: Cloning belum dibahas di draf proposal._

Prinsip: sistem **mendukung, bukan menggantikan**, keputusan auditor.

## Arsitektur (dari proposal)
4 engine → Risk Fusion → Auditor Workspace
1. **Process Mining** (PM4Py) — penyimpangan alur layanan
2. **Graph** (NetworkX, nanti Neo4j) — hubungan peserta–faskes–episode
3. **Rules + ML** (aturan, XGBoost, Isolation Forest) — pola & anomali
4. **Explainability** (SHAP + reason codes)

**Auditor workspace** (Streamlit): risk queue, detail kasus, timeline, graf, reason code,
keputusan auditor: *Valid / Need Clarification / Irregular / False Positive*.

## Cakupan MVP yang direkomendasikan (2026-10-25)
- **MVP:** generator data sintetis, validasi + episode linking, rule engine, similarity (repeat + cloning),
  graf NetworkX, Isolation Forest, risk fusion + reason code, Streamlit.
- **Opsional:** PM4Py ringan, XGBoost + SHAP (hati-hati: sirkular pada label sintetis), FastAPI.
- **Roadmap:** Neo4j, PostgreSQL, Next.js, Keycloak, MLflow.
- Dokumen rekomendasi: https://claude.ai/artifact/Hujp3hA2CT8Tmv7fVVfcrV

## Stack
Python, Pandas/Polars, Pandera, FastAPI, Streamlit, PostgreSQL, Docker.

## Data
- **Hanya data sintetis**: 10.000–50.000 klaim dengan skenario fraud yang disuntikkan (berlabel).
- Field inti: `claim_id, participant_token, facility_id, episode_id, diagnosis_code, procedure_code,
  service_timestamp, claim_timestamp, claim_amount, evidence_flag`.
- Skema disesuaikan dengan **data sampel resmi BPJS** (data.bpjs-kesehatan.go.id), 5 dataset:
  Peserta (18 var), FKTP (26), FKTP Non Kapitasi (23), FKRTL (55), Diagnosis Sekunder (4).

## Metrik evaluasi
Precision, Recall, F1, PR-AUC, Precision@K, Recall@K.

## Status proposal
Draf "Jejak JKN 1.pdf": bagian 1–5 dari 9 sudah ditulis. Belum ada: 6 Rencana & Kelayakan,
7 Dampak & Nilai, 8 Risiko/Privasi/Etika, 9 Profil Tim, serta statistik publik JKN yang terverifikasi.
