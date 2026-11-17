# -*- coding: utf-8 -*-
"""
Bước 1: Semantic Layer & Data Catalog + Intent & Context Parsing
Từ điển dữ liệu doanh nghiệp, định nghĩa KPI chuẩn và bộ bóc tách thực thể (Entity Extraction).
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# =====================================================================
# 1. SEMANTIC LAYER / DATA CATALOG (Từ điển dữ liệu doanh nghiệp)
# =====================================================================
DATA_CATALOG: Dict[str, Any] = {
    "tables": {
        "orders": {
            "description": "Bảng giao dịch đơn hàng chi tiết từ hệ thống POS & E-commerce",
            "primary_key": "order_id",
            "columns": {
                "order_id": "Mã hóa đơn duy nhất (VD: ORD-10001)",
                "store_id": "Mã cửa hàng (CH01 -> CH08)",
                "sku_id": "Mã sản phẩm SKU (SKU-001 -> SKU-010)",
                "order_timestamp": "Thời gian phát sinh đơn hàng (ISO 8601, chuẩn múi giờ +07:00)",
                "order_date": "Ngày đơn hàng (YYYY-MM-DD)",
                "order_hour": "Khung giờ phát sinh đơn (0 -> 23)",
                "status": "Trạng thái đơn: 'completed', 'cancelled', 'returned'",
                "quantity": "Số lượng sản phẩm",
                "revenue": "Doanh thu đơn hàng (VNĐ)",
                "cost": "Giá vốn hàng bán (VNĐ)",
                "cancel_reason": "Lý do hủy đơn (pos_sync_stockout, customer_changed_mind, payment_failed, delivery_delayed)",
                "pos_sync_delay_min": "Độ trễ đồng bộ tồn kho giữa kho thực tế và máy POS (phút)",
                "is_test": "Cờ đánh dấu đơn test nội bộ IT/QA (1 = Đơn test cần loại bỏ, 0 = Đơn thật)",
                "customer_name": "[PII] Họ tên khách hàng",
                "customer_phone": "[PII] Số điện thoại khách hàng",
                "customer_email": "[PII] Email khách hàng",
            },
        },
        "stores": {
            "description": "Danh mục cửa hàng và phân vùng quản lý",
            "primary_key": "store_id",
            "columns": {
                "store_id": "Mã cửa hàng (VD: CH04)",
                "store_name": "Tên cửa hàng (VD: Cửa hàng #04 - Cầu Giấy)",
                "region": "Khu vực địa lý ('North', 'South', 'Central')",
                "manager_role": "Role quản lý phụ trách (VD: Manager_Region_North)",
                "manager_name": "Tên quản lý khu vực",
            },
        },
        "inventory_logs": {
            "description": "Nhật ký cảnh báo tồn kho, biến ngoại cảnh (thời tiết, KM, giá đối thủ) theo khung giờ",
            "primary_key": "log_id",
            "columns": {
                "log_id": "Mã bản ghi log tồn kho",
                "store_id": "Mã cửa hàng",
                "sku_id": "Mã sản phẩm SKU",
                "log_date": "Ngày ghi nhận",
                "hour_slot": "Khung giờ (VD: '17h-19h')",
                "physical_stock": "Tồn kho thực tế tại quầy/kho",
                "pos_stock": "Tồn kho hiển thị trên hệ thống POS",
                "stockout_rate": "Tỷ lệ hết hàng (%)",
                "promo_active": "Có chương trình khuyến mãi (1 = Có, 0 = Không)",
                "weather_condition": "Thời tiết ('Sunny', 'Rainy', 'Storm')",
                "competitor_price_index": "Chỉ số giá đối thủ (<1.0 là đối thủ rẻ hơn)",
            },
        },
        "products": {
            "description": "Danh mục sản phẩm (SKU) và nhóm ngành hàng",
            "primary_key": "sku_id",
            "columns": {
                "sku_id": "Mã SKU",
                "product_name": "Tên sản phẩm",
                "category": "Nhóm hàng ('Beverage', 'Fresh Food', 'FMCG', 'Personal Care')",
                "unit_price": "Giá bán niêm yết (VNĐ)",
            },
        },
        "data_quarantine": {
            "description": "Bảng cách ly dữ liệu bẩn/lỗi phát hiện ở Bước 3 (Data Profiling)",
            "primary_key": "quarantine_id",
            "columns": {
                "quarantine_id": "ID bản ghi cách ly",
                "batch_id": "Mã phiên chạy",
                "order_id": "Mã hóa đơn lỗi",
                "anomaly_type": "Loại lỗi (NULL_SKU, NEGATIVE_REVENUE, DUPLICATE_ID, TIMEZONE_DRIFT, TEST_ORDER)",
                "anomaly_detail": "Chi tiết lỗi phát hiện",
                "raw_payload": "Dữ liệu gốc dạng JSON",
                "quarantined_at": "Thời điểm cách ly",
            },
        },
    },
    "kpi_definitions": {
        "cancel_rate": {
            "name": "Tỷ lệ hủy đơn (Cancellation Rate)",
            "formula": "COUNT(CASE WHEN status = 'cancelled' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)",
            "standard_filter": "is_test = 0",
            "unit": "%",
            "risk_threshold": 15.0,
            "description": "Tỷ lệ đơn bị hủy trên tổng số đơn hợp lệ (đã loại bỏ đơn test nội bộ và dữ liệu bẩn).",
        },
        "net_revenue": {
            "name": "Doanh thu thuần (Net Revenue)",
            "formula": "SUM(CASE WHEN status = 'completed' THEN revenue ELSE 0 END)",
            "standard_filter": "is_test = 0 AND revenue > 0",
            "unit": "VNĐ",
            "risk_threshold": -10.0,  # Giảm > 10% WoW
            "description": "Tổng doanh thu từ các đơn hàng hoàn thành hợp lệ.",
        },
        "gross_margin": {
            "name": "Biên lợi nhuận gộp (Gross Margin)",
            "formula": "SUM(revenue - cost) * 100.0 / NULLIF(SUM(revenue), 0)",
            "standard_filter": "is_test = 0 AND status = 'completed'",
            "unit": "%",
            "risk_threshold": 20.0,  # Thấp hơn 20%
            "description": "Tỷ lệ lợi nhuận gộp trên doanh thu thuần.",
        },
        "stockout_rate": {
            "name": "Tỷ lệ hết hàng (Out-of-Stock Rate)",
            "formula": "AVG(stockout_rate)",
            "standard_filter": "1=1",
            "unit": "%",
            "risk_threshold": 15.0,
            "description": "Tỷ lệ mã hàng bị hết tồn kho thực tế trong ca bán hàng.",
        },
    },
    "rbac_policies": {
        "Manager_Region_North": {
            "allowed_regions": ["North"],
            "mask_pii": True,
            "allowed_tables": ["orders", "stores", "inventory_logs", "products", "data_quarantine"],
            "description": "Quản lý Khu vực Miền Bắc - Chỉ xem dữ liệu các cửa hàng miền Bắc, ẩn thông tin nhạy cảm KH (PII).",
        },
        "Manager_Region_South": {
            "allowed_regions": ["South"],
            "mask_pii": True,
            "allowed_tables": ["orders", "stores", "inventory_logs", "products", "data_quarantine"],
            "description": "Quản lý Khu vực Miền Nam - Chỉ xem dữ liệu các cửa hàng miền Nam, ẩn thông tin nhạy cảm KH (PII).",
        },
        "CEO_Executive": {
            "allowed_regions": ["North", "South", "Central"],
            "mask_pii": True,
            "allowed_tables": ["orders", "stores", "inventory_logs", "products", "data_quarantine"],
            "description": "Ban Giám Đốc - Xem toàn quốc, vẫn tự động che giấu PII khách hàng theo chuẩn bảo mật.",
        },
    },
}


# =====================================================================
# 2. ENTITY EXTRACTION & INTENT PARSER (Bước 1)
# =====================================================================
def parse_intent_and_context(
    user_query: str,
    trigger_source: str = "Lark Suite Chat",
    user_role: str = "Manager_Region_North",
    reference_date: Optional[str] = None,
    custom_kpi_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Phân tách thực thể (thời gian, khu vực, nhóm hàng, chỉ số KPI, top N)
    và ánh xạ vào Semantic Layer / Data Catalog.
    """
    q_lower = user_query.lower()

    # 1. Xác định Intent chính
    if any(k in q_lower for k in ["hủy", "cancel", "tỷ lệ hủy", "đơn hủy"]):
        intent = "cancellation_root_cause"
        primary_kpi = "cancel_rate"
    elif any(k in q_lower for k in ["doanh thu", "revenue", "bán hàng", "tuần này", "tăng trưởng"]):
        intent = "revenue_performance_analysis"
        primary_kpi = "net_revenue"
    elif any(k in q_lower for k in ["tồn kho", "hết hàng", "stockout", "inventory"]):
        intent = "inventory_stockout_analysis"
        primary_kpi = "stockout_rate"
    elif any(k in q_lower for k in ["lợi nhuận", "margin", "biên lợi nhuận", "dự báo", "forecast"]):
        intent = "margin_and_forecast_analysis"
        primary_kpi = "gross_margin"
    else:
        # Mặc định chạy kịch bản tổng hợp hoặc hủy đơn nếu câu hỏi chung
        intent = "cancellation_root_cause"
        primary_kpi = "cancel_rate"

    # 2. Bóc tách thực thể Thời gian (Time Entity)
    if "hôm qua" in q_lower or "yesterday" in q_lower:
        time_entity = "yesterday"
        time_label = "Hôm qua (Yesterday)"
    elif "tuần này" in q_lower or "tuần trước" in q_lower or "week" in q_lower:
        time_entity = "this_week_vs_last_week"
        time_label = "Tuần này vs Tuần trước (WoW)"
    elif "tháng" in q_lower or "month" in q_lower:
        time_entity = "this_month"
        time_label = "Tháng hiện tại (MTD)"
    else:
        time_entity = "yesterday"
        time_label = "Hôm qua (Mặc định)"

    # 3. Bóc tách Top N
    top_match = re.search(r"top\s*(\d+)", q_lower)
    top_n = int(top_match.group(1)) if top_match else 5

    # 4. Bóc tách Khu vực (Region Entity) kết hợp với RBAC của User Role
    rbac_info = DATA_CATALOG["rbac_policies"].get(
        user_role, DATA_CATALOG["rbac_policies"]["Manager_Region_North"]
    )
    allowed_regions = rbac_info["allowed_regions"]

    if "miền bắc" in q_lower or "north" in q_lower:
        requested_regions = ["North"]
    elif "miền nam" in q_lower or "south" in q_lower:
        requested_regions = ["South"]
    else:
        requested_regions = allowed_regions

    # Giao thoa với quyền RBAC
    effective_regions = [r for r in requested_regions if r in allowed_regions]
    if not effective_regions:
        effective_regions = allowed_regions

    # 5. Bóc tách Nhóm hàng (Category Entity)
    category_entity = "All Categories"
    for cat, vn_keywords in [
        ("Beverage", ["đồ uống", "nước", "beverage"]),
        ("Fresh Food", ["thực phẩm tươi", "fresh", "đồ tươi"]),
        ("FMCG", ["tiêu dùng nhanh", "fmcg", "bánh kẹo"]),
        ("Personal Care", ["chăm sóc cá nhân", "personal care", "mỹ phẩm"]),
    ]:
        if any(w in q_lower for w in vn_keywords):
            category_entity = cat
            break

    # 6. Đối chiếu Semantic Layer
    kpi_meta = dict(DATA_CATALOG["kpi_definitions"][primary_kpi])
    if custom_kpi_overrides and primary_kpi in custom_kpi_overrides:
        kpi_meta.update(custom_kpi_overrides[primary_kpi])

    mapped_tables = ["orders", "stores", "inventory_logs", "products"]
    mapped_columns = {
        "orders": ["order_id", "store_id", "sku_id", "order_timestamp", "status", "revenue", "cancel_reason", "pos_sync_delay_min", "is_test"],
        "stores": ["store_id", "store_name", "region"],
        "inventory_logs": ["store_id", "sku_id", "hour_slot", "physical_stock", "pos_stock", "stockout_rate", "promo_active", "weather_condition"],
    }

    return {
        "trigger_source": trigger_source,
        "raw_query": user_query,
        "user_role": user_role,
        "intent": intent,
        "entities": {
            "time_range": time_entity,
            "time_label": time_label,
            "regions": effective_regions,
            "category": category_entity,
            "top_n": top_n,
            "primary_kpi": primary_kpi,
            "ask_root_cause": any(w in q_lower for w in ["nguyên nhân", "tại sao", "why", "root cause", "chi tiết", "phân tích"]),
        },
        "semantic_mapping": {
            "kpi_metadata": kpi_meta,
            "mapped_tables": mapped_tables,
            "mapped_columns": mapped_columns,
            "rbac_policy": rbac_info,
            "reference_date": reference_date,
        },
    }
