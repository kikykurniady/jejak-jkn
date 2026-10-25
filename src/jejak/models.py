"""Model risiko: Isolation Forest (tanpa label) dan XGBoost (berlabel), dijelaskan dengan SHAP.

- **Isolation Forest** dilatih pada fitur klaim batch yang sedang dinilai, tanpa label.
  `anomaly_score` = persentil skor anomali (0–1). SHAP (TreeExplainer) dihitung hanya untuk
  klaim teratas karena lambat; alasannya = fitur yang paling memperpendek jalur isolasi.
- **XGBoost** dilatih pada data sintetis **terpisah** (seed lain) dengan label generator, lalu
  dipakai menilai batch ini. SHAP diambil dari TreeSHAP bawaan XGBoost (`pred_contribs`), yang
  setara dengan `shap.TreeExplainer` namun jauh lebih cepat.

Kedua model memakai `MODEL_FEATURES` (tanpa fitur struktur episode/peserta, lihat di bawah).
Alasan diubah ke kalimat Bahasa Indonesia lewat templat di `features.FEATURES`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .features import FEATURE_NAMES, format_feature

# Fitur yang mencerminkan struktur episode/peserta buatan generator. Dipakai untuk uji ablasi:
# skenario suntikan selalu dibuat sebagai episode baru berisi satu klaim, sehingga fitur ini
# bisa "terlalu mudah" di data sintetis.
STRUCTURAL_FEATURES = ["episode_n_claims", "pf_visits", "participant_n_facilities"]
# Fitur default XGBoost: tanpa fitur struktur. Kinerjanya hampir sama, alasannya lebih bermakna
# bagi auditor, dan model tidak bersandar pada artefak generator.
MODEL_FEATURES = [f for f in FEATURE_NAMES if f not in STRUCTURAL_FEATURES]


def _reasons(contrib: np.ndarray, X: pd.DataFrame, cols: list[str], sign: int, top: int = 3,
             min_abs: float = 1e-6) -> list[str]:
    """Gabungkan `top` fitur dengan kontribusi terbesar searah `sign` menjadi teks alasan."""
    out = []
    vals = X[cols].to_numpy()
    for i in range(len(contrib)):
        c = contrib[i] * sign
        texts = (format_feature(cols[j], vals[i, j]) for j in np.argsort(-c) if c[j] > min_abs)
        out.append("; ".join([t for t in texts if t][:top]))
    return out


# ---------- Isolation Forest ----------
def anomaly_scores(features: pd.DataFrame, explain_top: int = 1000, seed: int = 0,
                   n_estimators: int = 200) -> pd.DataFrame:
    import shap
    from sklearn.ensemble import IsolationForest

    X = features[MODEL_FEATURES]
    model = IsolationForest(n_estimators=n_estimators, random_state=seed).fit(X)
    raw = -model.score_samples(X)  # makin besar makin anomali
    out = features[["claim_id"]].copy()
    out["anomaly_raw"] = raw.round(5)
    out["anomaly_score"] = pd.Series(raw).rank(pct=True).round(4).to_numpy()
    out["anomaly_reason"] = ""
    top = np.argsort(-raw)[:explain_top]
    if len(top):
        sv = shap.TreeExplainer(model).shap_values(X.iloc[top])
        # SHAP menjelaskan panjang jalur; kontribusi negatif = mendorong ke anomali
        out.iloc[top, out.columns.get_loc("anomaly_reason")] = _reasons(sv, X.iloc[top], MODEL_FEATURES, sign=-1)
    return out


# ---------- XGBoost ----------
@dataclass
class RiskModel:
    booster: object
    features: list[str] = field(default_factory=lambda: list(MODEL_FEATURES))

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        import xgboost as xgb
        return self.booster.predict(xgb.DMatrix(features[self.features], feature_names=self.features))

    def shap_values(self, features: pd.DataFrame) -> np.ndarray:
        """Kontribusi TreeSHAP (log-odds) per fitur; kolom terakhir = nilai dasar."""
        import xgboost as xgb
        return self.booster.predict(xgb.DMatrix(features[self.features], feature_names=self.features),
                                    pred_contribs=True)

    def explain(self, features: pd.DataFrame, top: int = 3) -> pd.DataFrame:
        sv = self.shap_values(features)
        out = features[["claim_id"]].copy()
        out["ml_score"] = self.predict(features).round(4)
        out["ml_reason"] = _reasons(sv[:, :-1], features, self.features, sign=1, top=top, min_abs=0.05)
        return out

    def importance(self) -> pd.Series:
        gain = self.booster.get_score(importance_type="total_gain")
        s = pd.Series({f: gain.get(f, 0.0) for f in self.features})
        return (s / s.sum()).sort_values(ascending=False).round(4)

    def save(self, path) -> None:
        self.booster.save_model(str(path))

    @classmethod
    def load(cls, path, features: list[str] | None = None) -> "RiskModel":
        import xgboost as xgb
        b = xgb.Booster()
        b.load_model(str(path))
        return cls(b, features or b.feature_names)


def train_xgb(features: pd.DataFrame, labels: pd.DataFrame, feature_names: list[str] | None = None,
              seed: int = 0) -> RiskModel:
    import xgboost as xgb

    cols = feature_names or list(MODEL_FEATURES)
    m = features.merge(labels[["claim_id", "label"]], on="claim_id")
    params = {
        "objective": "binary:logistic", "eval_metric": "aucpr", "max_depth": 4, "eta": 0.1,
        "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 5, "seed": seed, "nthread": 4,
    }
    d = xgb.DMatrix(m[cols], label=m.label, feature_names=cols)
    return RiskModel(xgb.train(params, d, num_boost_round=200), cols)
