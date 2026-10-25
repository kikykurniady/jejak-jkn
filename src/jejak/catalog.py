"""Katalog referensi sintetis: diagnosis (ICD-10) dan prosedur (ICD-9-CM).

Angka biaya dan batas frekuensi adalah asumsi sintetis untuk prototipe,
bukan tarif INA-CBG resmi.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Procedure:
    code: str
    name: str
    level: str  # "FKTP" atau "FKRTL": tingkat faskes minimal yang boleh melakukan
    service_type: str  # "RJ" (rawat jalan) atau "RI" (rawat inap)
    base_cost: int  # rupiah
    max_per_90d: int  # frekuensi wajar per peserta dalam 90 hari
    los: tuple[int, int] = (0, 0)  # rentang lama rawat (hari)


PROCEDURES: dict[str, Procedure] = {p.code: p for p in [
    Procedure("89.03", "Konsultasi dan pemeriksaan umum", "FKTP", "RJ", 60_000, 12),
    Procedure("90.59", "Pemeriksaan laboratorium darah", "FKTP", "RJ", 120_000, 6),
    Procedure("23.09", "Pencabutan gigi", "FKTP", "RJ", 150_000, 4),
    Procedure("87.44", "Rontgen dada", "FKRTL", "RJ", 250_000, 4),
    Procedure("88.72", "Ekokardiografi", "FKRTL", "RJ", 900_000, 2),
    Procedure("93.39", "Fisioterapi", "FKRTL", "RJ", 200_000, 24),
    Procedure("39.95", "Hemodialisis", "FKRTL", "RJ", 950_000, 39),
    Procedure("99.04", "Transfusi sel darah merah", "FKRTL", "RI", 1_800_000, 6, (1, 3)),
    Procedure("13.41", "Fakoemulsifikasi katarak", "FKRTL", "RJ", 7_500_000, 2),
    Procedure("47.09", "Apendektomi", "FKRTL", "RI", 9_000_000, 1, (2, 5)),
    Procedure("74.1", "Seksio sesarea", "FKRTL", "RI", 8_000_000, 1, (2, 4)),
    Procedure("36.06", "Pemasangan stent koroner", "FKRTL", "RI", 45_000_000, 2, (2, 6)),
    Procedure("81.54", "Penggantian sendi lutut total", "FKRTL", "RI", 60_000_000, 1, (3, 7)),
    Procedure("96.04", "Perawatan pneumonia rawat inap", "FKRTL", "RI", 6_000_000, 2, (3, 8)),
]}


@dataclass(frozen=True)
class Diagnosis:
    code: str
    name: str
    weight: float  # frekuensi relatif episode
    pathway: str  # pola episode, lihat generator._episode_claims
    procedures: tuple[str, ...]


DIAGNOSES: dict[str, Diagnosis] = {d.code: d for d in [
    Diagnosis("J06.9", "ISPA", 0.22, "single", ("89.03",)),
    Diagnosis("I10", "Hipertensi esensial", 0.18, "chronic_visit", ("89.03", "90.59")),
    Diagnosis("E11.9", "Diabetes melitus tipe 2", 0.14, "chronic_visit", ("89.03", "90.59")),
    Diagnosis("K02.9", "Karies gigi", 0.08, "single", ("23.09",)),
    Diagnosis("M17.9", "Osteoartritis lutut", 0.06, "therapy_series", ("93.39", "81.54")),
    Diagnosis("N18.5", "Penyakit ginjal kronik stadium 5", 0.03, "dialysis_series", ("39.95",)),
    Diagnosis("I25.1", "Penyakit jantung koroner", 0.04, "referral_then_proc", ("88.72", "36.06")),
    Diagnosis("H25.9", "Katarak senilis", 0.05, "referral_then_proc", ("13.41",)),
    Diagnosis("K35.8", "Apendisitis akut", 0.04, "referral_then_proc", ("47.09",)),
    Diagnosis("O82", "Persalinan dengan seksio sesarea", 0.05, "referral_then_proc", ("74.1",)),
    Diagnosis("J18.9", "Pneumonia", 0.06, "referral_then_proc", ("87.44", "96.04")),
    Diagnosis("D64.9", "Anemia", 0.05, "referral_then_proc", ("90.59", "99.04")),
]}

# Prosedur sekali-seumur/jarang: kandidat skenario prosedur berulang
ONE_OFF_PROCEDURES = [c for c, p in PROCEDURES.items() if p.max_per_90d <= 2]
