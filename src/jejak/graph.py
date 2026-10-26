"""Graph antar-klaim (NetworkX).

Node = klaim. Edge dibuat lewat *blocking* (hanya klaim satu kelompok yang dibandingkan),
tanpa label:

| Jenis edge | Syarat |
|---|---|
| `duplikat` | peserta, faskes, diagnosis, prosedur, waktu layanan, dan nominal identik |
| `hampir_duplikat` | peserta, faskes, prosedur sama; jarak layanan ≤ jendela prosedur; nominal ±5%; tidak identik |
| `kloning` | peserta **berbeda**, faskes, tanggal, diagnosis, prosedur sama; nominal ±2% |

Dari graf dihitung fitur per klaim (derajat per jenis edge, ukuran komponen, jumlah peserta
di komponen kloning) plus pola peserta–faskes dari graf bipartit (berapa kali peserta datang
ke faskes itu, berapa faskes yang dikunjungi peserta, porsi klaim faskes yang ada di klaster kloning).
"""
from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from .rules import DUP_KEY, _near_dup_window_days

EDGE_COLUMNS = ["claim_a", "claim_b", "edge_type", "similarity", "gap_days", "amount_diff"]


def _pairs(df: pd.DataFrame, on: list[str]) -> pd.DataFrame:
    cols = ["claim_id", "participant_token", "service_timestamp", "claim_timestamp", "claim_amount", "procedure_code"]
    a = df[list(dict.fromkeys(on + cols))]
    m = a.merge(a, on=on, suffixes=("", "_o"))
    m = m[m.claim_id < m.claim_id_o].copy()
    for col in set(on) & set(cols):  # kolom kunci tidak diberi sufiks oleh merge
        m[col + "_o"] = m[col]
    m["gap_days"] = (m.service_timestamp - m.service_timestamp_o).abs().dt.total_seconds() / 86400
    m["amount_diff"] = (m.claim_amount - m.claim_amount_o).abs() / m[["claim_amount", "claim_amount_o"]].min(axis=1)
    return m


def claim_edges(claims: pd.DataFrame, near_amount_tol: float = 0.05, clone_amount_tol: float = 0.02) -> pd.DataFrame:
    """Daftar edge antar-klaim (satu baris per pasangan, claim_a < claim_b)."""
    out = []
    dup = _pairs(claims, DUP_KEY)
    out.append(dup.assign(edge_type="duplikat", similarity=1.0))

    near = _pairs(claims, ["participant_token", "facility_id", "procedure_code"])
    window = near.procedure_code.map(_near_dup_window_days(3))
    keep = (near.gap_days <= window) & (near.amount_diff <= near_amount_tol) & ~((near.gap_days == 0) & (near.amount_diff == 0))
    near, window = near[keep], window[keep]
    out.append(near.assign(edge_type="hampir_duplikat",
                           similarity=1 - 0.5 * (near.gap_days / window) - 0.5 * (near.amount_diff / near_amount_tol)))

    c = claims.assign(service_date=claims.service_timestamp.dt.normalize())
    clone = _pairs(c, ["facility_id", "service_date", "diagnosis_code", "procedure_code"])
    clone = clone[(clone.participant_token != clone.participant_token_o) & (clone.amount_diff <= clone_amount_tol)]
    out.append(clone.assign(edge_type="kloning", similarity=1 - clone.amount_diff / clone_amount_tol))

    e = pd.concat(out, ignore_index=True).rename(columns={"claim_id": "claim_a", "claim_id_o": "claim_b"})
    e["similarity"] = e.similarity.clip(0, 1).round(3)
    e["gap_days"] = e.gap_days.round(2)
    e["amount_diff"] = e.amount_diff.round(4)
    return e[EDGE_COLUMNS].sort_values(["claim_a", "claim_b", "edge_type"]).reset_index(drop=True)


def build_graph(claims: pd.DataFrame, edges: pd.DataFrame) -> nx.MultiGraph:
    g = nx.MultiGraph()
    g.add_nodes_from(claims.claim_id)
    g.add_edges_from((a, b, {"edge_type": t, "similarity": s})
                     for a, b, t, s in edges[["claim_a", "claim_b", "edge_type", "similarity"]].itertuples(index=False))
    return g


