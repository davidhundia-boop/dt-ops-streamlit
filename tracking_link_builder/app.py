"""
Streamlit UI for the tracking link builder (wraps builder.build_link).
"""
import os
import sys

import streamlit as st

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from builder import DEFAULT_CLICK_ID, build_link

st.set_page_config(page_title="Tracking Link Builder", page_icon="🔗", layout="centered")
st.title("Tracking Link Builder")
st.caption("Inject test click ID and device ID into a raw tracking URL.")

raw = st.text_area("Raw tracking link", height=100, placeholder="https://...")
device_id = st.text_input("Device ID (UUID or SHA-1 as required by link)")
click_id = st.text_input("Click ID", value=DEFAULT_CLICK_ID)

if st.button("Build link", type="primary"):
    if not raw.strip() or not device_id.strip():
        st.error("Please provide both the raw link and device ID.")
    else:
        try:
            result = build_link(raw.strip(), device_id.strip(), click_id_val=click_id.strip() or DEFAULT_CLICK_ID)
            st.success(f"**{result['integration_type']}** · PID: `{result['pid'] or '(none)'}`")
            for m in result["messages"]:
                st.info(m)
            if result["changes"]:
                st.write("**Changes**")
                for c in result["changes"]:
                    st.write(f"- `{c['param']}` → `{c['new']}` ({c['desc']})")
            st.code(result["output_url"], language=None)
        except ValueError as e:
            st.error(str(e))
