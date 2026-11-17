# -*- coding: utf-8 -*-
"""
Giao diện Web App tương tác (Streamlit UI) cho Enterprise Data Analytics AI Agent (6 Bước).
Chạy bằng lệnh:
    streamlit run app.py
Hoặc mở trực tiếp file `index.html` trên trình duyệt (chạy độc lập không cần cài đặt).
"""

import io
import csv
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from agent_pipeline import EnterpriseDataAnalyticsAgent
from semantic_catalog import DATA_CATALOG

st.set_page_config(
    page_title="Enterprise Data Analytics AI Agent - 6-Step Pipeline",
    page_icon="📊",
    layout="wide",
)

# Khởi tạo Agent trong Session State
if "agent" not in st.session_state:
    st.session_state.agent = EnterpriseDataAnalyticsAgent()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "last_result" not in st.session_state:
    # Chạy sẵn kịch bản Demo mặc định khi mở ứng dụng
    st.session_state.last_result = st.session_state.agent.run_pipeline(
        user_query="Kiểm tra giúp tôi top 5 cửa hàng có tỷ lệ hủy đơn cao nhất hôm qua và nguyên nhân.",
        trigger_source="Lark Suite Chat",
        user_role="Manager_Region_North",
        simulate_retry_demo=True,
    )

# =====================================================================
# SIDEBAR: CẤU HÌNH TRIGGER, RBAC, HYBRID LLM & UPLOAD FILE
# =====================================================================
with st.sidebar:
    st.title("⚙️ Cấu hình AI Agent")
    st.caption("Quy trình 6 bước phân tích dữ liệu tự động & an toàn")

    trigger_source = st.selectbox(
        "1. Nguồn kích hoạt (Trigger Source)",
        [
            "Lark Suite Chat (Nội bộ)",
            "Slack Bot Channel",
            "Web App Portal",
            "Cronjob Hằng Đêm (00:30 AM)",
            "Lark Base / Google Sheets Sync",
        ],
    )

    user_role = st.selectbox(
        "2. Quyền hạn người hỏi (RBAC Role)",
        ["Manager_Region_North", "Manager_Region_South", "CEO_Executive"],
        help="Giới hạn phạm vi khu vực dữ liệu và tự động ẩn thông tin nhạy cảm (PII Masking).",
    )

    simulate_retry = st.checkbox(
        "Mô phỏng Auto-Retry SQL (3 lần)",
        value=True,
        help="Minh họa Bước 2: Agent tự phát hiện lỗi cột SQL / dữ liệu rỗng và viết lại câu truy vấn.",
    )

    st.divider()
    st.subheader("🧠 Chế độ Hybrid LLM")
    llm_mode = st.radio(
        "Chọn Engine:",
        ["Chạy ngay (Built-in Statistical Engine)", "Kết nối Gemini API", "Kết nối OpenAI API"],
    )
    api_key = ""
    if llm_mode != "Chạy ngay (Built-in Statistical Engine)":
        api_key = st.text_input("Nhập API Key:", type="password")

    st.divider()
    st.subheader("📂 Upload Excel / CSV (Tùy chọn)")
    uploaded_file = st.file_uploader("Tải lên file .xlsx hoặc .csv", type=["csv", "xlsx"])
    uploaded_records = None
    if uploaded_file is not None:
        if uploaded_file.name.endswith(".csv"):
            df_up = pd.read_csv(uploaded_file)
        else:
            df_up = pd.read_excel(uploaded_file)
        uploaded_records = df_up.to_dict(orient="records")
        st.success(f"Đã nạp {len(uploaded_records)} dòng từ `{uploaded_file.name}`!")

    st.divider()
    st.subheader("🛡️ Kiểm thử Bảo mật AST Guardrail")
    custom_sql_test = st.text_area(
        "Thử tiêm lệnh SQL nguy hiểm (INSERT/DELETE/DROP):",
        placeholder="VD: DROP TABLE orders; hoặc DELETE FROM orders WHERE is_test = 1;",
    )
    if st.button("Chạy thử Guardrail"):
        st.session_state.last_result = st.session_state.agent.run_pipeline(
            user_query="Kiểm tra bảo mật SQL",
            trigger_source=trigger_source,
            user_role=user_role,
            custom_sql_test=custom_sql_test,
        )

# =====================================================================
# MAIN HEADER & KHUNG CHAT ĐẶT CÂU HỎI
# =====================================================================
st.title("🤖 Enterprise Data Analytics AI Agent")
st.markdown(
    "**Kiến trúc 6 bước:** `1. Intent & Semantic Catalog` → `2. Planner & SQL Guardrails` → "
    "`3. Sandbox Profiling & Quarantine` → `4. Deep Analytics & Root-Cause` → "
    "`5. Visualization & Executive Summary` → `6. Proactive Alert & Feedback Loop`"
)

col_q1, col_q2 = st.columns([4, 1])
with col_q1:
    user_query = st.text_input(
        "💬 Nhập câu hỏi phân tích dữ liệu (hoặc chọn kịch bản mẫu):",
        value="Kiểm tra giúp tôi top 5 cửa hàng có tỷ lệ hủy đơn cao nhất hôm qua và nguyên nhân.",
    )
