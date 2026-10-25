"""Auditor workspace JEJAK-JKN (Streamlit).

Jalankan lewat `python -m jejak demo` (membuat data sintetis bila belum ada), atau langsung:
`streamlit run src/jejak/app.py -- --data data`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from jejak.catalog import DIAGNOSES, PROCEDURES
from jejak.workspace import (DECISION_TEXT, DECISIONS, DEFAULT_WEIGHTS, EDGE_TEXT, SIGNALS, WorkspaceData,
                             build_queue, contributions, episode_events, latest_decisions, load_decisions,
                             load_workspace, missing_files, participant_history, related_graph, rule_reasons,
                             save_decision, split_reasons)

st.set_page_config(page_title="JEJAK-JKN · Auditor Workspace", page_icon="🔎", layout="wide")

DISCLAIMER = ("**Risiko tinggi ≠ fraud.** Skor hanya mengurutkan klaim untuk diperiksa lebih dulu. "
              "Keputusan akhir tetap di tangan auditor.")
TIER_COLOR = {"Tinggi": "#c0392b", "Sedang": "#e67e22", "Rendah": "#7f8c8d"}
EDGE_COLOR = {"duplikat": "#c0392b", "hampir_duplikat": "#e67e22", "kloning": "#8e44ad",
              "peserta": "#95a5a6", "faskes": "#bdc3c7"}
NODE_COLOR = {"klaim": "#2e86c1", "peserta": "#27ae60", "faskes": "#7f8c8d"}


def _data_dir() -> Path:
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data")
    return Path(p.parse_known_args(sys.argv[1:])[0].data)


DATA_DIR = _data_dir()


def rp(x: float) -> str:
    return "Rp" + f"{int(round(x)):,}".replace(",", ".")


def rp_short(x: float) -> str:
    for div, unit in [(1e12, "T"), (1e9, "M"), (1e6, "jt")]:
        if abs(x) >= div:
            return f"Rp{num(x / div, 1)} {unit}"
    return rp(x)


def num(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


@st.cache_data(show_spinner="Memuat hasil engine…")
def _load(data_dir: str, mtime: float) -> WorkspaceData:
    return load_workspace(Path(data_dir))


@st.cache_data(show_spinner=False)
def _queue(data_dir: str, mtime: float, weights: tuple) -> pd.DataFrame:
    return build_queue(_load(data_dir, mtime), dict(weights))


def _mtime() -> float:
    return (DATA_DIR / "risk_scores.csv").stat().st_mtime


# ---------- Sidebar ----------
def sidebar() -> dict[str, float]:
    st.sidebar.title("🔎 JEJAK-JKN")
    st.sidebar.caption("Auditor workspace · prototipe lomba · **data sintetis**")
    st.sidebar.text_input("Nama auditor", key="auditor", placeholder="mis. Auditor 01")
    with st.sidebar.expander("Bobot skor gabungan sementara", expanded=False):
        st.caption("Risk fusion belum dibangun. Skor gabungan = rata-rata berbobot sinyal tiap engine. "
                   "Bobot dinormalisasi otomatis.")
        weights = {k: st.slider(SIGNALS[k], 0.0, 1.0, DEFAULT_WEIGHTS[k], 0.05, key=f"w_{k}") for k in SIGNALS}
        if sum(weights.values()) == 0:
            st.warning("Semua bobot 0; memakai bobot bawaan.")
            weights = dict(DEFAULT_WEIGHTS)
    st.sidebar.toggle("Mode evaluasi (tampilkan label sintetis)", key="eval_mode",
                      help="Hanya untuk juri/tim. Di data nyata label tidak ada; auditorlah yang menentukan.")
    st.sidebar.divider()
    st.sidebar.caption(f"Folder data: `{DATA_DIR}`")
    return weights


def weights_key(w: dict[str, float]) -> tuple:
    return tuple(sorted(w.items()))


# ---------- Halaman: antrean ----------
def page_queue():
    data, q = st.session_state._data, st.session_state._queue
    dec = latest_decisions(load_decisions(DATA_DIR))
    q = q.assign(keputusan=q.claim_id.map(dec.keputusan) if len(dec) else "").fillna({"keputusan": ""})

    st.title("Antrean prioritas klaim")
    st.info(DISCLAIMER, icon="⚖️")

    high = q[q.prioritas == "Tinggi"]
    c = st.columns(4)
    c[0].metric("Klaim dinilai", f"{len(q):,}".replace(",", "."))
    c[1].metric("Prioritas tinggi", f"{len(high):,}".replace(",", "."))
    c[1].caption(f"{num(100 * len(high) / len(q), 1)}% dari semua klaim")
    c[2].metric("Nominal prioritas tinggi", rp_short(high.claim_amount.sum()), help=rp(high.claim_amount.sum()))
    c[2].caption("M = miliar, jt = juta")
    c[3].metric("Sudah diputuskan auditor", f"{len(dec):,}".replace(",", "."))

    with st.container(border=True):
        f = st.columns([2, 2, 2, 2, 1])
        tiers = f[0].multiselect("Prioritas", ["Tinggi", "Sedang", "Rendah"], default=["Tinggi", "Sedang"],
                                placeholder="Semua")
        pats = f[1].multiselect("Dugaan pola", sorted(q.dugaan_pola.unique()), placeholder="Semua")
        facs = f[2].multiselect("Faskes", sorted(q.facility_id.unique()), placeholder="Semua")
        status = f[3].selectbox("Status", ["Belum diputuskan", "Sudah diputuskan", "Semua"])
        top_n = f[4].number_input("Tampilkan", 20, 5000, 200, step=50)
        search = st.text_input("Cari ID klaim / token peserta", placeholder="CLM-00004720")

    v = q[q.prioritas.isin(tiers or ["Tinggi", "Sedang", "Rendah"])]
    if pats:
        v = v[v.dugaan_pola.isin(pats)]
    if facs:
        v = v[v.facility_id.isin(facs)]
    if status == "Belum diputuskan":
        v = v[v.keputusan == ""]
    elif status == "Sudah diputuskan":
        v = v[v.keputusan != ""]
    if search.strip():
        s = search.strip().upper()
        v = v[v.claim_id.str.upper().str.contains(s) | v.participant_token.str.upper().str.contains(s)]
    st.caption(f"{len(v):,} klaim cocok dengan filter; menampilkan {min(len(v), top_n):,} teratas. "
               "Pilih satu baris (kotak di kiri) untuk membuka detailnya.".replace(",", "."))

    show = v.head(int(top_n)).assign(
        prosedur=lambda d: d.procedure_code.map(lambda c: f"{c} {PROCEDURES[c].name}"),
        layanan=lambda d: d.service_timestamp.dt.strftime("%Y-%m-%d"))
    cols = ["peringkat", "claim_id", "prioritas", "skor_gabungan", "dugaan_pola", "alasan_utama", "facility_id",
            "prosedur", "layanan", "claim_amount", "keputusan"]
    ev = st.dataframe(
        show[cols], hide_index=True, width="stretch", height=560, on_select="rerun", selection_mode="single-row",
        column_config={
            "peringkat": st.column_config.NumberColumn("#", width="small"),
            "claim_id": "ID klaim", "prioritas": "Prioritas",
            "skor_gabungan": st.column_config.ProgressColumn("Skor gabungan", min_value=0, max_value=1, format="%.2f"),
            "dugaan_pola": "Dugaan pola", "alasan_utama": st.column_config.TextColumn("Alasan utama", width="large"),
            "facility_id": "Faskes", "prosedur": "Prosedur", "layanan": "Tgl layanan",
            "claim_amount": st.column_config.NumberColumn("Nominal (Rp)", format="localized"),
            "keputusan": "Keputusan",
        })
    rows = ev.selection.rows if ev and ev.selection else []
    if rows:
        r = show.iloc[rows[0]]
        st.session_state.case = r.claim_id
        st.session_state.case_list = list(show.claim_id)
        with st.container(border=True):
            a, b = st.columns([5, 1])
            a.markdown(f"**#{r.peringkat} {r.claim_id}** · prioritas {r.prioritas} · skor {num(r.skor_gabungan)} · "
                       f"{r.dugaan_pola}  \n{r.alasan_utama}")
            if b.button("Buka detail ▶", type="primary", width="stretch"):
                st.switch_page(st.session_state._pages["detail"])


# ---------- Halaman: detail kasus ----------
def _score_chart(contrib: pd.DataFrame) -> go.Figure:
    c = contrib.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=c.kontribusi, y=c.engine, orientation="h", marker_color="#2e86c1",
        text=[f"sinyal {num(s)} × bobot {num(b)}" for s, b in zip(c.sinyal, c.bobot)], textposition="auto",
        hovertemplate="%{y}: kontribusi %{x:.3f}<extra></extra>"))
    fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Kontribusi ke skor gabungan",
                      xaxis_range=[0, max(0.05, contrib.bobot.max())])
    return fig


def _timeline_chart(hist: pd.DataFrame, focus: str, related: set[str]) -> go.Figure:
    fig = go.Figure()
    for r in hist.itertuples():
        color = "#c0392b" if r.claim_id == focus else ("#e67e22" if r.claim_id in related else "#2e86c1")
        width = 4 if r.claim_id == focus else 2
        hover = (f"<b>{r.claim_id}</b><br>{r.prosedur}<br>Layanan: {r.service_timestamp:%Y-%m-%d %H:%M}"
                 f"<br>Klaim: {r.claim_timestamp:%Y-%m-%d %H:%M}<br>{r.facility_id} · {rp(r.claim_amount)}"
                 f"<br>Episode {r.episode_id}<br>Bukti: {'ada' if r.evidence_flag else 'tidak ada'}")
        fig.add_trace(go.Scatter(
            x=[r.service_timestamp, r.claim_timestamp], y=[r.prosedur, r.prosedur], mode="lines+markers",
            line=dict(color=color, width=width), marker=dict(symbol=["circle", "diamond"], size=[10, 9]),
            hovertemplate=hover + "<extra></extra>", showlegend=False))
    fig.update_layout(height=max(220, 60 + 45 * hist.prosedur.nunique()), margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_title="● waktu layanan → ◆ waktu pengajuan klaim")
    return fig


def _graph_chart(g: nx.Graph) -> go.Figure:
    # Lingkaran berlapis: faskes di tengah, klaim di cincin tengah, peserta di luar
    claims = [n for n, d in g.nodes(data=True) if d["kind"] == "klaim"]
    owners = list(dict.fromkeys(m for n in claims for m in g[n] if g.nodes[m]["kind"] == "peserta"))
    shells = [[n for n, d in g.nodes(data=True) if d["kind"] == "faskes"], claims, owners]
    pos = nx.shell_layout(g, nlist=[s for s in shells if s], rotate=0)
    fig = go.Figure()
    for t, name in EDGE_TEXT.items():
        es = [(a, b) for a, b, d in g.edges(data=True) if d["edge_type"] == t]
        if not es:
            continue
        xs, ys = [], []
        for a, b in es:
            xs += [pos[a][0], pos[b][0], None]
            ys += [pos[a][1], pos[b][1], None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=name, hoverinfo="skip",
                                 line=dict(color=EDGE_COLOR[t], width=1 if t in ("peserta", "faskes") else 3,
                                           dash="dot" if t in ("peserta", "faskes") else "solid")))
    few = sum(1 for _, d in g.nodes(data=True) if d["kind"] == "klaim") <= 12
    groups = [("Kasus ini", "klaim", True), ("Klaim terkait", "klaim", False), ("Peserta", "peserta", None),
              ("Faskes", "faskes", None)]
    style = {"klaim": ("circle", 13), "peserta": ("square", 12), "faskes": ("diamond", 13)}
    for name, kind, focus in groups:
        ns = [n for n, d in g.nodes(data=True) if d["kind"] == kind and (focus is None or d.get("focus", False) == focus)]
        if not ns:
            continue
        sym, size = style[kind]
        color = "#c0392b" if focus else ("#e67e22" if kind == "klaim" else NODE_COLOR[kind])
        fig.add_trace(go.Scatter(
            x=[pos[n][0] for n in ns], y=[pos[n][1] for n in ns], mode="markers+text", name=name,
            text=[g.nodes[n]["label"] if focus or kind != "klaim" or few else "" for n in ns],
            textposition="top center",
            marker=dict(symbol=sym, size=22 if focus else size, color=color, line=dict(width=1, color="white")),
            customdata=[[g.nodes[n]["label"], g.nodes[n]["info"]] for n in ns],
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>"))
    fig.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(visible=False),
                      yaxis=dict(visible=False), legend=dict(orientation="h", y=-0.05))
    return fig


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {t}" for t in items)


def page_detail():
    data, q = st.session_state._data, st.session_state._queue
    weights = st.session_state._weights
    ids = st.session_state.get("case_list") or list(q.claim_id.head(200))
    qp = st.query_params.get("klaim")
    if qp and qp in set(q.claim_id) and st.session_state.get("_qp_used") != qp:
        st.session_state.case, st.session_state._qp_used = qp, qp  # tautan langsung ?klaim=CLM-…
    case = st.session_state.get("case") or ids[0]
    if case not in ids:
        ids = [case] + ids

    st.title("Detail kasus")
    nav = st.columns([4, 1, 1])
    case = nav[0].selectbox("Klaim", ids, index=ids.index(case), label_visibility="collapsed")
    i = ids.index(case)
    if nav[1].button("◀ Sebelumnya", disabled=i == 0, width="stretch"):
        st.session_state.case = ids[i - 1]
        st.rerun()
    if nav[2].button("Berikutnya ▶", disabled=i == len(ids) - 1, width="stretch"):
        st.session_state.case = ids[i + 1]
        st.rerun()
    st.session_state.case = case

    row = q.set_index("claim_id").loc[case]
    claim = data.claims.set_index("claim_id").loc[case]
    dec = latest_decisions(load_decisions(DATA_DIR))
    proc = PROCEDURES[claim.procedure_code]
    diag = DIAGNOSES.get(claim.diagnosis_code)

    st.info(DISCLAIMER, icon="⚖️")
    head = st.columns([1, 1, 1, 1])
    head[0].markdown(f"### {case}")
    head[0].markdown(f"<span style='background:{TIER_COLOR[row.prioritas]};color:white;padding:3px 10px;"
                     f"border-radius:10px'>Prioritas {row.prioritas}</span> &nbsp; peringkat **#{row.peringkat}**",
                     unsafe_allow_html=True)
    head[1].metric("Skor gabungan sementara", num(row.skor_gabungan))
    head[2].metric("Dugaan pola", row.dugaan_pola)
    head[3].metric("Keputusan saat ini", dec.keputusan.get(case, "Belum ada") if len(dec) else "Belum ada")

    left, right = st.columns([1, 1])
    with left.container(border=True):
        st.markdown("**Data klaim**")
        info = {
            "Peserta (token)": claim.participant_token,
            "Faskes": f"{claim.facility_id} ({claim.facility_type})",
            "Episode": claim.episode_id,
            "Diagnosis": f"{claim.diagnosis_code} {diag.name if diag else ''}",
            "Prosedur": f"{claim.procedure_code} {proc.name} (wajar ≤{proc.max_per_90d}×/90 hari, tingkat {proc.level})",
            "Jenis layanan": f"{claim.service_type}, lama rawat {claim.los_days} hari",
            "Waktu layanan": f"{claim.service_timestamp:%Y-%m-%d %H:%M}",
            "Waktu klaim": f"{claim.claim_timestamp:%Y-%m-%d %H:%M}",
            "Nominal": rp(claim.claim_amount),
            "Rujukan": "ada" if claim.referral_flag else "tidak ada",
            "Bukti layanan": "ada" if claim.evidence_flag else "**tidak ada**",
        }
        st.markdown("\n".join(f"- {k}: {v}" for k, v in info.items()))
    with right.container(border=True):
        st.markdown("**Komposisi skor gabungan sementara**")
        st.plotly_chart(_score_chart(contributions(row, weights)), width="stretch", config={"displayModeBar": False})
        st.caption("Rata-rata berbobot sinyal engine, bukan risk fusion final. Isolation Forest: persentil "
                   "≥P90 diskalakan ke 0–1.")

    if st.session_state.get("eval_mode") and data.labels is not None:
        lab = data.labels.set_index("claim_id").loc[case]
        st.warning(f"Mode evaluasi · label sintetis: **{lab.scenario}** "
                   f"({'fraud suntikan' if lab.label else 'normal'}). Tidak tersedia di data nyata.", icon="🧪")

    tabs = st.tabs(["Alasan (reason code)", "Timeline layanan", "Graf hubungan klaim"])
    with tabs[0]:
        rr = rule_reasons(data.hits, case)
        st.markdown(f"**Aturan yang terpicu** · skor aturan {num(row.rule_score)} (noisy-OR)")
        if len(rr):
            st.dataframe(rr, hide_index=True, width="stretch",
                         column_config={"bobot": st.column_config.NumberColumn(format="%.2f"),
                                        "detail": st.column_config.TextColumn(width="large")})
        else:
            st.caption("Tidak ada aturan R01–R10 yang terpicu.")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**XGBoost + SHAP** · skor {num(row.ml_score)}")
            st.markdown(_bullets(split_reasons(row.ml_reason)) or "_Tidak ada kontribusi SHAP yang menonjol._")
            st.caption("3 fitur dengan kontribusi SHAP terbesar ke arah risiko. Model dilatih pada pola yang "
                       "sudah dilabeli; lemah untuk pola baru.")
            st.markdown(f"**Isolation Forest + SHAP** · persentil anomali {num(100 * row.anomaly_score, 1)}")
            st.markdown(_bullets(split_reasons(row.anomaly_reason))
                        or "_Bukan anomali teratas (SHAP hanya untuk 1.000 klaim paling anomali)._")
        with c2:
            st.markdown(f"**Process mining** · skor {num(row.proc_score)}")
            st.markdown(f"- {row.proc_reason}" if row.proc_reason else "_Alur episode umum._")
            st.markdown(f"**Graph antar-klaim** · skor {num(row.graph_score)}")
            st.markdown(f"- {row.graph_reason}" if row.graph_reason else "_Tidak ada klaim duplikat/kloning terkait._")

    g = related_graph(data, case)
    related = {n for n, d in g.nodes(data=True) if d["kind"] == "klaim" and n != case}
    with tabs[1]:
        hist = participant_history(data.claims, claim.participant_token)
        st.markdown(f"**Riwayat klaim peserta {claim.participant_token}** · {len(hist)} klaim. "
                    "Merah = kasus ini, oranye = klaim terkait di graf.")
        st.plotly_chart(_timeline_chart(hist, case, related), width="stretch")
        st.markdown(f"**Alur proses episode {claim.episode_id}** (event log process mining)")
        ev = episode_events(data.claims, claim.episode_id)
        ev.insert(0, "langkah", range(1, len(ev) + 1))
        ev["kasus_ini"] = (ev.claim_id == case).map({True: "◀", False: ""})
        st.dataframe(ev, hide_index=True, width="stretch")
    with tabs[2]:
        n_claims = sum(1 for _, d in g.nodes(data=True) if d["kind"] == "klaim")
        st.markdown(f"**{n_claims - 1} klaim terkait** lewat edge duplikat / hampir duplikat / kloning "
                    "(maks. 2 langkah), beserta peserta dan faskesnya.")
        if n_claims == 1:
            st.caption("Klaim ini tidak punya pasangan di graph antar-klaim; yang tampil hanya peserta dan faskesnya.")
        st.plotly_chart(_graph_chart(g), width="stretch")
        if related:
            rel = q[q.claim_id.isin(related)][["claim_id", "participant_token", "facility_id", "procedure_code",
                                              "service_timestamp", "claim_amount", "skor_gabungan", "prioritas"]]
            st.dataframe(rel, hide_index=True, width="stretch", column_config={
                "claim_id": "ID klaim", "participant_token": "Peserta", "facility_id": "Faskes",
                "procedure_code": "Prosedur", "service_timestamp": st.column_config.DatetimeColumn("Layanan"),
                "claim_amount": st.column_config.NumberColumn("Nominal (Rp)", format="localized"),
                "skor_gabungan": st.column_config.NumberColumn("Skor gabungan", format="%.2f"),
                "prioritas": "Prioritas"})

    decision_form(case, float(row.skor_gabungan), dec)


def decision_form(case: str, score: float, dec: pd.DataFrame):
    st.divider()
    st.subheader("Keputusan auditor")
    current = dec.loc[case] if len(dec) and case in dec.index else None
    if current is not None:
        st.success(f"Keputusan tercatat: **{current.keputusan}** · {current.waktu}"
                   + (f" · {current.auditor}" if current.auditor else "")
                   + (f" — _{current.catatan}_" if current.catatan else ""))
    with st.form(f"form_{case}", clear_on_submit=False):
        choice = st.radio("Keputusan", DECISIONS, format_func=DECISION_TEXT.get, horizontal=True,
                          index=DECISIONS.index(current.keputusan) if current is not None else None)
        note = st.text_area("Catatan pemeriksaan", placeholder="Dasar keputusan, dokumen yang dicek, tindak lanjut…")
        if st.form_submit_button("Simpan keputusan", type="primary"):
            if choice is None:
                st.error("Pilih salah satu keputusan dulu.")
            else:
                save_decision(DATA_DIR, case, choice, note, st.session_state.get("auditor", ""), round(score, 4))
                st.toast(f"Keputusan {choice} untuk {case} disimpan", icon="✅")
                st.rerun()
    st.caption(f"Disimpan lokal di `{DATA_DIR / 'keputusan_auditor.csv'}` (log append-only; keputusan terbaru berlaku).")


# ---------- Halaman: ringkasan ----------
def page_summary():
    data, q = st.session_state._data, st.session_state._queue
    log = load_decisions(DATA_DIR)
    dec = latest_decisions(log)
    st.title("Ringkasan & log keputusan")

    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.markdown("**Klaim per prioritas dan dugaan pola**")
        t = pd.crosstab(q.dugaan_pola, q.prioritas).reindex(columns=["Tinggi", "Sedang", "Rendah"], fill_value=0)
        t.index.name, t.columns.name = "Dugaan pola", None
        st.dataframe(t, width="stretch")
    with c2.container(border=True):
        st.markdown("**Faskes dengan klaim prioritas tinggi terbanyak**")
        h = q[q.prioritas == "Tinggi"].groupby("facility_id").agg(
            klaim_tinggi=("claim_id", "size"), nominal=("claim_amount", "sum")).sort_values("klaim_tinggi", ascending=False)
        h.index.name = "Faskes"
        st.dataframe(h.head(10), width="stretch",
                     column_config={"klaim_tinggi": "Klaim prioritas tinggi",
                                    "nominal": st.column_config.NumberColumn("Nominal (Rp)", format="localized")})

    with st.container(border=True):
        st.markdown(f"**Log keputusan auditor** · {len(dec)} klaim diputuskan, {len(log)} entri log")
        if len(log):
            counts = dec.keputusan.value_counts().reindex(DECISIONS, fill_value=0)
            cc = st.columns(4)
            for col, (k, v) in zip(cc, counts.items()):
                col.metric(k, v)
            st.dataframe(log.iloc[::-1], hide_index=True, width="stretch")
            st.download_button("Unduh log keputusan (CSV)", log.to_csv(index=False).encode(),
                               "keputusan_auditor.csv", "text/csv")
        else:
            st.caption("Belum ada keputusan. Buka antrean, pilih klaim, lalu simpan keputusan di bawah detail kasus.")

    if st.session_state.get("eval_mode") and data.labels is not None:
        with st.container(border=True):
            st.markdown("**🧪 Mode evaluasi (data sintetis)**")
            m = q.merge(data.labels, on="claim_id")
            rows = []
            for k in (100, 500, 1000):
                top = m.nsmallest(k, "peringkat")
                rows.append({"K": k, "Precision@K": round(top.label.mean(), 3),
                             "Recall@K": round(top.label.sum() / max(1, m.label.sum()), 3)})
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            st.dataframe(pd.crosstab(m.prioritas, m.scenario), width="stretch")
            if len(dec):
                d = dec.join(data.labels.set_index("claim_id"), how="left")
                st.markdown("Keputusan auditor vs label sintetis")
                st.dataframe(pd.crosstab(d.keputusan, d.scenario), width="stretch")
            st.caption("Angka ini optimistis: skenario dan engine dibuat tim yang sama (lihat README).")


def page_about():
    st.title("Tentang skor & cara membaca")
    st.markdown(f"""
{DISCLAIMER}

