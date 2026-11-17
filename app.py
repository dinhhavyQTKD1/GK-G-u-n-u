# -*- coding: utf-8 -*-
"""
Vercel Python WSGI Entrypoint (`app.py`)
Exports top-level `app` (and `application`) for Vercel's Python runtime.
- Serves `index.html` at `/`
- Serves REST APIs:
  - GET  /api/status
  - POST /api/feedback
  - POST /api/approve-alert
  - POST /api/analyze
- Zero external pip dependencies (uses Python stdlib WSGI + SQLite Data Warehouse).
"""

import os
import json
import mimetypes
from datetime import datetime
from typing import Dict, Any, List, Callable

from agent_pipeline import EnterpriseDataAnalyticsAgent

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DATA_DIR = "/tmp/beardata" if os.environ.get("VERCEL") else os.path.join(ROOT_DIR, "data")
os.makedirs(RUNTIME_DATA_DIR, exist_ok=True)
APPROVAL_LOG_PATH = os.path.join(RUNTIME_DATA_DIR, "approval_audit_log.json")

_AGENT_INSTANCE = None


def get_agent() -> EnterpriseDataAnalyticsAgent:
    global _AGENT_INSTANCE
    if _AGENT_INSTANCE is None:
        _AGENT_INSTANCE = EnterpriseDataAnalyticsAgent()
    return _AGENT_INSTANCE


def _json_response(start_response: Callable, status: str, payload: Dict[str, Any]) -> List[bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
    ]
    start_response(status, headers)
    return [body]


def _read_json_body(environ: Dict[str, Any]) -> Dict[str, Any]:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length <= 0:
        return {}
    raw = environ["wsgi.input"].read(length).decode("utf-8")
    return json.loads(raw) if raw.strip() else {}


def _format_memories_for_ui(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    formatted = []
    for r in rows:
        threshold = "15.0%"
        try:
            override = json.loads(r.get("kpi_override_json") or "{}")
            if "risk_threshold_pct" in override:
                threshold = f"{override['risk_threshold_pct']}%"
            elif "risk_threshold" in override:
                threshold = f"{override['risk_threshold']}%"
        except Exception:
            pass
        formatted.append({
            "id": f"VEC-{int(r.get('memory_id', 1)):03d}",
            "time": (r.get("created_at") or "")[:16].replace("T", " "),
            "role": r.get("user_role") or "Manager_Region_North",
            "type": r.get("feedback_type") or "LIKE_ACCURATE",
            "threshold": threshold,
            "rule": r.get("user_note") or "",
        })
    return formatted


def app(environ: Dict[str, Any], start_response: Callable) -> List[bytes]:
    """Top-level WSGI entrypoint required by Vercel Python runtime."""
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    path = environ.get("PATH_INFO") or "/"

    if method == "OPTIONS":
        start_response(
            "200 OK",
            [
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "Content-Type"),
                ("Content-Length", "0"),
            ],
        )
        return [b""]

    # 1. GET /api/status
    if path == "/api/status":
        agent = get_agent()
        memories = _format_memories_for_ui(agent.get_feedback_memories())
        return _json_response(
            start_response,
            "200 OK",
            {
                "status": "online",
                "server": "BearData AI Agent (Vercel Python WSGI)",
                "port": 443 if os.environ.get("VERCEL") else 8080,
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+07:00"),
                "vector_memories": memories,
            },
        )

    # 2. POST /api/feedback
    if path == "/api/feedback" and method == "POST":
        data = _read_json_body(environ)
        agent = get_agent()
        threshold_str = str(data.get("threshold") or "15.0").replace("%", "").strip()
        try:
            threshold_val = float(threshold_str)
        except ValueError:
            threshold_val = 15.0

        agent.save_human_feedback(
            query_pattern=data.get("query_pattern") or "tỷ lệ hủy đơn",
            user_role=data.get("role") or "Manager_Region_North",
            feedback_type=data.get("type") or "LIKE_ACCURATE",
            kpi_override={"risk_threshold_pct": threshold_val},
            user_note=data.get("rule") or "",
        )
        memories = _format_memories_for_ui(agent.get_feedback_memories())
        return _json_response(
            start_response,
            "200 OK",
            {
                "ok": True,
                "saved": memories[0] if memories else None,
                "all_memories": memories,
            },
        )

    # 3. POST /api/approve-alert
    if path == "/api/approve-alert" and method == "POST":
        data = _read_json_body(environ)
        audit_record = {
            "audit_id": "AUD-" + datetime.now().strftime("%Y%m%d%H%M%S"),
            "approved": bool(data.get("approved", True)),
            "role": data.get("role") or "Manager_Region_North",
            "target_store": "CH04 - Cửa hàng #04 Cầu Giấy",
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+07:00"),
        }
        with open(APPROVAL_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(audit_record, f, ensure_ascii=False, indent=2)
        return _json_response(start_response, "200 OK", {"ok": True, "audit": audit_record})

    # 4. POST /api/analyze
    if path == "/api/analyze" and method == "POST":
        data = _read_json_body(environ)
        agent = get_agent()
        result = agent.run_pipeline(
            user_query=data.get("query") or "Kiểm tra giúp tôi top 5 cửa hàng có tỷ lệ hủy đơn cao nhất hôm qua và nguyên nhân.",
            trigger_source=data.get("trigger_source") or "Web App Portal",
            user_role=data.get("role") or "Manager_Region_North",
            simulate_retry_demo=bool(data.get("simulate_retry", True)),
            uploaded_records=data.get("uploaded_records"),
            custom_sql_test=data.get("custom_sql_test"),
            llm_provider=data.get("llm_provider") or "hybrid_local",
            api_key=data.get("api_key"),
        )
        return _json_response(start_response, "200 OK", result)

    # 5. Static file serving (index.html and assets)
    rel_path = "index.html" if path in ("/", "") else path.lstrip("/")
    safe_path = os.path.normpath(os.path.join(ROOT_DIR, rel_path))
    if safe_path.startswith(ROOT_DIR) and os.path.isfile(safe_path):
        mime_type, _ = mimetypes.guess_type(safe_path)
        if safe_path.endswith(".html"):
            mime_type = "text/html; charset=utf-8"
        elif safe_path.endswith(".csv"):
            mime_type = "text/csv; charset=utf-8"
        elif not mime_type:
            mime_type = "application/octet-stream"

        with open(safe_path, "rb") as f:
            content = f.read()
        start_response(
            "200 OK",
            [
                ("Content-Type", mime_type),
                ("Content-Length", str(len(content))),
            ],
        )
        return [content]

    not_found = f"404 Not Found: {path}".encode("utf-8")
    start_response(
        "404 Not Found",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(not_found))),
        ],
    )
    return [not_found]


# Alias for WSGI servers expecting `application`
application = app

if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    print("Serving BearData AI Agent WSGI app at http://localhost:8080")
    make_server("127.0.0.1", 8080, app).serve_forever()
