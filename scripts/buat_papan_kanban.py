"""Buat papan Kanban GitHub Projects untuk JEJAK-JKN (K023/K024)."""
import json
import subprocess
import sys

OWNER = "kikykurniady"
REPO = f"{OWNER}/jejak-jkn"
TITLE = "JEJAK-JKN — Menuju Submit 1 Nov 2026"

MOSCOW = ["Must", "Should", "Could", "Won't"]
KRITERIA = ["Kreativitas", "Model Bisnis", "Dampak", "Presentasi", "Kesiapan Produk"]
HARI = ["Sen 26/10", "Sel 27/10", "Rab 28/10", "Kam 29/10", "Jum 30/10", "Sab 31/10", "Min 1/11"]

# (judul, moscow, kriteria, hari|None, isi)
CARDS = [
    ("Perketat .gitignore untuk data BPJS", "Must", "Kesiapan Produk", "Sen 26/10",
     "Jaring pengaman K026: pola file data/model/notebook diabaikan. Repo publik."),
    ("Profil kolom data sampel BPJS (agregat saja)", "Must", "Kesiapan Produk", "Sen 26/10",
     "Nama kolom, tipe, jumlah baris, statistik ringkas. Tanpa baris mentah (K026). "
     "Hasil: tabel pemetaan kolom BPJS -> skema JEJAK di docs/."),
    ("Lean Canvas model bisnis", "Must", "Model Bisnis", "Sen 26/10",
     "Masalah, segmen pengguna (auditor/verifikator BPJS), solusi, nilai unik, biaya, "
     "metrik kunci, cara implementasi nasional."),
    ("Adapter data BPJS dengan DuckDB", "Must", "Kesiapan Produk", "Sel 27/10",
     "Muat format data sampel BPJS, hash ulang kode peserta/faskes, petakan ke skema klaim, validasi Pandera."),
    ("Kembaran sintetis data BPJS dengan SDV", "Must", "Kesiapan Produk", "Sel 27/10",
     "Latih SDV pada data BPJS (lokal), hasilkan data sintetis untuk demo/video/repo. Cek kemiripan distribusi (agregat)."),
    ("Diagram arsitektur & alur proses", "Must", "Presentasi", "Sel 27/10",
     "draw.io/Mermaid: Input -> Proses -> Analisis AI -> Output -> Tindak lanjut (sesuai template slide 4)."),
    ("Splink untuk deteksi cloning & repeat billing", "Must", "Kreativitas", "Rab 28/10",
     "Record linkage probabilistik; skor kemiripan + alasan per kolom. Bandingkan dengan graph.py saat ini."),
    ("Risk fusion final (ganti skor sementara K019)", "Must", "Dampak", "Rab 28/10",
     "Gabungkan aturan + anomali + graf + process + Splink; kalibrasi pada seed terpisah; satu skor + daftar alasan."),
    ("Profil risiko faskes: Benford + peer group", "Must", "Dampak", "Kam 29/10",
     "Peringkat faskes, deviasi terhadap kelompok sejenis, uji Benford nominal. Halaman baru di dashboard."),
    ("Halaman Dampak: top-K% vs sampling acak", "Must", "Dampak", "Kam 29/10",
     "Kurva % nominal berisiko tertangkap vs % klaim diperiksa, estimasi jam auditor dihemat. Angka dari hasil uji."),
    ("Tes asap dashboard & CLI demo", "Must", "Kesiapan Produk", "Jum 30/10",
     "app.py dan cli.py masih 0% cakupan tes; pastikan `python -m jejak demo` tidak error saat rekam."),
    ("Naskah demo 3 kasus + isi slide template", "Must", "Presentasi", "Sab 31/10",
     "Repeat, phantom, cloning. Ikuti template Panduan Project Final (7 bagian, total 10 menit)."),
    ("Rekam video ≤10 menit & submit dashboard", "Must", "Presentasi", "Min 1/11",
     "YouTube unlisted/private, foto semua anggota, demo aplikasi berjalan, hanya data sintetis/agregat."),
    ("Asisten auditor GenAI (Claude API)", "Should", "Kreativitas", None,
     "Ringkasan kasus + draf surat klarifikasi dari reason code. Hanya data sintetis; template cadangan bila offline."),
    ("PyOD ECOD untuk anomali", "Should", "Kreativitas", None,
     "Lengkapi/ganti Isolation Forest; tampilkan kolom penyebab anomali."),
    ("AI Red Team: cari titik buta deteksi", "Should", "Kreativitas", None,
     "Mutasi skenario fraud (nominal, jeda, faskes) sampai lolos; laporkan pola yang lolos + usulan aturan."),
    ("FastAPI /score + Docker Compose", "Could", "Kesiapan Produk", None,
     "Endpoint skor batch & per klaim, satu perintah docker compose up."),
    ("InterpretML EBM sebagai model kotak kaca", "Could", "Kreativitas", None,
     "Bandingkan dengan XGBoost; tampilkan kontribusi per faktor."),
    ("Deteksi jaringan fraud (igraph + Leiden)", "Could", "Kreativitas", None,
     "Komunitas peserta–faskes mencurigakan."),
    ("Umpan balik keputusan auditor -> latih ulang", "Could", "Dampak", None,
     "Pakai log keputusan_auditor.csv sebagai label; tunjukkan model membaik."),
    ("Roadmap: Neo4j, PostgreSQL, MLflow, GNN, SSO", "Won't", "Kesiapan Produk", None,
     "Tidak dikerjakan sebelum 1 Nov; cukup di slide Rencana pengembangan."),
]


def gh(*args, parse=True):
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out) if parse and out.strip() else out


def main():
    proj = gh("project", "create", "--owner", OWNER, "--title", TITLE, "--format", "json")
    num, pid = str(proj["number"]), proj["id"]
    print("Papan:", proj["url"])
    gh("project", "link", num, "--owner", OWNER, "--repo", REPO, parse=False)

    fields = {}
    for name, opts in [("MoSCoW", MOSCOW), ("Kriteria Juri", KRITERIA), ("Hari", HARI)]:
        gh("project", "field-create", num, "--owner", OWNER, "--name", name,
           "--data-type", "SINGLE_SELECT", "--single-select-options", ",".join(opts), "--format", "json")
    for f in gh("project", "field-list", num, "--owner", OWNER, "--format", "json")["fields"]:
        fields[f["name"]] = (f["id"], {o["name"]: o["id"] for o in f.get("options", [])})

    for label, color in [("must", "b60205"), ("should", "d93f0b"), ("could", "fbca04"), ("wont", "c5def5")]:
        subprocess.run(["gh", "label", "create", label, "--repo", REPO, "--color", color, "--force"],
                       check=True, capture_output=True)

    for title, moscow, kriteria, hari, body in CARDS:
        url = gh("issue", "create", "--repo", REPO, "--title", title, "--body", body,
                 "--label", moscow.lower().replace("'", ""), parse=False).strip()
        item = gh("project", "item-add", num, "--owner", OWNER, "--url", url, "--format", "json")
        done = title.startswith("Perketat .gitignore")
        values = {"MoSCoW": moscow, "Kriteria Juri": kriteria, "Status": "Done" if done else "Todo"}
        if hari:
            values["Hari"] = hari
        for fname, val in values.items():
            fid, opts = fields[fname]
            gh("project", "item-edit", "--id", item["id"], "--project-id", pid,
               "--field-id", fid, "--single-select-option-id", opts[val], parse=False)
        if done:
            gh("issue", "close", url, "--comment", "Selesai 2026-10-26.", parse=False)
        print("+", moscow, "|", title)


if __name__ == "__main__":
    sys.exit(main())