**Alur:** data klaim (sintetis) → 4 engine → *skor gabungan sementara* → antrean prioritas → auditor memutuskan.

| Engine | Yang ditangkap | Sinyal di skor gabungan |
|---|---|---|
| Aturan R01–R10 | duplikat, prosedur berulang, tanpa bukti, klaim sebelum layanan, tanpa rujukan, kloning templat | `rule_score` (noisy-OR bobot aturan) |
| XGBoost + SHAP | pola yang **sudah pernah dilabeli** | probabilitas model |
| Graph antar-klaim | pasangan duplikat, hampir duplikat, klaster kloning | `graph_score` |
| Process mining (PM4Py) | alur episode yang langka/menyimpang | `proc_score` |
| Isolation Forest + SHAP | anomali tanpa label (pola baru) | persentil ≥P90 diskalakan 0–1 |

**Skor gabungan sementara** = Σ(bobot × sinyal) / Σ bobot. Bobot bawaan:
{", ".join(f"{SIGNALS[k]} {num(v)}" for k, v in DEFAULT_WEIGHTS.items())}. Bisa diubah di sidebar.
Prioritas: **Tinggi** ≥ 0,50 · **Sedang** ≥ 0,25 · **Rendah** < 0,25.
Ini pengganti sederhana sampai *risk fusion* dibangun.

