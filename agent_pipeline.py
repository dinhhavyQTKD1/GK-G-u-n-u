# -*- coding: utf-8 -*-
"""
Orchestrator điều phối toàn bộ quy trình 6 bước của Enterprise Data Analytics AI Agent:
1. Intent & Context Parsing (Bóc tách thực thể + Ánh xạ Semantic Layer / Data Catalog)
2. Planning & Secure Retrieval (Agent Planner + Text-to-SQL + AST Guardrails + RBAC + PII Masking + Auto-Retry 3x)
3. Data Profiling & Quarantine (Làm sạch trong Python Sandbox: lọc 14 đơn test, NULL SKU, âm tiền, trùng mã, lệch múi giờ + xuất data_quarantine)
4. Deep Analytics & Root-Cause (Phân tích đóng góp Drill-down, tương quan biến ngoại cảnh & dự báo ngắn hạn)
5. Visualization & Narrative Generation (Biểu đồ Bar, Heatmap, Waterfall, Line Forecast + Executive Summary)
6. Delivery & Human-in-the-loop (Đa kênh, Proactive Alert + Approval Card + Vector DB Feedback Loop)
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List

from data_generator import init_data_warehouse, DB_PATH
from semantic_catalog import parse_intent_and_context, DATA_CATALOG
from planner_guardrails import (
    build_execution_plan,
    execute_secure_query_with_retry,
    validate_sql_ast_and_rbac,
)
from data_profiler_quarantine import run_sandbox_profiling_and_quarantine
from deep_analytics_engine import (
    run_deep_analytics,
    generate_executive_summary,
    evaluate_proactive_alerts,
)


class EnterpriseDataAnalyticsAgent:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or init_data_warehouse(force_rebuild=False)

    def run_pipeline(
        self,
        user_query: str,
        trigger_source: str = "Lark Suite Chat",
        user_role: str = "Manager_Region_North",
        simulate_retry_demo: bool = True,
        uploaded_records: Optional[List[Dict[str, Any]]] = None,
        custom_sql_test: Optional[str] = None,
        llm_provider: str = "hybrid_local",
        api_key: Optional[str] = None,
        custom_kpi_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Chạy khép kín 6 bước của AI Agent và trả về kết quả chi tiết từng bước.
        """
        # =================================================================
        # BƯỚC 1: TIẾP NHẬN & HIỂU Ý ĐỊNH (Intent & Context Parsing)
        # =================================================================
        step1_context = parse_intent_and_context(
            user_query=user_query,
            trigger_source=trigger_source,
            user_role=user_role,
            reference_date="2026-11-15",
            custom_kpi_overrides=custom_kpi_overrides,
        )

        # =================================================================
        # BƯỚC 2: LẬP KẾ HOẠCH & TRUY VẤN AN TOÀN (Planning & Secure Retrieval)
        # =================================================================
        execution_plan = build_execution_plan(step1_context)
        retrieval_result = execute_secure_query_with_retry(
            db_path=self.db_path,
            parsed_context=step1_context,
            simulate_retry_demo=simulate_retry_demo,
            custom_sql_Attempt=custom_sql_test,
        )

        # Nếu người dùng upload file Excel/CSV trực tiếp, ưu tiên dùng dữ liệu upload cho Bước 3
        raw_orders = uploaded_records if uploaded_records is not None else retrieval_result["orders_data"]

        if not retrieval_result["success"] and uploaded_records is None:
            return {
                "status": "BLOCKED_OR_FAILED",
                "step1_intent_context": step1_context,
                "step2_planning_retrieval": {
                    "plan": execution_plan,
                    "retrieval": retrieval_result,
                },
            }

        # =================================================================
        # BƯỚC 3: LÀM SẠCH & KIỂM ĐỊNH CHẤT LƯỢNG DỮ LIỆU (Data Profiling & Quarantine)
        # =================================================================
        step3_profiling = run_sandbox_profiling_and_quarantine(
            raw_records=raw_orders,
            db_path=self.db_path,
        )

        # =================================================================
        # BƯỚC 4: PHÂN TÍCH CHUYÊN SÂU & NGUYÊN NHÂN GỐC RỄ (Deep Analytics & Root-Cause)
        # =================================================================
        step4_analytics = run_deep_analytics(
            clean_orders=step3_profiling["clean_records"],
            inventory_logs=retrieval_result["inventory_data"],
            historical_orders=retrieval_result["historical_data"],
            parsed_context=step1_context,
        )

        # =================================================================
        # BƯỚC 5: TRỰC QUAN HÓA & TỔNG HỢP INSIGHT (Visualization & Narrative Generation)
        # =================================================================
        step5_narrative = generate_executive_summary(
            analytics_result=step4_analytics,
            profiling_result=step3_profiling,
            parsed_context=step1_context,
            llm_provider=llm_provider,
            api_key=api_key,
        )

        # =================================================================
        # BƯỚC 6: PHẢN HỒI TƯƠNG TÁC & CẢNH BÁO CHỦ ĐỘNG (Delivery & Human-in-the-loop)
        # =================================================================
        proactive_alerts = evaluate_proactive_alerts(
            analytics_result=step4_analytics,
            parsed_context=step1_context,
        )

        feedback_memories = self.get_feedback_memories()

        return {
            "status": "COMPLETED",
            "step1_intent_context": step1_context,
            "step2_planning_retrieval": {
                "plan": execution_plan,
                "guardrail_result": retrieval_result["guardrail_result"],
                "retry_logs": retrieval_result["retry_logs"],
                "sample_masked_rows": raw_orders[:5],
            },
            "step3_profiling_quarantine": {
                k: v for k, v in step3_profiling.items() if k != "clean_records"
            },
            "step4_deep_analytics": step4_analytics,
            "step5_visualization_narrative": step5_narrative,
            "step6_delivery_hitl": {
                "proactive_alerts": proactive_alerts,
                "feedback_memories": feedback_memories,
            },
        }

    def save_human_feedback(
        self,
        query_pattern: str,
        user_role: str,
        feedback_type: str,
        kpi_override: Dict[str, Any],
        user_note: str,
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vector_feedback_memory (
                query_pattern, user_role, feedback_type, kpi_override_json, user_note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                query_pattern,
                user_role,
                feedback_type,
                json.dumps(kpi_override, ensure_ascii=False),
                user_note,
                datetime.now().strftime("%Y-%m-%dT%H:%M:%S+07:00"),
            ),
        )
        conn.commit()
        conn.close()

    def get_feedback_memories(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM vector_feedback_memory ORDER BY memory_id DESC LIMIT 10")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows


if __name__ == "__main__":
    agent = EnterpriseDataAnalyticsAgent()
    demo_query = "Kiểm tra giúp tôi top 5 cửa hàng có tỷ lệ hủy đơn cao nhất hôm qua và nguyên nhân."
    res = agent.run_pipeline(demo_query, simulate_retry_demo=True)
    print("=== DEMO PIPELINE RESULT ===")
    print("Status:", res["status"])
    print("Quarantined rows:", res["step3_profiling_quarantine"]["total_quarantined_rows"])
    print("Headline:", res["step5_visualization_narrative"]["headline"])
