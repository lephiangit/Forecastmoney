"""
evaluate_tft.py – So sánh TFT với các baseline kinh điển.

Đây là script trả lời câu hỏi mà hội đồng chấm đồ án gần như chắc chắn sẽ đặt ra:
"Mô hình của em tốt hơn phép dự báo ngây thơ bao nhiêu phần trăm?"

Nếu TFT không đánh bại được naive forecast, đó KHÔNG phải là thất bại của đồ án —
đó là một phát hiện có giá trị, và là kết quả rất thường gặp với dữ liệu giá tài chính
(giả thuyết thị trường hiệu quả dạng yếu nói rằng giá xấp xỉ một bước ngẫu nhiên).
Điều quan trọng là báo cáo phải trung thực về con số, và biết giải thích tại sao.

────────────────────────────────────────────────────────────────────────────────
CÁC BASELINE

  naive     Giá ngày mai = giá hôm nay. Đây là baseline khó đánh bại nhất với
            chuỗi giá, và là baseline BẮT BUỘC phải có trong mọi báo cáo nghiêm túc.
  ma5/ma20  Giá ngày mai = trung bình động 5 / 20 phiên gần nhất.
  drift     Ngoại suy tuyến tính theo xu hướng 5 phiên gần nhất.

CÁC CHỈ SỐ

  MAE       Sai số tuyệt đối trung bình (cùng đơn vị với giá).
  RMSE      Căn bậc hai sai số bình phương trung bình — phạt nặng sai số lớn.
  MAPE      Sai số phần trăm tuyệt đối trung bình — cho phép so sánh giữa các mã
            có mức giá rất khác nhau.
  DirAcc    Độ chính xác về HƯỚNG (tăng/giảm). Với giao dịch, chỉ số này thường
            quan trọng hơn sai số tuyệt đối. Ngưỡng tham chiếu là 50% (đoán mò).
  Coverage  Tỷ lệ giá thực tế nằm trong khoảng [p10, p90]. Nếu dải tin cậy được
            hiệu chỉnh tốt, con số này phải xấp xỉ 80%. Lệch nhiều nghĩa là mô hình
            đang quá tự tin (dưới 80%) hoặc quá thận trọng (trên 80%).

────────────────────────────────────────────────────────────────────────────────
CÁCH DÙNG

    python -m backend.evaluate_tft                    # đánh giá toàn bộ data/
    python -m backend.evaluate_tft --tickers BTC-USD,AAPL,FPT.VN
    (chỉ hỗ trợ horizon = 1 — xem chốt chặn trong main())

Kết quả được ghi ra models/evaluation_report.md (dán thẳng vào báo cáo được)
kèm models/evaluation_results.csv để vẽ biểu đồ.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

# Khi stdout được redirect ra file (vd: `python -m ... *> log.txt` trong PowerShell),
# Python KHÔNG dùng UTF-8 nữa mà rơi về bảng mã mặc định của hệ thống (cp1258 trên
# Windows tiếng Việt) — bảng mã này thiếu một số ký tự có dấu, khiến script crash
# ngay dòng print() đầu tiên có tiếng Việt. Ép UTF-8 tường minh để in ra màn hình
# lẫn ghi ra file đều hoạt động như nhau.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.models.feature_engineering import add_technical_indicators, get_feature_columns
from backend.train_tft import LOOK_BACK, SKIP_FILES, TRAIN_RATIO, VALIDATION_GAP

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

MIN_TEST_SAMPLES = 30


# ══════════════════════════════════════════════════════════════════════════════
#  CHỈ SỐ
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, last_known: np.ndarray) -> Dict:
    """Tính bộ chỉ số so sánh giữa giá thực tế và giá dự báo."""
    errors = y_pred - y_true
    abs_errors = np.abs(errors)

    # Bỏ các điểm có giá thực tế bằng 0 để MAPE không chia cho 0.
    nonzero = y_true != 0
    mape = float(np.mean(abs_errors[nonzero] / np.abs(y_true[nonzero])) * 100) if nonzero.any() else float("nan")

    # Độ chính xác về hướng: so sánh dấu của biến động dự báo và biến động thực tế.
    pred_direction = np.sign(y_pred - last_known)
    true_direction = np.sign(y_true - last_known)
    # Bỏ các phiên giá đứng yên — không có hướng nào để đoán đúng hay sai.
    moved = true_direction != 0
    dir_acc = float(np.mean(pred_direction[moved] == true_direction[moved]) * 100) if moved.any() else float("nan")

    return {
        "mae": float(np.mean(abs_errors)),
        "rmse": float(np.sqrt(np.mean(errors ** 2))),
        "mape": mape,
        "dir_acc": dir_acc,
        "n": int(len(y_true)),
    }


def compute_coverage(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    """Tỷ lệ giá thực tế nằm trong dải tin cậy dự báo."""
    inside = (y_true >= lower) & (y_true <= upper)
    return float(np.mean(inside) * 100)


# ══════════════════════════════════════════════════════════════════════════════
#  BASELINE
# ══════════════════════════════════════════════════════════════════════════════

def baseline_predictions(closes: np.ndarray, indices: np.ndarray, horizon: int) -> Dict[str, np.ndarray]:
    """
    Sinh dự báo của các baseline.

    `indices` là vị trí của điểm gốc dự báo (phiên cuối cùng mà mô hình được thấy).
    Baseline dự báo cho phiên `indices + horizon`.
    """
    naive = closes[indices]

    ma5 = np.array([closes[max(0, i - 4) : i + 1].mean() for i in indices])
    ma20 = np.array([closes[max(0, i - 19) : i + 1].mean() for i in indices])

    # Drift: kéo dài xu hướng trung bình của 5 phiên gần nhất thêm `horizon` bước.
    drift = np.array(
        [
            closes[i] + (closes[i] - closes[max(0, i - 5)]) / 5 * horizon
            for i in indices
        ]
    )

    return {"naive": naive, "ma5": ma5, "ma20": ma20, "drift": drift}


# ══════════════════════════════════════════════════════════════════════════════
#  ĐÁNH GIÁ MỘT MÃ
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_ticker(model, ticker: str, horizon: int = 1) -> Optional[Dict]:
    """
    Đánh giá TFT và các baseline trên phần dữ liệu KHÔNG dùng để huấn luyện.

    Cách chia giống hệt lúc huấn luyện (theo thời gian, có khoảng trống ở ranh giới)
    để đảm bảo mọi điểm đánh giá đều thực sự nằm ngoài tầm nhìn của mô hình.

    Ghi chú về horizon > 1: ở đây dùng dự báo MỘT BƯỚC lặp lại, tức mỗi điểm đánh giá
    đều xuất phát từ dữ liệu thật, không phải dự báo tự hồi quy nhiều bước. Cách này
    đo được chất lượng mô hình mà không lẫn với sai số tích luỹ — nếu muốn đo
    dự báo nhiều bước thật, dùng `run_tft_forecast` trực tiếp (chậm hơn nhiều).
    """
    path = os.path.join(DATA_DIR, f"{ticker}.csv")
    if not os.path.exists(path):
        return None

    try:
        df = pd.read_csv(path, index_col="Date", parse_dates=True).sort_index()
    except Exception as e:
        print(f"  {ticker}: không đọc được file ({e})")
        return None

    if df.empty or "Close" not in df.columns:
        return None

    df = add_technical_indicators(df)
    available = [c for c in get_feature_columns() if c in df.columns]
    all_cols = ["Close"] + available
    df_clean = df[all_cols].dropna()

    split_idx = int(len(df_clean) * TRAIN_RATIO)
    train_slice = df_clean.iloc[:split_idx]
    test_slice = df_clean.iloc[split_idx + VALIDATION_GAP :]

    if len(test_slice) < LOOK_BACK + horizon + MIN_TEST_SAMPLES:
        return None
    if len(train_slice) < LOOK_BACK + 10:
        return None

    # Scaler khớp trên tập train — giống hệt điều kiện lúc huấn luyện.
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaler.fit(train_slice.values)
    scaled_test = scaler.transform(test_slice.values)

    closes = test_slice["Close"].values

    # Dựng toàn bộ cửa sổ đầu vào rồi predict một lần theo lô — nhanh hơn hàng chục
    # lần so với gọi model.predict cho từng điểm.
    windows, target_idx = [], []
    for i in range(LOOK_BACK - 1, len(scaled_test) - horizon):
        windows.append(scaled_test[i - LOOK_BACK + 1 : i + 1])
        target_idx.append(i)

    if not windows:
        return None

    X = np.array(windows, dtype=np.float32)
    origin_idx = np.array(target_idx)
    y_true = closes[origin_idx + horizon]
    last_known = closes[origin_idx]

    preds_return = model.predict(X, verbose=0, batch_size=256)

    # Ràng buộc quantile không giảm dần, phòng trường hợp mạng cho ra thứ tự sai.
    q_sorted = np.sort(preds_return[:, :3], axis=1)

    # Model dự đoán % THAY ĐỔI GIÁ (return) so với phiên cuối cùng trong cửa sổ,
    # KHÔNG phải mức giá tuyệt đối — xem TARGET_TYPE trong backend/train_tft.py.
    # Tái tạo giá bằng last_known * (1 + return/100) thay vì inverse_transform qua
    # scaler như bản cũ — cách cũ là nguyên nhân gây lệch scale nghiêm trọng khi
    # giá thực tế vượt phạm vi scaler từng thấy lúc train (xem
    # models/danh_gia_ket_qua.md).
    tft_lower = last_known * (1.0 + q_sorted[:, 0] / 100.0)
    tft_median = last_known * (1.0 + q_sorted[:, 1] / 100.0)
    tft_upper = last_known * (1.0 + q_sorted[:, 2] / 100.0)

    results = {
        "ticker": ticker,
        "test_samples": len(y_true),
        "test_period": f"{test_slice.index[LOOK_BACK - 1].date()} → {test_slice.index[-1].date()}",
        "models": {"tft": compute_metrics(y_true, tft_median, last_known)},
        "coverage_p10_p90": compute_coverage(y_true, tft_lower, tft_upper),
    }

    for name, preds in baseline_predictions(closes, origin_idx, horizon).items():
        results["models"][name] = compute_metrics(y_true, preds, last_known)

    return results


# ══════════════════════════════════════════════════════════════════════════════
#  BÁO CÁO
# ══════════════════════════════════════════════════════════════════════════════

MODEL_LABELS = {
    "tft": "TFT (mô hình đề xuất)",
    "naive": "Naive (giá hôm nay)",
    "ma5": "Trung bình động 5 phiên",
    "ma20": "Trung bình động 20 phiên",
    "drift": "Ngoại suy xu hướng",
}


def aggregate(all_results: List[Dict]) -> Dict[str, Dict]:
    """Gộp kết quả của mọi mã. MAPE và DirAcc lấy trung bình vì chúng không có đơn vị."""
    aggregated: Dict[str, Dict] = {}
    for model_name in MODEL_LABELS:
        mapes, dir_accs, n_total = [], [], 0
        for r in all_results:
            m = r["models"].get(model_name)
            if not m:
                continue
            if not np.isnan(m["mape"]):
                mapes.append(m["mape"])
            if not np.isnan(m["dir_acc"]):
                dir_accs.append(m["dir_acc"])
            n_total += m["n"]
        if mapes:
            aggregated[model_name] = {
                "mape": float(np.mean(mapes)),
                "dir_acc": float(np.mean(dir_accs)) if dir_accs else float("nan"),
                "n": n_total,
                "tickers": len(mapes),
            }
    return aggregated


def build_markdown_report(all_results: List[Dict], horizon: int) -> str:
    agg = aggregate(all_results)
    tft_mape = agg.get("tft", {}).get("mape")
    naive_mape = agg.get("naive", {}).get("mape")

    lines = [
        "# Kết quả đánh giá mô hình TFT",
        "",
        f"*Tạo lúc: {datetime.now().strftime('%d/%m/%Y %H:%M')}*",
        "",
        f"- **Horizon đánh giá:** {horizon} phiên",
        f"- **Số mã được đánh giá:** {len(all_results)}",
        f"- **Cách chia dữ liệu:** theo thời gian, {TRAIN_RATIO:.0%} đầu để huấn luyện, "
        f"phần cuối để kiểm thử, cách nhau {VALIDATION_GAP} phiên",
        "",
        "## 1. Kết quả tổng hợp (trung bình trên tất cả các mã)",
        "",
        "| Mô hình | MAPE (%) ↓ | Độ chính xác hướng (%) ↑ | Số mã |",
        "|---|---:|---:|---:|",
    ]

    for name, label in MODEL_LABELS.items():
        m = agg.get(name)
        if not m:
            continue
        highlight = "**" if name == "tft" else ""
        dir_acc = f"{m['dir_acc']:.1f}" if not np.isnan(m["dir_acc"]) else "—"
        lines.append(
            f"| {highlight}{label}{highlight} | {highlight}{m['mape']:.3f}{highlight} | "
            f"{highlight}{dir_acc}{highlight} | {m['tickers']} |"
        )

    lines.append("")

    # ── Kết luận tự động, viết trung thực theo đúng con số đo được ──
    lines.append("## 2. Nhận xét")
    lines.append("")

    if tft_mape is not None and naive_mape is not None:
        improvement = (naive_mape - tft_mape) / naive_mape * 100
        if improvement > 5:
            lines.append(
                f"TFT cho MAPE thấp hơn baseline naive **{improvement:.1f}%** "
                f"({tft_mape:.3f}% so với {naive_mape:.3f}%). Đây là mức cải thiện có ý nghĩa "
                "với dữ liệu giá tài chính."
            )
        elif improvement > 0:
            lines.append(
                f"TFT chỉ tốt hơn baseline naive **{improvement:.1f}%** "
                f"({tft_mape:.3f}% so với {naive_mape:.3f}%). Mức chênh lệch này nhỏ và "
                "cần kiểm định thống kê trước khi khẳng định mô hình thực sự tốt hơn."
            )
        else:
            lines.append(
                f"TFT **chưa** vượt được baseline naive ({tft_mape:.3f}% so với {naive_mape:.3f}%). "
                "Đây là kết quả thường gặp với chuỗi giá tài chính và hoàn toàn có thể trình bày "
                "trong báo cáo: nó cho thấy giá đóng cửa ngắn hạn hành xử gần với bước ngẫu nhiên, "
                "phù hợp với giả thuyết thị trường hiệu quả dạng yếu. Hướng cải thiện nên tập trung "
                "vào dự báo HƯỚNG và biến động thay vì dự báo mức giá tuyệt đối."
            )
        lines.append("")

    tft_dir = agg.get("tft", {}).get("dir_acc")
    if tft_dir is not None and not np.isnan(tft_dir):
        if tft_dir > 55:
            lines.append(
                f"Độ chính xác về hướng đạt **{tft_dir:.1f}%**, cao hơn mức đoán mò (50%). "
                "Đây là chỉ số đáng nhấn mạnh trong báo cáo vì nó liên quan trực tiếp tới "
                "chất lượng tín hiệu giao dịch."
            )
        else:
            lines.append(
                f"Độ chính xác về hướng đạt **{tft_dir:.1f}%**, xấp xỉ mức đoán mò (50%). "
                "Cần nêu rõ hạn chế này trong báo cáo thay vì chỉ trình bày MAE/RMSE."
            )
        lines.append("")

    coverages = [r["coverage_p10_p90"] for r in all_results if r.get("coverage_p10_p90") is not None]
    if coverages:
        mean_coverage = float(np.mean(coverages))
        lines.append(
            f"**Hiệu chỉnh dải tin cậy:** khoảng [p10, p90] bao phủ **{mean_coverage:.1f}%** "
            "số quan sát thực tế (giá trị lý tưởng là 80%). "
            + (
                "Dải tin cậy được hiệu chỉnh tốt."
                if 72 <= mean_coverage <= 88
                else (
                    "Dải quá hẹp — mô hình đang tự tin hơn mức nó xứng đáng, cần nêu rõ hạn chế này."
                    if mean_coverage < 72
                    else "Dải quá rộng — mô hình thận trọng quá mức, khoảng dự báo ít giá trị sử dụng."
                )
            )
        )
        lines.append("")

    # ── Bảng chi tiết theo từng mã ──
    lines.extend(
        [
            "## 3. Chi tiết theo từng mã",
            "",
            "| Mã | Giai đoạn kiểm thử | Mẫu | MAPE TFT | MAPE Naive | Hướng TFT | Coverage |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )

    for r in sorted(all_results, key=lambda x: x["models"]["tft"]["mape"]):
        tft = r["models"]["tft"]
        naive = r["models"].get("naive", {})
        lines.append(
            f"| {r['ticker']} | {r['test_period']} | {r['test_samples']} | "
            f"{tft['mape']:.3f}% | {naive.get('mape', float('nan')):.3f}% | "
            f"{tft['dir_acc']:.1f}% | {r['coverage_p10_p90']:.1f}% |"
        )

    lines.extend(
        [
            "",
            "## 4. Ghi chú về phương pháp",
            "",
            "- Toàn bộ điểm đánh giá nằm ngoài tập huấn luyện, tách theo thời gian "
            "(không trộn ngẫu nhiên), nên không có rò rỉ dữ liệu.",
            "- Scaler được khớp riêng trên tập huấn luyện của từng mã; giá trị min/max "
            "của giai đoạn kiểm thử không hề tham gia vào quá trình huấn luyện.",
            f"- Đánh giá dùng dự báo {horizon} bước xuất phát từ dữ liệu thật ở mỗi điểm gốc, "
            "không phải dự báo tự hồi quy nhiều bước — nhờ vậy chỉ số đo được phản ánh chất lượng "
            "mô hình, không lẫn với sai số tích luỹ.",
            "- Baseline naive (giá ngày mai = giá hôm nay) là chuẩn so sánh khó vượt qua nhất "
            "đối với chuỗi giá tài chính; mọi báo cáo nghiêm túc đều cần đối chiếu với nó.",
            "",
        ]
    )

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Đánh giá TFT so với các baseline")
    parser.add_argument("--tickers", type=str, default=None, help="Danh sách mã, phân tách bằng dấu phẩy")
    parser.add_argument("--horizon", type=int, default=1, help="Số phiên dự báo trước (mặc định 1)")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số mã đánh giá")
    args = parser.parse_args()

    import tensorflow as tf

    from backend.models.tft_model import quantile_loss

    model_path = os.path.join(MODELS_DIR, "global_tft.keras")
    if not os.path.exists(model_path):
        print(f"Không tìm thấy mô hình tại {model_path}.")
        print("Chạy `python -m backend.train_tft` trước.")
        sys.exit(1)

    print("Đang nạp mô hình...")
    model = tf.keras.models.load_model(
        model_path, custom_objects={"loss_fn": quantile_loss([0.1, 0.5, 0.9])}
    )

    # Script này diễn giải output của model là % THAY ĐỔI GIÁ (return), không phải
    # mức giá tuyệt đối — cảnh báo nếu checkpoint đang nạp được huấn luyện trước
    # khi đổi sang target này, để không đọc nhầm kết quả.
    meta_path = os.path.join(MODELS_DIR, "tft_meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            target_type = meta.get("target_type", "close_price_scaled")
            if target_type != "return_pct_1step":
                print(
                    f"CẢNH BÁO: checkpoint có target_type='{target_type}', script này đang "
                    "diễn giải output là % return. Kết quả sẽ SAI nếu model thực ra dự đoán "
                    "giá tuyệt đối. Train lại với `python -m backend.train_tft --fresh`."
                )
        except Exception:
            pass

    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = sorted(
            f[:-4] for f in os.listdir(DATA_DIR) if f.endswith(".csv") and f[:-4] not in SKIP_FILES
        )
    if args.limit:
        tickers = tickers[: args.limit]

    # CHỐT CHẶN: mô hình được huấn luyện với target "return_pct_1step" — % thay đổi
    # giá từ phiên cuối cửa sổ sang ĐÚNG PHIÊN KẾ TIẾP. Hàm evaluate_ticker() chỉ
    # gọi model đúng MỘT lần rồi áp % đó lên `last_known`, nhưng lại so với
    # `closes[i + horizon]`. Với horizon > 1, đó là đem dự báo 1 phiên so với biến
    # động thật của nhiều phiên — mọi chỉ số MAPE/DirAcc thu được đều vô nghĩa và
    # sẽ làm mô hình trông tệ hơn thực tế. Dự báo nhiều bước phải đi qua
    # run_tft_forecast() (tự hồi quy), không phải hàm này.
    if args.horizon != 1:
        print(
            f"LỖI: --horizon {args.horizon} không hợp lệ với script này.\n"
            "Mô hình dự đoán % thay đổi giá cho ĐÚNG MỘT phiên kế tiếp, nên chỉ đánh giá\n"
            "được ở horizon = 1. Muốn đánh giá nhiều bước, dùng dự báo tự hồi quy qua\n"
            "backend.models.forecaster.run_tft_forecast()."
        )
        return

    print(f"Đánh giá {len(tickers)} mã, horizon = {args.horizon} phiên\n")

    all_results = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker}...", end=" ", flush=True)
        try:
            result = evaluate_ticker(model, ticker, args.horizon)
        except Exception as e:
            print(f"lỗi: {type(e).__name__}: {e}")
            continue

        if result is None:
            print("bỏ qua (không đủ dữ liệu)")
            continue

        tft = result["models"]["tft"]
        naive = result["models"]["naive"]
        verdict = "tốt hơn naive" if tft["mape"] < naive["mape"] else "kém hơn naive"
        print(f"MAPE {tft['mape']:.3f}% ({verdict})")
        all_results.append(result)

    if not all_results:
        print("\nKhông có mã nào đủ dữ liệu để đánh giá.")
        sys.exit(1)

    os.makedirs(MODELS_DIR, exist_ok=True)

    # ── Báo cáo Markdown ──
    report_path = os.path.join(MODELS_DIR, "evaluation_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(build_markdown_report(all_results, args.horizon))

    # ── CSV để vẽ biểu đồ ──
    rows = []
    for r in all_results:
        for model_name, m in r["models"].items():
            rows.append(
                {
                    "ticker": r["ticker"],
                    "model": model_name,
                    "mae": m["mae"],
                    "rmse": m["rmse"],
                    "mape": m["mape"],
                    "directional_accuracy": m["dir_acc"],
                    "samples": m["n"],
                    "coverage_p10_p90": r["coverage_p10_p90"] if model_name == "tft" else None,
                }
            )
    csv_path = os.path.join(MODELS_DIR, "evaluation_results.csv")
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    # ── JSON thô ──
    json_path = os.path.join(MODELS_DIR, "evaluation_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {"horizon": args.horizon, "generated_at": datetime.now().isoformat(), "results": all_results},
            f,
            ensure_ascii=False,
            indent=2,
        )

    # ── Tóm tắt ra màn hình ──
    agg = aggregate(all_results)
    print("\n" + "=" * 70)
    print("KẾT QUẢ TỔNG HỢP")
    print("=" * 70)
    print(f"{'Mô hình':<28} {'MAPE (%)':>10} {'Hướng (%)':>12}")
    print("-" * 70)
    for name, label in MODEL_LABELS.items():
        m = agg.get(name)
        if m:
            dir_acc = f"{m['dir_acc']:.1f}" if not np.isnan(m["dir_acc"]) else "—"
            print(f"{label:<28} {m['mape']:>10.3f} {dir_acc:>12}")
    print("=" * 70)
    print(f"\nBáo cáo:  {report_path}")
    print(f"CSV:      {csv_path}")
    print(f"JSON:     {json_path}")


if __name__ == "__main__":
    main()