**Keputusan auditor:**
""" + "\n".join(f"- {DECISION_TEXT[d]}" for d in DECISIONS) + """

Keputusan disimpan sebagai log lokal dan nantinya bisa menjadi label umpan balik untuk melatih ulang model.
Semua data di prototipe ini **sintetis**; token peserta adalah pseudonim, bukan NIK/nomor kartu.
""")


def main():
    miss = missing_files(DATA_DIR)
    if miss:
        st.error(f"File hasil engine belum ada di `{DATA_DIR}`: {', '.join(miss)}. "
                 "Jalankan `python -m jejak demo` untuk membuat data sintetis dan menilai klaim.")
        st.stop()
    weights = sidebar()
    mtime = _mtime()
    st.session_state._data = _load(str(DATA_DIR), mtime)
    st.session_state._queue = _queue(str(DATA_DIR), mtime, weights_key(weights))
    st.session_state._weights = weights
    pages = {
        "queue": st.Page(page_queue, title="Antrean risiko", icon="📋", default=True, url_path="antrean"),
        "detail": st.Page(page_detail, title="Detail kasus", icon="🔍", url_path="kasus"),
        "summary": st.Page(page_summary, title="Ringkasan & keputusan", icon="📊", url_path="ringkasan"),
        "about": st.Page(page_about, title="Tentang skor", icon="ℹ️", url_path="tentang"),
    }
    st.session_state._pages = pages
    st.navigation(list(pages.values())).run()


main()
