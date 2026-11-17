# -*- coding: utf-8 -*-
"""
Module khởi tạo SQLite Data Warehouse & Dữ liệu mẫu chuẩn kịch bản Demo:
- Bảng stores, products, orders (chứa cả đơn hợp lệ, 14 đơn test nội bộ, và các bản ghi lỗi bẩn để test Bước 3 Quarantine)
- Bảng inventory_logs (chứa dữ liệu tồn kho thực tế vs POS, thời tiết, khuyến mãi, giá đối thủ)
- Bảng data_quarantine & vector_feedback_memory
- Xuất kèm file CSV mẫu để người dùng test tính năng Upload File.
"""

import os
import csv
import json
import sqlite3
import random
from datetime import datetime, timedelta

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_DIR = "/tmp/beardata" if os.environ.get("VERCEL") else _DEFAULT_DATA_DIR
DB_PATH = os.path.join(DB_DIR, "enterprise_dw.db")
SAMPLE_CSV_PATH = os.path.join(DB_DIR, "sample_orders_yesterday.csv")


def init_data_warehouse(force_rebuild: bool = False) -> str:
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(DB_PATH) and not force_rebuild:
        return DB_PATH

    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Tạo bảng stores
    cur.execute("""
        CREATE TABLE stores (
            store_id TEXT PRIMARY KEY,
            store_name TEXT,
            region TEXT,
            manager_role TEXT,
            manager_name TEXT,
            manager_email TEXT
        )
    """)

    stores_data = [
        ("CH01", "Cửa hàng #01 - Hoàn Kiếm", "North", "Manager_Region_North", "Nguyễn Văn Bắc", "bac.nv@enterprise.vn"),
        ("CH02", "Cửa hàng #02 - Đống Đa", "North", "Manager_Region_North", "Nguyễn Văn Bắc", "bac.nv@enterprise.vn"),
        ("CH03", "Cửa hàng #03 - Ba Đình", "North", "Manager_Region_North", "Nguyễn Văn Bắc", "bac.nv@enterprise.vn"),
        ("CH04", "Cửa hàng #04 - Cầu Giấy", "North", "Manager_Region_North", "Nguyễn Văn Bắc", "bac.nv@enterprise.vn"),
        ("CH05", "Cửa hàng #05 - Thanh Xuân", "North", "Manager_Region_North", "Nguyễn Văn Bắc", "bac.nv@enterprise.vn"),
        ("CH06", "Cửa hàng #06 - Long Biên", "North", "Manager_Region_North", "Nguyễn Văn Bắc", "bac.nv@enterprise.vn"),
        ("CH07", "Cửa hàng #07 - Quận 1 (HCM)", "South", "Manager_Region_South", "Trần Thị Nam", "nam.tt@enterprise.vn"),
        ("CH08", "Cửa hàng #08 - Quận 7 (HCM)", "South", "Manager_Region_South", "Trần Thị Nam", "nam.tt@enterprise.vn"),
    ]
    cur.executemany("INSERT INTO stores VALUES (?, ?, ?, ?, ?, ?)", stores_data)

    # 2. Tạo bảng products
    cur.execute("""
        CREATE TABLE products (
            sku_id TEXT PRIMARY KEY,
            product_name TEXT,
            category TEXT,
            unit_price REAL,
            cost_price REAL
        )
    """)

    products_data = [
        ("SKU-001", "Sữa tươi thanh trùng Organic 1L", "Fresh Food", 65000, 45000),
        ("SKU-002", "Ức gà phi lê tươi CP 500g", "Fresh Food", 58000, 40000),
        ("SKU-003", "Trà Ô Long đóng chai 500ml", "Beverage", 22000, 12000),
        ("SKU-004", "Nước ép Cam nguyên chất 1L", "Beverage", 75000, 48000),
        ("SKU-005", "Mì trộn Hàn Quốc gói 5", "FMCG", 89000, 62000),
        ("SKU-006", "Gạo ST25 túi 5kg", "FMCG", 185000, 145000),
        ("SKU-007", "Sữa rửa mặt dịu nhẹ 150ml", "Personal Care", 145000, 85000),
        ("SKU-008", "Combo Rau củ tươi theo ngày", "Fresh Food", 49000, 31000),
    ]
    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", products_data)

    # 3. Tạo bảng orders
    cur.execute("""
        CREATE TABLE orders (
            row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            store_id TEXT,
            sku_id TEXT,
            order_timestamp TEXT,
            order_date TEXT,
            order_hour INTEGER,
            status TEXT,
            quantity INTEGER,
            revenue REAL,
            cost REAL,
            cancel_reason TEXT,
            pos_sync_delay_min INTEGER,
            is_test INTEGER,
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT
        )
    """)

    # 4. Tạo bảng inventory_logs
    cur.execute("""
        CREATE TABLE inventory_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id TEXT,
            sku_id TEXT,
            log_date TEXT,
            hour_slot TEXT,
            physical_stock INTEGER,
            pos_stock INTEGER,
            stockout_rate REAL,
            promo_active INTEGER,
            weather_condition TEXT,
            competitor_price_index REAL
        )
    """)

    # 5. Tạo bảng data_quarantine
    cur.execute("""
        CREATE TABLE data_quarantine (
            quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT,
            order_id TEXT,
            store_id TEXT,
            anomaly_type TEXT,
            anomaly_detail TEXT,
            raw_payload TEXT,
            quarantined_at TEXT
        )
    """)

    # 6. Tạo bảng vector_feedback_memory (Bước 6: Feedback Loop)
    cur.execute("""
        CREATE TABLE vector_feedback_memory (
            memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_pattern TEXT,
            user_role TEXT,
            feedback_type TEXT,
            kpi_override_json TEXT,
            user_note TEXT,
            created_at TEXT
        )
    """)

    # Seed một bản ghi bộ nhớ dài hạn mẫu
    cur.execute(
        """
        INSERT INTO vector_feedback_memory (query_pattern, user_role, feedback_type, kpi_override_json, user_note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "tỷ lệ hủy đơn",
            "Manager_Region_North",
            "KPI_RULE_CONFIRMED",
            json.dumps({"exclude_test_orders": True, "risk_threshold_pct": 15.0}),
            "Luôn loại bỏ đơn test nội bộ (is_test=1) và cảnh báo đỏ nếu tỷ lệ hủy cửa hàng > 15%.",
            "2026-11-15T09:00:00+07:00",
        ),
    )

    # Ngày tham chiếu: Hôm qua là 2026-11-15
    yesterday_str = "2026-11-15"
    random.seed(42)

    orders_rows = []
    order_seq = 10001

    # Cấu hình số lượng đơn hợp lệ ngày hôm qua cho từng cửa hàng để ra đúng con số Demo:
    # Cửa hàng #04 (CH04): 250 đơn hợp lệ, 46 đơn hủy -> Tỷ lệ hủy = 18.4% (gấp ~3 lần TB vùng ~6.1%)
    # Trong 46 đơn hủy của CH04: 38 đơn hủy (82.6% ~ 82%) rơi vào khung 17h-19h do hết tồn kho thực tế nhưng POS chưa đồng bộ kịp!
    yesterday_store_specs = [
        ("CH04", 250, 46),  # 18.40%
        ("CH02", 200, 16),  # 8.00%
        ("CH01", 200, 13),  # 6.50%
        ("CH05", 200, 11),  # 5.50%
        ("CH03", 200, 9),   # 4.50%
        ("CH06", 200, 7),   # 3.50%
        ("CH07", 220, 11),  # 5.00% (South - sẽ bị chặn bởi RBAC nếu role là Manager_Region_North)
        ("CH08", 180, 9),   # 5.00% (South)
    ]

    sample_names = ["Phạm Minh Tuấn", "Lê Hoàng Lan", "Nguyễn Thu Hà", "Trần Quốc Bảo", "Vũ Thị Mai", "Đặng Tiến Dũng"]

    for store_id, total_valid, cancelled_count in yesterday_store_specs:
        completed_count = total_valid - cancelled_count

        # Sinh các đơn completed
        for i in range(completed_count):
            sku, _, _, price, cost = random.choice(products_data)
            qty = random.choice([1, 1, 2, 2, 3])
            hr = random.choice([8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21])
            minute = random.randint(0, 59)
            ts = f"{yesterday_str}T{hr:02d}:{minute:02d}:00+07:00"
            cname = random.choice(sample_names)
            cphone = f"09{random.randint(10000000, 99999999)}"
            cemail = f"khachhang{order_seq}@gmail.com"
            orders_rows.append((
                f"ORD-{order_seq}", store_id, sku, ts, yesterday_str, hr,
                "completed", qty, float(price * qty), float(cost * qty),
                "none", random.randint(1, 5), 0, cname, cphone, cemail
            ))
            order_seq += 1

        # Sinh các đơn cancelled
        for j in range(cancelled_count):
            if store_id == "CH04":
                # 38/46 đơn hủy (82.6%) tại CH04 rơi vào khung 17h-19h do pos_sync_stockout
                if j < 38:
                    hr = random.choice([17, 18])
                    reason = "pos_sync_stockout"
                    delay_min = random.randint(35, 55)
                    sku, _, _, price, cost = random.choice([products_data[0], products_data[1], products_data[7]])
                else:
                    hr = random.choice([10, 11, 14, 15, 20])
                    reason = random.choice(["customer_changed_mind", "payment_failed", "delivery_delayed"])
                    delay_min = random.randint(2, 8)
                    sku, _, _, price, cost = random.choice(products_data)
            else:
                hr = random.choice([9, 11, 13, 15, 17, 18, 20])
                reason = random.choice(["customer_changed_mind", "payment_failed", "pos_sync_stockout", "delivery_delayed"])
                delay_min = random.randint(3, 15)
                sku, _, _, price, cost = random.choice(products_data)

            qty = random.choice([1, 2])
            minute = random.randint(0, 59)
            ts = f"{yesterday_str}T{hr:02d}:{minute:02d}:00+07:00"
            cname = random.choice(sample_names)
            cphone = f"09{random.randint(10000000, 99999999)}"
            cemail = f"khachhang{order_seq}@gmail.com"
            orders_rows.append((
                f"ORD-{order_seq}", store_id, sku, ts, yesterday_str, hr,
                "cancelled", qty, float(price * qty), float(cost * qty),
                reason, delay_min, 0, cname, cphone, cemail
            ))
            order_seq += 1

    # =================================================================
    # BỔ SUNG 14 ĐƠN TEST NỘI BỘ (is_test = 1) ĐÚNG KỊCH BẢN DEMO BƯỚC 3
    # =================================================================
    for t_idx in range(14):
        st = random.choice(["CH01", "CH02", "CH03", "CH04", "CH05", "CH06"])
        orders_rows.append((
            f"ORD-TEST-{t_idx+1:02d}", st, "SKU-001",
            f"{yesterday_str}T08:15:00+07:00", yesterday_str, 8,
            "cancelled", 10, 650000.0, 450000.0,
            "it_qa_test_order", 0, 1,
            "IT QA Tester", "0900000000", "qa.test@enterprise.vn"
        ))

    # =================================================================
    # BỔ SUNG CÁC BẢN GHI LỖI DỮ LIỆU BẨN ĐỂ TEST BƯỚC 3 (QUARANTINE)
    # 1. Thiếu mã sản phẩm (NULL SKU): 4 bản ghi
    # 2. Doanh thu âm (Negative Revenue): 3 bản ghi
    # 3. Trùng lặp mã hóa đơn (Duplicate ID): 3 bản ghi
    # 4. Lệch múi giờ (Timezone != +07:00): 5 bản ghi
    # =================================================================
    # 1. NULL SKU (4 bản ghi)
    for idx in range(4):
        orders_rows.append((
            f"ORD-ERR-NULL-{idx+1}", "CH04", None,
            f"{yesterday_str}T12:30:00+07:00", yesterday_str, 12,
            "completed", 1, 65000.0, 45000.0,
            "none", 2, 0, "Khách Lỗi SKU", "0912345678", "err_sku@gmail.com"
        ))

    # 2. Doanh thu âm (3 bản ghi)
    for idx in range(3):
        orders_rows.append((
            f"ORD-ERR-NEG-{idx+1}", "CH02", "SKU-003",
            f"{yesterday_str}T15:20:00+07:00", yesterday_str, 15,
            "completed", 2, -125000.0, 40000.0,
            "none", 3, 0, "Khách Lỗi Âm Tiền", "0923456789", "err_neg@gmail.com"
        ))

    # 3. Trùng lặp mã hóa đơn (Duplicate ID - lấy lại mã ORD-10005, ORD-10010, ORD-10015)
    for dup_id in ["ORD-10005", "ORD-10010", "ORD-10015"]:
        orders_rows.append((
            dup_id, "CH01", "SKU-002",
            f"{yesterday_str}T16:10:00+07:00", yesterday_str, 16,
            "completed", 1, 58000.0, 40000.0,
            "none", 2, 0, "Khách Trùng Mã", "0934567890", "err_dup@gmail.com"
        ))

    # 4. Lệch múi giờ (+00:00 UTC hoặc -05:00 thay vì +07:00): 5 bản ghi
    for idx in range(5):
        orders_rows.append((
            f"ORD-ERR-TZ-{idx+1}", "CH04", "SKU-001",
            f"{yesterday_str}T18:05:00+00:00", yesterday_str, 18,
            "cancelled", 1, 65000.0, 45000.0,
            "pos_sync_stockout", 40, 0, "Khách Lệch Múi Giờ", "0945678901", "err_tz@gmail.com"
        ))

    # =================================================================
    # BỔ SUNG DỮ LIỆU 13 NGÀY TRƯỚC ĐÓ (Để phân tích Xu hướng Tuần này vs Tuần trước & Dự báo)
    # =================================================================
    base_dt = datetime.strptime(yesterday_str, "%Y-%m-%d")
    for day_offset in range(1, 14):
        d_str = (base_dt - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        is_this_week = day_offset < 7
        for st_id, _, _ in yesterday_store_specs[:6]:
            # CH04 tuần này có doanh thu giảm nhẹ vào buổi chiều tối do lỗi tồn kho POS
            daily_orders = random.randint(140, 175)
            for _ in range(daily_orders):
                sku, _, _, price, cost = random.choice(products_data)
                qty = random.choice([1, 1, 2, 3])
                hr = random.randint(8, 21)
                cancel_prob = 0.14 if (st_id == "CH04" and is_this_week and hr in (17, 18)) else 0.05
                st_status = "cancelled" if random.random() < cancel_prob else "completed"
                reason = "pos_sync_stockout" if (st_status == "cancelled" and st_id == "CH04") else "none"
                orders_rows.append((
                    f"ORD-{order_seq}", st_id, sku,
                    f"{d_str}T{hr:02d}:30:00+07:00", d_str, hr,
                    st_status, qty, float(price * qty), float(cost * qty),
                    reason, 38 if reason == "pos_sync_stockout" else 3, 0,
                    "Khách Hàng Thường Xuyên", "0988888888", "khach@enterprise.vn"
                ))
                order_seq += 1

    cur.executemany("""
        INSERT INTO orders (
            order_id, store_id, sku_id, order_timestamp, order_date, order_hour,
            status, quantity, revenue, cost, cancel_reason, pos_sync_delay_min,
            is_test, customer_name, customer_phone, customer_email
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, orders_rows)

    # =================================================================
    # SINH DỮ LIỆU BẢNG INVENTORY_LOGS (Tồn kho thực tế vs POS & Biến ngoại cảnh)
    # =================================================================
    inv_rows = []
    hour_slots = ["08h-11h", "11h-14h", "14h-17h", "17h-19h", "19h-22h"]
    for st_id, _, _ in yesterday_store_specs[:6]:
        for slot in hour_slots:
            for sku_id, _, _, _, _ in products_data[:4]:
                if st_id == "CH04" and slot == "17h-19h":
                    # Tại CH04 khung 17h-19h: Hết tồn kho thực tế (0) nhưng POS vẫn báo còn 15-24 sp!
                    phys_stock = 0
                    pos_stock = random.randint(15, 24)
                    stockout_pct = 28.5
                    promo = 1
                    weather = "Rainy"
                    comp_idx = 0.96
                else:
                    phys_stock = random.randint(18, 60)
                    pos_stock = phys_stock + random.randint(0, 2)
                    stockout_pct = round(random.uniform(2.0, 7.5), 1)
                    promo = 1 if slot in ("17h-19h", "19h-22h") else 0
                    weather = "Sunny" if slot != "17h-19h" else "Rainy"
                    comp_idx = round(random.uniform(0.98, 1.05), 2)

                inv_rows.append((
                    st_id, sku_id, yesterday_str, slot,
                    phys_stock, pos_stock, stockout_pct, promo, weather, comp_idx
                ))

    cur.executemany("""
        INSERT INTO inventory_logs (
            store_id, sku_id, log_date, hour_slot,
            physical_stock, pos_stock, stockout_rate, promo_active,
            weather_condition, competitor_price_index
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, inv_rows)

    conn.commit()
    conn.close()

    # Xuất thêm file CSV ngày hôm qua để người dùng có thể tải lên thử nghiệm
    export_sample_csv(yesterday_str)
    return DB_PATH


def export_sample_csv(target_date: str = "2026-11-15") -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE order_date = ?", (target_date,))
    rows = cur.fetchall()
    col_names = [desc[0] for desc in cur.description]
    conn.close()

    with open(SAMPLE_CSV_PATH, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        writer.writerows(rows)

    return SAMPLE_CSV_PATH


if __name__ == "__main__":
    path = init_data_warehouse(force_rebuild=True)
    print(f"Data Warehouse initialized at: {path}")
