# -*- coding: utf-8 -*-
"""
Bước 3: Làm sạch & Kiểm định chất lượng dữ liệu (Data Profiling & Quarantine)
Thực thi trong môi trường cô lập (Python Sandbox):
- Phát hiện bất thường (Anomaly Detection):
  1. Đơn test nội bộ (is_test == 1) -> Loại bỏ 14 đơn test theo đúng kịch bản Demo
  2. Thiếu mã sản phẩm (NULL / Empty SKU)
  3. Doanh thu âm (revenue <= 0)
  4. Trùng lặp mã hóa đơn (Duplicate order_id)
  5. Lệch múi giờ (Timezone != +07:00)
- Cách ly dữ liệu lỗi (Quarantine):
  Lưu toàn bộ bản ghi bẩn sang bảng `data_quarantine` và xuất file `data_quarantine.csv`
  để kỹ sư dữ liệu (Data Engineer) xử lý sau, đảm bảo số liệu đưa vào Bước 4 sạch 100%.
"""

import os
import csv
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Tuple


QUARANTINE_CSV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "data_quarantine_export.csv"
)


def run_sandbox_profiling_and_quarantine(
    raw_records: List[Dict[str, Any]],
    db_path: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Chạy bộ quy tắc kiểm định chất lượng dữ liệu tự động trên tập dữ liệu thô.
    Trả về:
    - clean_records: Dữ liệu sạch 100% để chuyển sang Bước 4 (Deep Analytics)
    - quarantine_records: Danh sách các bản ghi bị cách ly kèm nguyên nhân chi tiết
    - summary_metrics: Thống kê số lượng từng loại lỗi phát hiện được
    """
    if not batch_id:
        batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    clean_records: List[Dict[str, Any]] = []
    quarantine_records: List[Dict[str, Any]] = []
    seen_order_ids = set()

    anomaly_counts = {
        "TEST_ORDER": 0,
        "NULL_SKU": 0,
        "NEGATIVE_REVENUE": 0,
        "DUPLICATE_ID": 0,
        "TIMEZONE_DRIFT": 0,
    }

    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+07:00")

    for row in raw_records:
        order_id = str(row.get("order_id") or "UNKNOWN")
        store_id = str(row.get("store_id") or "UNKNOWN")
        sku_id = row.get("sku_id")
        revenue = row.get("revenue")
        ts = str(row.get("order_timestamp") or "")
        is_test = int(row.get("is_test") or 0)

        detected_type = None
        detected_detail = None

        # Quy tắc 1: Đơn test nội bộ (is_test = True / 1)
        if is_test == 1:
            detected_type = "TEST_ORDER"
            detected_detail = "Đơn hàng test nội bộ của IT/QA (is_test = True) - Loại bỏ khỏi báo cáo vận hành."
            anomaly_counts["TEST_ORDER"] += 1

        # Quy tắc 2: Thiếu mã sản phẩm (NULL SKU)
        elif sku_id is None or str(sku_id).strip() == "" or str(sku_id).upper() == "NONE":
            detected_type = "NULL_SKU"
            detected_detail = "Thiếu mã định danh sản phẩm (sku_id IS NULL) do lỗi đồng bộ danh mục POS."
            anomaly_counts["NULL_SKU"] += 1

        # Quy tắc 3: Doanh thu âm (Negative Revenue)
        elif revenue is None or float(revenue) <= 0:
            detected_type = "NEGATIVE_REVENUE"
            detected_detail = f"Giá trị doanh thu âm hoặc bằng 0 bất thường (revenue = {revenue} VNĐ)."
            anomaly_counts["NEGATIVE_REVENUE"] += 1

        # Quy tắc 4: Trùng lặp mã hóa đơn (Duplicate ID)
        elif order_id in seen_order_ids:
            detected_type = "DUPLICATE_ID"
            detected_detail = f"Trùng lặp mã hóa đơn (order_id = {order_id}) do webhook gửi lặp sự kiện."
            anomaly_counts["DUPLICATE_ID"] += 1

        # Quy tắc 5: Lệch múi giờ (Không chuẩn +07:00)
        elif ts and not ts.endswith("+07:00"):
            detected_type = "TIMEZONE_DRIFT"
            detected_detail = f"Lệch múi giờ chuẩn Việt Nam +07:00 (timestamp gốc: {ts})."
            anomaly_counts["TIMEZONE_DRIFT"] += 1

        if detected_type:
            quarantine_records.append({
                "batch_id": batch_id,
                "order_id": order_id,
                "store_id": store_id,
                "anomaly_type": detected_type,
                "anomaly_detail": detected_detail,
                "raw_payload": json.dumps(row, ensure_ascii=False),
                "quarantined_at": now_iso,
            })
        else:
            seen_order_ids.add(order_id)
            clean_records.append(row)

    # Lưu vào bảng data_quarantine trong SQLite (nếu có db_path)
    if db_path and os.path.exists(db_path) and quarantine_records:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM data_quarantine WHERE batch_id = ?", (batch_id,))
        cur.executemany(
            """
            INSERT INTO data_quarantine (
                batch_id, order_id, store_id, anomaly_type,
                anomaly_detail, raw_payload, quarantined_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    q["batch_id"],
                    q["order_id"],
                    q["store_id"],
                    q["anomaly_type"],
                    q["anomaly_detail"],
                    q["raw_payload"],
                    q["quarantined_at"],
                )
                for q in quarantine_records
            ],
        )
        conn.commit()
        conn.close()

    # Xuất ra file CSV cách ly để kỹ sư dữ liệu tải về xử lý
    os.makedirs(os.path.dirname(QUARANTINE_CSV_PATH), exist_ok=True)
    with open(QUARANTINE_CSV_PATH, mode="w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["batch_id", "order_id", "store_id", "anomaly_type", "anomaly_detail", "quarantined_at", "raw_payload"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for q in quarantine_records:
            writer.writerow(q)

    total_raw = len(raw_records)
    total_clean = len(clean_records)
    total_quarantined = len(quarantine_records)

    return {
        "batch_id": batch_id,
        "total_raw_rows": total_raw,
        "total_clean_rows": total_clean,
        "total_quarantined_rows": total_quarantined,
        "data_quality_score": round((total_clean / total_raw * 100.0), 2) if total_raw else 100.0,
        "anomaly_breakdown": anomaly_counts,
        "clean_records": clean_records,
        "quarantine_records": quarantine_records,
        "quarantine_csv_path": QUARANTINE_CSV_PATH,
    }
