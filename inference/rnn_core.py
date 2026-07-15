from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def build_seq_frame(base_df: pd.DataFrame, seq_raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    all_toks = {"<pad>", "<unk>"}
    for c in ["diag_1", "diag_2", "diag_3", "insulin", "metformin"]:
        all_toks.update(seq_raw[c].fillna("<unk>").astype(str).unique().tolist())
    tok2id = {t: i for i, t in enumerate(sorted(all_toks))}
    tok2id["<pad>"] = 0

    def row_ids(r):
        return [tok2id.get(str(r[c]), tok2id["<unk>"]) for c in ["diag_1", "diag_2", "diag_3", "insulin", "metformin"]]

    out = seq_raw.copy()
    out["seq_ids"] = [row_ids(r) for r in out.to_dict("records")]
    static_cols = ["time_in_hospital", "total_visits", "active_med_count"]
    if all(c in base_df.columns for c in static_cols):
        static = base_df.set_index("encounter_id")[static_cols]
        out = out.merge(static, on="encounter_id", how="left")
        out = out.rename(columns={
            "time_in_hospital": "static_los",
            "total_visits": "static_visits",
            "active_med_count": "static_meds",
        })
    else:
        out["static_los"] = 0
        out["static_visits"] = 0
        out["static_meds"] = 0
    out[["static_los", "static_visits", "static_meds"]] = out[["static_los", "static_visits", "static_meds"]].fillna(0)
    return out, {"tok2id": tok2id}


def train_rnn_model(
    seq_train: pd.DataFrame,
    y_train: pd.Series,
    epochs: int = 5,
    emb: int = 16,
    hidden: int = 32,
    lr: float = 1e-3,
    token_maps: dict | None = None,
):
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError:
        return None, None

    class SmallRNN(nn.Module):
        def __init__(self, vocab, emb=16, hidden=32):
            super().__init__()
            self.emb = nn.Embedding(vocab, emb, padding_idx=0)
            self.rnn = nn.GRU(emb, hidden, batch_first=True)
            self.fc = nn.Linear(hidden + 3, 1)

        def forward(self, seq, static):
            x = self.emb(seq)
            _, h = self.rnn(x)
            h = h.squeeze(0)
            z = torch.cat([h, static], dim=1)
            return self.fc(z).squeeze(1)

    vocab = len(token_maps["tok2id"]) if token_maps else max(max(max(ids) for ids in seq_train["seq_ids"]), 1) + 1
    model = SmallRNN(vocab, emb=emb, hidden=hidden)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss()

    seq_t = torch.tensor(np.stack(seq_train["seq_ids"].to_numpy()), dtype=torch.long)
    st_t = torch.tensor(seq_train[["static_los", "static_visits", "static_meds"]].to_numpy(np.float32))
    y_t = torch.tensor(y_train.to_numpy(np.float32))
    loader = DataLoader(TensorDataset(seq_t, st_t, y_t), batch_size=256, shuffle=True)

    model.train()
    for _ in range(epochs):
        for xb, sb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(xb, sb), yb)
            loss.backward()
            opt.step()
    model.eval()
    return model, torch


def predict_rnn_prob(model, torch_mod, seq_df: pd.DataFrame) -> np.ndarray:
    if model is None or len(seq_df) == 0:
        return np.array([])
    with torch_mod.no_grad():
        seq_t = torch_mod.tensor(np.stack(seq_df["seq_ids"].to_numpy()), dtype=torch_mod.long)
        st_t = torch_mod.tensor(seq_df[["static_los", "static_visits", "static_meds"]].to_numpy(np.float32))
        logits = model(seq_t, st_t)
        return torch_mod.sigmoid(logits).numpy()


def encode_seq_row(row: dict, token_maps: dict) -> list[int]:
    tok2id = token_maps["tok2id"]
    return [tok2id.get(str(row.get(c, "<unk>")), tok2id["<unk>"]) for c in
            ["diag_1", "diag_2", "diag_3", "insulin", "metformin"]]


def row_to_seq_frame(row: dict, token_maps: dict | None = None) -> pd.DataFrame:
    merged = dict(row)
    static_los = float(merged.get("time_in_hospital", 0) or 0)
    static_visits = float(merged.get("total_visits", 0) or 0)
    static_meds = float(merged.get("active_med_count", merged.get("num_medications", 0)) or 0)
    if token_maps:
        seq_ids = encode_seq_row(merged, token_maps)
    else:
        seq_raw = pd.DataFrame([{
            "encounter_id": merged.get("encounter_id", 0),
            "diag_1": merged.get("diag_1", "<unk>"),
            "diag_2": merged.get("diag_2", "<unk>"),
            "diag_3": merged.get("diag_3", "<unk>"),
            "insulin": merged.get("insulin", "<unk>"),
            "metformin": merged.get("metformin", "<unk>"),
        }])
        base = pd.DataFrame([{"encounter_id": 0, "time_in_hospital": static_los,
                              "total_visits": static_visits, "active_med_count": static_meds}])
        seq_frame, _ = build_seq_frame(base, seq_raw)
        return seq_frame
    return pd.DataFrame([{
        "seq_ids": seq_ids,
        "static_los": static_los,
        "static_visits": static_visits,
        "static_meds": static_meds,
    }])


def _rnn_arch_params() -> tuple[int, int]:
    try:
        from ml.tuning import get_rnn_params
        p = get_rnn_params()
        return int(p.get("emb", 16)), int(p.get("hidden", 32))
    except Exception:
        return 16, 32


def load_rnn_chat_artifacts(models_dir: Path | None = None):
    models_dir = models_dir or ROOT / "models"
    pt = models_dir / "rnn_primary.pt"
    tok = models_dir / "rnn_token_maps.json"
    if not pt.exists() or not tok.exists():
        return None, None, None
    try:
        import torch
        import torch.nn as nn

        token_maps = json.loads(tok.read_text(encoding="utf-8"))
        vocab = len(token_maps["tok2id"])
        emb, hidden = _rnn_arch_params()

        class SmallRNN(nn.Module):
            def __init__(self, vocab_size, emb_size=16, hidden_size=32):
                super().__init__()
                self.emb = nn.Embedding(vocab_size, emb_size, padding_idx=0)
                self.rnn = nn.GRU(emb_size, hidden_size, batch_first=True)
                self.fc = nn.Linear(hidden_size + 3, 1)

            def forward(self, seq, static):
                x = self.emb(seq)
                _, h = self.rnn(x)
                h = h.squeeze(0)
                z = torch.cat([h, static], dim=1)
                return self.fc(z).squeeze(1)

        model = SmallRNN(vocab, emb_size=emb, hidden_size=hidden)
        model.load_state_dict(torch.load(pt, map_location="cpu", weights_only=True))
        model.eval()
        return model, token_maps, torch
    except Exception:
        return None, None, None