with col_q2:
    st.write("")
    st.write("")
    run_btn = st.button("🚀 Chạy AI Agent", type="primary", use_container_width=True)

if run_btn:
    st.session_state.last_result = st.session_state.agent.run_pipeline(
        user_query=user_query,
        trigger_source=trigger_source,
        user_role=user_role,
        simulate_retry_demo=simulate_retry,
        uploaded_records=uploaded_records,
        llm_provider="gemini" if "Gemini" in llm_mode else "hybrid_local",
        api_key=api_key,
    )

res = st.session_state.last_result

if res["status"] != "COMPLETED":
    st.error("🚨 Truy vấn đã bị chặn bởi Lớp bảo vệ AST Guardrail & RBAC!")
    st.json(res["step2_planning_retrieval"]["retrieval"])
    st.stop()

# =====================================================================
# HIỂN THỊ CHI TIẾT 6 BƯỚC XỬ LÝ
# =====================================================================
tabs = st.tabs([
    "📌 Tổng quan & Biểu đồ (Bước 5 & 6)",
    "1️⃣ Bước 1: Intent & Data Catalog",
    "2️⃣ Bước 2: Planner & SQL Guardrails",
    "3️⃣ Bước 3: Profiling & Quarantine",
    "4️⃣ Bước 4: Deep Analytics & Dự báo",
    "6️⃣ Bước 6: Proactive Alert & Vector Memory",
])

# --- TAB 0: TỔNG QUAN & BIỂU ĐỒ ---
with tabs[0]:
    s3 = res["step3_profiling_quarantine"]
    s4 = res["step4_deep_analytics"]
    s5 = res["step5_visualization_narrative"]
    s6 = res["step6_delivery_hitl"]
    worst = s4["worst_store"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Cửa hàng rủi ro cao nhất",
        worst.get("store_name", "CH04"),
        f"Tỷ lệ hủy: {worst.get('cancel_rate', 18.4)}% (Gấp {s4['worst_vs_avg_multiplier']}x TB)",
        delta_color="inverse",
    )
    m2.metric(
        "Tỷ lệ hủy khung 17h–19h (CH04)",
        f"{worst.get('pct_cancelled_17_19', 82.6)}%",
        "Do lệch tồn kho thực tế vs POS",
        delta_color="inverse",
    )
    m3.metric(
        "Dữ liệu bẩn đã cách ly (Quarantine)",
        f"{s3['total_quarantined_rows']} bản ghi",
        f"Gồm {s3['anomaly_breakdown']['TEST_ORDER']} đơn test nội bộ",
    )
    m4.metric(
        "Chất lượng dữ liệu (Data Quality)",
        f"{s3['data_quality_score']}%",
        f"{s3['total_clean_rows']}/{s3['total_raw_rows']} đơn hợp lệ",
    )

    st.info(f"🎯 **{s5['headline']}**")

    st.subheader("📝 Tóm tắt điều hành (Executive Summary)")
    for b in s5["bullets"]:
        st.markdown(f"- **{b['tag']}:** {b['text']}")

    if s5.get("llm_live_response"):
        st.success(f"**[Phản hồi bổ sung từ Live LLM]:**\n\n{s5['llm_live_response']}")

    c_left, c_right = st.columns(2)
    with c_left:
        df_top = pd.DataFrame(s4["top_stores_ranking"])
        fig_bar = px.bar(
            df_top,
            x="store_name",
            y="cancel_rate",
            color="cancel_rate",
            color_continuous_scale="Reds",
            text="cancel_rate",
            title="Top 5 Cửa hàng có Tỷ lệ hủy đơn cao nhất hôm qua (%)",
            labels={"store_name": "Cửa hàng", "cancel_rate": "Tỷ lệ hủy (%)"},
        )
        fig_bar.add_hline(
            y=s4["regional_avg_cancel_rate"],
            line_dash="dash",
            line_color="green",
            annotation_text=f"Trung bình vùng: {s4['regional_avg_cancel_rate']}%",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with c_right:
        hm = s4["heatmap"]
        fig_hm = go.Figure(
            data=go.Heatmap(
                z=hm["matrix"],
                x=hm["hour_slots"],
                y=hm["stores"],
                colorscale="YlOrRd",
                text=hm["matrix"],
                texttemplate="%{text}%",
            )
        )
        fig_hm.update_layout(title="Heatmap Tỷ lệ hủy đơn (%) theo Cửa hàng & Khung giờ")
        st.plotly_chart(fig_hm, use_container_width=True)

# --- TAB 1: BƯỚC 1 ---
with tabs[1]:
    st.subheader("Bước 1: Tiếp nhận & Hiểu ý định (Intent & Context Parsing)")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Thực thể bóc tách được (Entity Extraction):**")
        st.json(res["step1_intent_context"]["entities"])
    with col2:
        st.markdown("**Ánh xạ Semantic Layer & Chính sách RBAC:**")
        st.json(res["step1_intent_context"]["semantic_mapping"])

# --- TAB 2: BƯỚC 2 ---
with tabs[2]:
    st.subheader("Bước 2: Lập kế hoạch & Truy vấn an toàn (Planning, Guardrails & Auto-Retry)")
    st.markdown("#### 1. Kế hoạch chia nhỏ bài toán (Agent Planner):")
    st.table(pd.DataFrame(res["step2_planning_retrieval"]["plan"]))

    st.markdown("#### 2. Nhật ký Vòng lặp tự sửa lỗi SQL (Auto-Retry Loop - Tối đa 3 lần):")
    for log in res["step2_planning_retrieval"]["retry_logs"]:
        status_icon = "✅" if log["status"] == "SUCCESS" else "⚠️"
        with st.expander(f"{status_icon} Lần thử #{log['attempt']} - Trạng thái: {log['status']}", expanded=True):
            st.code(log["sql"], language="sql")
            if log.get("error"):
                st.warning(log["error"])
            else:
                st.success(f"Truy vấn thành công {log.get('row_count')} bản ghi và đã che giấu PII (PII Masking)!")

    st.markdown("#### 3. Mẫu dữ liệu sau khi áp dụng PII Masking (Che giấu SĐT, Email, Họ tên KH):")
    st.dataframe(pd.DataFrame(res["step2_planning_retrieval"]["sample_masked_rows"]))

# --- TAB 3: BƯỚC 3 ---
with tabs[3]:
    st.subheader("Bước 3: Làm sạch & Kiểm định chất lượng dữ liệu (Python Sandbox & Quarantine)")
    s3 = res["step3_profiling_quarantine"]
    st.json(s3["anomaly_breakdown"])
    df_q = pd.DataFrame(s3["quarantine_records"])
    st.dataframe(df_q, use_container_width=True)
    csv_bytes = df_q.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Tải file cách ly data_quarantine.csv cho Kỹ sư dữ liệu",
        data=csv_bytes,
        file_name="data_quarantine.csv",
        mime="text/csv",
    )

