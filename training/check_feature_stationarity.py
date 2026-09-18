"""
check_feature_stationarity.py – Đo xem đặc trưng đầu vào có thật sự dừng không.

VÌ SAO CẦN SCRIPT NÀY

Câu "12/22 đặc trưng phụ thuộc mức giá tuyệt đối" là một nhận định về mã nguồn.
Hội đồng sẽ hỏi bằng chứng, và bằng chứng thuyết phục nhất là một con số đo được
trên chính dữ liệu: bao nhiêu phần trăm điểm ở tập TEST rơi ra ngoài phạm vi giá
trị mà scaler đã học ở tập TRAIN.

Với một đặc trưng dừng, tỷ lệ đó phải nhỏ (vài phần trăm — chỉ là các ngoại lai
bình thường). Với một đặc trưng trôi theo mức giá, ở một mã tăng dài hạn tỷ lệ này
tiến tới 100%: mọi giá trị tương lai đều lớn hơn mọi giá trị quá khứ, nên MinMaxScaler
đẩy hết ra ngoài [0,1] và mạng buộc phải ngoại suy vào vùng chưa từng thấy.

Script chạy phép đo đó cho CẢ HAI tập đặc trưng — tập cũ (LEGACY_FEATURE_COLUMNS)
và tập mới (get_feature_columns) — trên cùng dữ liệu, cùng cách chia tập. Bảng kết
quả đi thẳng vào báo cáo.

    python -m training.check_feature_stationarity
    python -m training.check_feature_stationarity --max-tickers 60 --csv models/stationarity.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.models.feature_engineering import (  # noqa: E402
    LEGACY_FEATURE_COLUMNS,
    TARGET_COLUMN,
    add_technical_indicators,
    clean_price_history,
    get_feature_columns,
)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def _split_indices(n_rows: int):
    """
    Dùng CHÍNH cách chia của train_tft.py. Import muộn vì train_tft kéo theo
    TensorFlow, thứ không cần cho phép đo này — nếu máy chưa cài TF thì rơi về
    bản sao chép có cảnh báo rõ ràng thay vì crash.
    """
    try:
        from backend.train_tft import split_indices
        return split_indices(n_rows)
    except Exception:
        train_ratio, val_ratio, gap = 0.70, 0.15, 60
        train_end = int(n_rows * train_ratio)
        val_start = train_end + gap
        val_end = val_start + int(n_rows * val_ratio)
        return train_end, val_start, val_end, val_end + gap


def out_of_range_rate(train: np.ndarray, test: np.ndarray) -> np.ndarray:
    """
    Tỷ lệ điểm test nằm ngoài [min, max] của train, tính riêng cho từng cột.

    Đây chính xác là điều kiện khiến MinMaxScaler cho ra giá trị ngoài [0,1].
    """
    lo, hi = train.min(axis=0), train.max(axis=0)
    outside = (test < lo) | (test > hi)
    return outside.mean(axis=0) * 100.0


def extreme_z_rate(train: np.ndarray, test: np.ndarray, sigma: float = 5.0) -> np.ndarray:
    """Tỷ lệ điểm test lệch quá `sigma` so với phân phối train (bị FeatureScaler cắt)."""
    mu = train.mean(axis=0)
    sd = train.std(axis=0)
    sd = np.where(sd == 0, 1.0, sd)
    return (np.abs((test - mu) / sd) > sigma).mean(axis=0) * 100.0


def analyse(max_tickers: int | None, csv_out: str | None) -> None:
    files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".csv"))
    files = [f for f in files if f[:-4] not in {"merged_data", "bitcoin_data", "bitcoin_data_global"}]
    if max_tickers:
        step = max(1, len(files) // max_tickers)
        files = files[::step][:max_tickers]

    new_cols = get_feature_columns()
    # ĐO TẬP CŨ PHẢI GỒM CẢ "Close".
    # LEGACY_FEATURE_COLUMNS không liệt kê Close, nhưng train_tft bản cũ vẫn đưa
    # Close vào đầu vào — và đó chính là cột PHI DỪNG NGHIÊM TRỌNG NHẤT. Bỏ nó ra
    # khỏi phép đo nghĩa là con số "22 đặc trưng" trong báo cáo không có phép đo
    # nào đứng sau, và còn làm tập cũ trông đỡ tệ hơn thực tế.
    old_cols = ["Close"] + [c for c in LEGACY_FEATURE_COLUMNS if c != "Close"]

    acc = {"old": [], "new": []}
    acc_z = {"old": [], "new": []}
    used = 0

    for filename in files:
        try:
            df = pd.read_csv(os.path.join(DATA_DIR, filename), index_col="Date", parse_dates=True)
        except Exception:
            continue
        if df.empty or TARGET_COLUMN not in df.columns:
            continue

        # Phải làm sạch ĐÚNG như train_tft làm, nếu không phép đo chạy trên một
        # phân phối dữ liệu khác với dữ liệu mô hình thật sự được huấn luyện.
        df = clean_price_history(df.sort_index())
        featured = add_technical_indicators(df)
        featured = featured.replace([np.inf, -np.inf], np.nan)

        row = {}
        ok = True
        for tag, cols in (("old", old_cols), ("new", new_cols)):
            present = [c for c in cols if c in featured.columns]
            frame = featured[present].dropna()
            if len(frame) < 400:
                ok = False
                break
            train_end, _, _, test_start = _split_indices(len(frame))
            tr = frame.iloc[:train_end].values.astype(np.float64)
            te = frame.iloc[test_start:].values.astype(np.float64)
            if len(tr) < 50 or len(te) < 50:
                ok = False
                break
            row[tag] = (present, out_of_range_rate(tr, te), extreme_z_rate(tr, te))

        if not ok:
            continue
        used += 1
        for tag in ("old", "new"):
            present, oor, z = row[tag]
            acc[tag].append(pd.Series(oor, index=present))
            acc_z[tag].append(pd.Series(z, index=present))

    if used == 0:
        print("Không có mã nào đủ dữ liệu để đo.")
        return

    old_mean = pd.concat(acc["old"], axis=1).mean(axis=1)
    new_mean = pd.concat(acc["new"], axis=1).mean(axis=1)
    new_z = pd.concat(acc_z["new"], axis=1).mean(axis=1)

    print("=" * 78)
    print(f"TÍNH DỪNG CỦA ĐẶC TRƯNG — trung bình trên {used} mã")
    print("=" * 78)
    print("\nCột 'ngoài phạm vi train' = % điểm ở tập TEST nằm ngoài [min,max] của tập TRAIN.")
    print("Càng cao nghĩa là scaler càng phải ngoại suy — đặc trưng càng phi dừng.\n")

    print(f"--- TẬP ĐẶC TRƯNG CŨ ({len(old_mean)} cột) ---")
    print(f"{'đặc trưng':<22}{'ngoài phạm vi train (%)':>26}")
    for name, v in old_mean.sort_values(ascending=False).items():
        flag = "  <-- phi dừng" if v > 20 else ""
        print(f"{name:<22}{v:>26.1f}{flag}")
    print(f"{'TRUNG BÌNH':<22}{old_mean.mean():>26.1f}")

    print(f"\n--- TẬP ĐẶC TRƯNG MỚI ({len(new_mean)} cột) ---")
    print(f"{'đặc trưng':<22}{'ngoài phạm vi train (%)':>26}{'bị cắt ở 5 sigma (%)':>24}")
    for name, v in new_mean.sort_values(ascending=False).items():
        flag = "  <-- phi dừng" if v > 20 else ""
        print(f"{name:<22}{v:>26.1f}{new_z.get(name, float('nan')):>24.2f}{flag}")
    print(f"{'TRUNG BÌNH':<22}{new_mean.mean():>26.1f}{new_z.mean():>24.2f}")

    print("\n" + "-" * 78)
    print(f"Trung bình cũ : {old_mean.mean():.1f}%   | số cột > 20%: {(old_mean > 20).sum()}/{len(old_mean)}")
    print(f"Trung bình mới: {new_mean.mean():.1f}%   | số cột > 20%: {(new_mean > 20).sum()}/{len(new_mean)}")
    print("-" * 78)

    if csv_out:
        out = pd.DataFrame({"feature": new_mean.index, "out_of_range_pct": new_mean.values,
                            "clipped_at_5sigma_pct": new_z.reindex(new_mean.index).values})
        old_df = pd.DataFrame({"feature": old_mean.index, "out_of_range_pct": old_mean.values})
        old_df["feature_set"] = "legacy"
        out["feature_set"] = "stationary-v2"
        os.makedirs(os.path.dirname(csv_out) or ".", exist_ok=True)
        pd.concat([old_df, out], ignore_index=True).to_csv(csv_out, index=False, encoding="utf-8")
        print(f"\nĐã ghi bảng số liệu: {csv_out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Đo tính dừng của đặc trưng đầu vào TFT.")
    ap.add_argument("--max-tickers", type=int, default=None, help="Chỉ đo N mã (lấy mẫu đều).")
    ap.add_argument("--csv", dest="csv_out", default=None, help="Ghi bảng kết quả ra file CSV.")
    a = ap.parse_args()
    analyse(a.max_tickers, a.csv_out)
