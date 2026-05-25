import sqlite3
import time
import pandas as pd
import streamlit as st
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "approvals.db"

st.set_page_config(page_title="Request Approval Monitor", layout="wide")
st.title("Request Approval Monitor")
st.caption("Approve or reject public ngrok requests before the server responds")

if "live" not in st.session_state:
    st.session_state.live = True

if "refresh_sec" not in st.session_state:
    st.session_state.refresh_sec = 1

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_pending():
    conn = get_db()
    rows = conn.execute("""
        SELECT id, method, path, client_ip, created_at, filename, file_size
        FROM requests
        WHERE status='pending'
        ORDER BY created_at ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def load_recent(limit=30):
    conn = get_db()
    rows = conn.execute("""
        SELECT id, method, path, status, action, client_ip, created_at, decided_at, filename, file_size
        FROM requests
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def decide(req_id, action):
    conn = get_db()
    conn.execute("""
        UPDATE requests
        SET status='decided', action=?, decided_at=?
        WHERE id=? AND status='pending'
    """, (action, time.time(), req_id))
    conn.commit()
    conn.close()

with st.sidebar:
    st.header("Monitor")
    st.checkbox("Live refresh", key="live")
    st.slider("Refresh seconds", 1, 10, key="refresh_sec")
    st.write(f"Database: `{DB_PATH}`")

run_every = st.session_state.refresh_sec if st.session_state.live else None

@st.fragment(run_every=run_every)
def live_panel():
    pending = load_pending()
    recent = load_recent()

    c1, c2 = st.columns([1.2, 1.8])

    with c1:
        st.subheader("Pending requests")
        if not pending:
            st.info("No pending requests.")
        else:
            pending_df = pd.DataFrame(pending)
            if not pending_df.empty:
                if "created_at" in pending_df.columns:
                    pending_df["created_at"] = pd.to_datetime(pending_df["created_at"], unit="s")
                st.dataframe(pending_df, use_container_width=True, hide_index=True)

            ids = [row["id"] for row in pending]
            selected_id = st.selectbox("Select pending request", ids, key="pending_select")

            selected = next((row for row in pending if row["id"] == selected_id), None)
            if selected:
                st.markdown(f"**Method:** {selected['method']}")
                st.markdown(f"**Path:** {selected['path']}")
                st.markdown(f"**Client IP:** {selected['client_ip']}")
                st.markdown(f"**Filename:** {selected.get('filename') or '-'}")
                st.markdown(f"**Size:** {selected.get('file_size') or '-'}")

                a, b = st.columns(2)
                with a:
                    if st.button("Allow", use_container_width=True, key=f"allow_{selected_id}"):
                        decide(selected_id, "allow")
                        st.rerun()
                with b:
                    if st.button("Reject", use_container_width=True, key=f"reject_{selected_id}"):
                        decide(selected_id, "reject")
                        st.rerun()

    with c2:
        st.subheader("Recent requests")
        if not recent:
            st.info("No request history yet.")
        else:
            recent_df = pd.DataFrame(recent)
            if "created_at" in recent_df.columns:
                recent_df["created_at"] = pd.to_datetime(recent_df["created_at"], unit="s")
            if "decided_at" in recent_df.columns:
                recent_df["decided_at"] = pd.to_datetime(recent_df["decided_at"], unit="s", errors="coerce")
            st.dataframe(recent_df, use_container_width=True, hide_index=True)

live_panel()