# --- TAB 4: BƯỚC 4 ---
with tabs[4]:
    st.subheader("Bước 4: Phân tích đóng góp (Contribution), Tương quan & Dự báo ngắn hạn")
    s4 = res["step4_deep_analytics"]
    st.markdown("#### Cảnh báo lệch tồn kho thực tế vs Hệ thống POS:")
    st.dataframe(pd.DataFrame(s4["root_cause_breakdown"]["pos_discrepancy_alerts"]))

    cf = s4["correlation_and_forecast"]
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=cf["historical_dates"], y=cf["historical_revenue_m_vnd"],
        mode="lines+markers", name="Doanh thu lịch sử (Triệu VNĐ)"
    ))
    fig_line.add_trace(go.Scatter(
        x=cf["forecast_dates"], y=cf["forecast_baseline_m_vnd"],
        mode="lines+markers", line=dict(dash="dash"), name="Dự báo cơ sở (Chưa fix POS)"
    ))
    fig_line.add_trace(go.Scatter(
        x=cf["forecast_dates"], y=cf["forecast_after_fix_m_vnd"],
        mode="lines+markers", name="Dự báo sau khi đồng bộ Real-time POS (+8.5%)"
    ))
    fig_line.update_layout(title="Mô hình Dự báo Doanh thu 7 ngày tới (Triệu VNĐ)")
    st.plotly_chart(fig_line, use_container_width=True)

# --- TAB 5: BƯỚC 6 ---
with tabs[5]:
    st.subheader("Bước 6: Cảnh báo chủ động (Proactive Alert) & Học hỏi phản hồi (Vector DB)")
    for alert in res["step6_delivery_hitl"]["proactive_alerts"]:
        st.error(f"🚨 **[PROACTIVE ALERT - {alert['severity']}]** {alert['metric_name']}: {alert['current_value']} (Ngưỡng: {alert['threshold_value']})")
        st.markdown("**Thẻ phê duyệt hành động (Approval Card):**")
        for act in alert["proposed_actions"]:
            st.markdown(f"- [x] {act}")
        if st.button("✅ Phê duyệt & Thực thi tự động (Approve Card)"):
            st.success("Đã gửi lệnh kích hoạt đồng bộ Real-time POS và phiếu điều chuyển kho tới Quản lý Cửa hàng #04!")

    st.divider()
    st.markdown("#### 🧠 Ghi nhận Phản hồi vào Bộ nhớ dài hạn (Vector DB Feedback Loop)")
    fb_note = st.text_input("Hiệu chỉnh định nghĩa KPI hoặc ghi chú cho Agent:", value="Loại bỏ đơn test nội bộ và cảnh báo khi tỷ lệ hủy > 15%")
    if st.button("💾 Lưu vào Vector DB"):
        st.session_state.agent.save_human_feedback(
            query_pattern=user_query,
            user_role=user_role,
            feedback_type="USER_APPROVED_RULE",
            kpi_override={"risk_threshold": 15.0, "exclude_test": True},
            user_note=fb_note,
        )
        st.success("Đã lưu phản hồi vào bộ nhớ dài hạn!")
    st.dataframe(pd.DataFrame(st.session_state.agent.get_feedback_memories()))