def _later_flags(claims: pd.DataFrame, edges: pd.DataFrame, edge_type: str) -> tuple[pd.Series, pd.Series]:
    """Per klaim: punya pasangan `edge_type` yang diajukan lebih dulu (= klaim ini salinan),
    dan klaim pasangan pertama itu."""
    e = edges[edges.edge_type == edge_type]
    ts = claims.set_index("claim_id").claim_timestamp
    both = pd.concat([e[["claim_a", "claim_b"]].set_axis(["c", "o"], axis=1),
                      e[["claim_b", "claim_a"]].set_axis(["c", "o"], axis=1)], ignore_index=True)
    tc, to = both.c.map(ts), both.o.map(ts)
    both = both[(tc > to) | ((tc == to) & (both.c > both.o))]
    first = both.assign(t=both.o.map(ts)).sort_values("t").drop_duplicates("c").set_index("c").o
    return pd.Series(True, index=first.index), first


def graph_features(claims: pd.DataFrame, edges: pd.DataFrame | None = None) -> pd.DataFrame:
    """Fitur graf per klaim + `graph_score` (0–1) dan `graph_reason` berbahasa Indonesia."""
    edges = claim_edges(claims) if edges is None else edges
    g = build_graph(claims, edges)
    out = claims[["claim_id"]].copy()
    ids = out.claim_id

    for t, col in [("duplikat", "deg_dup"), ("hampir_duplikat", "deg_near"), ("kloning", "deg_clone")]:
        e = edges[edges.edge_type == t]
        out[col] = ids.map(pd.concat([e.claim_a, e.claim_b]).value_counts()).fillna(0).astype(int)

    comp_of = {n: i for i, comp in enumerate(nx.connected_components(g)) for n in comp}
    out["graph_component"] = ids.map(comp_of)
    out["component_size"] = out.groupby("graph_component").claim_id.transform("size")

    # Klaster kloning: komponen di subgraf edge kloning saja
    gc = nx.Graph()
    gc.add_edges_from(edges.loc[edges.edge_type == "kloning", ["claim_a", "claim_b"]].itertuples(index=False))
    clone_comp = {n: i for i, comp in enumerate(nx.connected_components(gc)) for n in comp}
    part = claims.set_index("claim_id").participant_token
    cc = ids.map(clone_comp)
    n_part = pd.Series(ids.map(part).values, index=ids.index).groupby(cc).transform("nunique")
    out["clone_participants"] = n_part.fillna(1).astype(int).values

    dup_later, dup_src = _later_flags(claims, edges, "duplikat")
    near_later, near_src = _later_flags(claims, edges, "hampir_duplikat")
    out["dup_is_later"] = ids.map(dup_later).fillna(False).astype(int)
    out["near_is_later"] = ids.map(near_later).fillna(False).astype(int)

    # Pola peserta–faskes (graf bipartit)
    pf = claims.groupby(["participant_token", "facility_id"]).claim_id.transform("size")
    out["pf_visits"] = pf.values
    out["participant_n_facilities"] = claims.groupby("participant_token").facility_id.transform("nunique").values
    in_clone = (out.clone_participants >= 3).astype(float)
    out["facility_clone_share"] = in_clone.groupby(claims.facility_id.values).transform("mean").round(4).values

    # Skor graf sederhana yang bisa dijelaskan
    clone_s = np.where(out.clone_participants >= 3, np.minimum(0.95, 0.15 * (out.clone_participants - 1)), 0)
    score = np.maximum.reduce([
        0.9 * out.dup_is_later, 0.7 * out.near_is_later, clone_s,
        0.3 * ((out.deg_dup + out.deg_near) > 0),  # klaim asal yang punya salinan: tampilkan sebagai konteks
    ])
    out["graph_score"] = np.round(score, 4)

    fac = claims.set_index("claim_id").facility_id
    reason = np.select(
        [out.dup_is_later == 1, out.near_is_later == 1, clone_s > 0, (out.deg_dup + out.deg_near) > 0],
        ["Salinan identik dari klaim " + ids.map(dup_src).fillna("").astype(str),
         "Hampir sama dengan klaim lebih awal " + ids.map(near_src).fillna("").astype(str),
         "Klaster " + out.clone_participants.astype(str) + " peserta berbeda di " + ids.map(fac).astype(str)
         + " dengan tanggal, diagnosis, prosedur sama dan nominal ±2%",
         "Memiliki " + (out.deg_dup + out.deg_near).astype(str) + " klaim salinan/mirip yang diajukan belakangan"],
        default="",
    )
    out["graph_reason"] = reason
    return out.drop(columns="graph_component")
