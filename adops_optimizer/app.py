"""
Campaign Optimizer — Streamlit app.
Upload files, set KPI goals and weighting, configure optimization settings, run pipeline,
and download the color-coded Excel report or CSV.

Supports two modes:
  - Performance Optimization: KPI/segment-based bid adjustments (requires both files)
  - Scale Optimization: FillRate-based bid increases (internal file only)
"""

import os
import sys
import tempfile

# Ensure app directory is on path when run from repo root (e.g. Streamlit Community Cloud)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import streamlit as st
from optimizer import run_optimization, run_scale_optimization, xlsx_to_csv, col_letter_to_idx, col_name_or_letter_to_idx

st.set_page_config(
    page_title="Campaign Optimizer",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom styling to align with reference (dark header area optional; keeping clean light/dark compatible)
st.markdown("""
<style>
    .main-header { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem; }
    .main-caption { color: #666; margin-bottom: 1.5rem; }
    .section-head { font-weight: 600; margin: 1.25rem 0 0.75rem 0; }
    .stSlider [data-baseweb="slider"] { margin-top: 0.5rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🎯 Campaign Optimizer</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="main-caption">Upload your files, enter your goals, and get instant bid recommendations.</p>',
    unsafe_allow_html=True,
)
st.divider()

# ---------------------------------------------------------------------------
# 0 — Optimization Mode
# ---------------------------------------------------------------------------
opt_mode = st.radio(
    "Optimization Mode",
    ["Performance Optimization", "Scale Optimization"],
    horizontal=True,
    help="**Performance**: adjusts bids up/down based on KPI targets and segments. Requires both files.\n\n"
         "**Scale**: increases bids based on FillRate to grow volume. Only internal file required.",
)
is_scale = opt_mode == "Scale Optimization"

if is_scale:
    st.info(
        "**Scale Optimization** — Only the internal file is required. "
        "Bids are increased based on FillRate bands (0–20% → +30%, 20–35% → +25%, "
        "35–50% → +20%, 50–70% → +15%, 70–85% → +10%, ≥85% → no change). "
        "CVR > 20% adds +5% bonus. Capped at highTier × 1.20. "
        "Sites with spend < $100, maxPreloads < 100, or existing dailyCap are excluded.",
        icon="ℹ️",
    )

st.divider()

# ---------------------------------------------------------------------------
# 1 — Upload Your Data Files
# ---------------------------------------------------------------------------
st.markdown("### 1 Upload Your Data Files")
col1, col2 = st.columns(2)
with col1:
    with st.container():
        st.caption("Internal Campaign Data (Excel .xlsx)")
        internal_file = st.file_uploader(
            "Internal Campaign Data (Excel .xlsx)",
            type=["xlsx"],
            key="internal",
            label_visibility="collapsed",
            help="Campaign/site-level bid and delivery data. Limit 200MB. XLSX only.",
        )
        if not internal_file:
            st.caption("Drag and drop file here — Limit 200MB per file · XLSX")
with col2:
    with st.container():
        adv_label = "Advertiser Performance Report (CSV) — optional" if is_scale else "Advertiser Performance Report (CSV)"
        st.caption(adv_label)
        advertiser_file = st.file_uploader(
            adv_label,
            type=["csv"],
            key="advertiser",
            label_visibility="collapsed",
            help="ROAS/ROI performance per site. Optional for Scale mode. Limit 200MB. CSV only.",
        )
        if not advertiser_file:
            hint = "Optional — adds ROI/ROAS columns to the report" if is_scale else "Drag and drop file here — Limit 200MB per file · CSV"
            st.caption(hint)

st.divider()

# ---------------------------------------------------------------------------
# 2 — Set Your KPI Goals (Performance mode only)
# ---------------------------------------------------------------------------
if not is_scale:
    st.markdown("### 2 Set Your KPI Goals")

    # Preset configurations for common campaigns
    PRESETS = {
        "Custom": {
            "kpi_mode": "roi",
            "main_col": "I",
            "main_target": 10.0,
            "secondary_col": "K",
            "secondary_target": 5.0,
            "weight_main": 80,
        },
        "Domino Dreams - ROAS D7": {
            "kpi_mode": "roas",
            "main_col": "Domino Dreams Marketing Campaigns Daily Metrics Full ROAS D7",
            "main_target": 2.18,
            "secondary_col": "K",
            "secondary_target": 2.0,
            "weight_main": 100,
        },
    }

    preset_choice = st.selectbox(
        "Campaign preset",
        options=list(PRESETS.keys()),
        index=0,
        help="Select a preset configuration for common campaigns, or choose 'Custom' to configure manually.",
    )
    preset = PRESETS[preset_choice]

    # KPI Mode selection
    kpi_mode = st.radio(
        "KPI Type",
        options=["ROI (percentage)", "ROAS (ratio)"],
        index=0 if preset["kpi_mode"] == "roi" else 1,
        horizontal=True,
        help="ROI is expressed as percentage (e.g., 10% = 0.10). ROAS is a ratio (e.g., 2.18% means $0.0218 return per $1 spent).",
    )
    kpi_mode_value = "roi" if "ROI" in kpi_mode else "roas"

    k1, k2 = st.columns(2)
    with k1:
        st.caption("**Primary KPI (D7)**")
        main_col_spec = st.text_input(
            "Column letter or name pattern",
            value=preset["main_col"],
            key="main_col",
            help="Column letter (e.g. 'I') or partial column name (e.g. 'ROAS D7' or 'Domino Dreams').",
        ).strip()
        main_target = st.number_input(
            "Target (%)",
            min_value=0.0,
            max_value=1000.0,
            value=preset["main_target"],
            step=0.01,
            format="%.2f",
            key="main_target",
            help="Target percentage for the primary KPI. For ROAS, 2.18 means 2.18%.",
        )
    with k2:
        st.caption("**Secondary KPI (D14/D30)**")
        secondary_col_spec = st.text_input(
            "Column letter or name pattern",
            value=preset["secondary_col"],
            key="secondary_col",
            help="Column letter (e.g. 'K') or partial column name (e.g. 'ROAS D14').",
        ).strip()
        secondary_target = st.number_input(
            "Target (%)",
            min_value=0.0,
            max_value=1000.0,
            value=preset["secondary_target"],
            step=0.01,
            format="%.2f",
            key="secondary_target",
            help="Target percentage for the secondary KPI.",
        )

    st.markdown("**How important is the Main KPI compared to the Secondary KPI?**")
    weight_main = st.slider(
        "Main KPI weight",
        min_value=0,
        max_value=100,
        value=preset["weight_main"],
        step=5,
        key="weight_slider",
        label_visibility="collapsed",
    )
    weight_secondary = 100 - weight_main
    st.caption(f"Main {weight_main}% / Secondary {weight_secondary}% — The optimizer will weight the Main KPI at {weight_main}% and the Secondary KPI at {weight_secondary}% when scoring each campaign.")

    st.divider()

    # ---------------------------------------------------------------------------
    # 3 — Optimization Settings (Performance only)
    # ---------------------------------------------------------------------------
    st.markdown("### 3 Optimization Settings")
    opt_goal = st.radio(
        "Optimization goal",
        options=["Scale", "Performance", "Other"],
        index=0,
        horizontal=True,
        help="Primary optimization objective.",
    )
    report_days = st.radio(
        "Report covers the last...",
        options=["30 days", "60 days", "Other"],
        index=0,
        horizontal=True,
        help="Time window of the report data.",
    )
    additional_notes = st.text_area(
        "Additional notes or constraints (optional)",
        placeholder="e.g. Advertiser wants to scale but keep performance — no single campaign should spend more than $100/day. Need at least 50 installs per week.",
        height=80,
        help="Optional context or constraints for the optimization.",
    )

    st.divider()

# ---------------------------------------------------------------------------
# Actions: prerequisite message vs Run Optimization
# ---------------------------------------------------------------------------
if is_scale:
    files_ready = internal_file is not None
else:
    files_ready = internal_file is not None and advertiser_file is not None

if not files_ready:
    needed = "the internal file" if is_scale else "both files"
    st.button(
        f"📄 Upload {needed} above to enable the optimizer.",
        type="primary",
        use_container_width=True,
        disabled=True,
    )
    run_clicked = False
else:
    run_clicked = st.button("🚀 Run Optimization", type="primary", use_container_width=True)

if run_clicked and files_ready:
    # Validate (Performance only)
    if not is_scale:
        if not main_col_spec:
            st.error("Main KPI column specification is required.")
            st.stop()
        if not secondary_col_spec:
            st.error("Secondary KPI column specification is required.")
            st.stop()
        if main_target <= 0:
            st.error("Main KPI target must be greater than 0.")
            st.stop()
        if secondary_target <= 0 and weight_secondary > 0:
            st.error("Secondary KPI target must be greater than 0 when secondary weight is used.")
            st.stop()

    with st.spinner("Running optimization…"):
        internal_path = None
        advertiser_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f:
                f.write(internal_file.getvalue())
                internal_path = f.name
            if advertiser_file:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
                    f.write(advertiser_file.getvalue())
                    advertiser_path = f.name

            if is_scale:
                output_bytes, summary = run_scale_optimization(
                    internal_file=internal_path,
                    advertiser_file=advertiser_path,
                )
            else:
                output_bytes, summary = run_optimization(
                    internal_file=internal_path,
                    advertiser_file=advertiser_path,
                    kpi_d7_pct=main_target,
                    kpi_d2nd_pct=secondary_target,
                    weight_main=weight_main / 100.0,
                    weight_secondary=weight_secondary / 100.0,
                    kpi_col_d7_spec=main_col_spec,
                    kpi_col_d2nd_spec=secondary_col_spec,
                    kpi_mode=kpi_mode_value,
                )
        except ValueError as e:
            st.error(f"Error: {e}")
            st.stop()
        finally:
            for p in (internal_path, advertiser_path):
                if p and os.path.isfile(p):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    # Results
    if is_scale:
        st.success(f"Scale Optimization done! {summary.get('rows_actioned', 0)} sites actioned.")
        a, b, c = st.columns(3)
        a.metric("Total sites", summary.get("total_rows", 0))
        b.metric("Sites actioned", summary.get("rows_actioned", 0))
        c.metric("Sorted by", "FillRate ↓")
    else:
        kpi_mode_label = "ROAS" if summary.get("kpi_mode") == "roas" else "ROI"
        st.success(f"Done! {summary.get('rows_actioned', 0)} sites actioned using {kpi_mode_label} mode.")
        a, b, c, d, e = st.columns(5)
        a.metric("Total sites", summary.get("total_rows", 0))
        b.metric("Sites actioned", summary.get("rows_actioned", 0))
        c.metric("Sites disregarded", summary.get("rows_disregarded", 0))
        d.metric("Daily cap suggestions", summary.get("rows_with_cap", 0))
        kpi_d7_target = summary.get("kpi_d7_target", 0)
        e.metric(f"D7 Target ({kpi_mode_label})", f"{kpi_d7_target:.2%}")

    ab = summary.get("action_breakdown") or {}
    sb = summary.get("segment_breakdown") or {}

    if ab or sb:
        t1, t2 = st.columns(2)
        if ab:
            with t1:
                st.write("**Action breakdown**")
                st.dataframe(
                    [{"Action": k, "Count": v} for k, v in sorted(ab.items(), key=lambda x: -x[1])],
                    use_container_width=True,
                    hide_index=True,
                )
        if sb:
            with t2:
                st.write("**Segment breakdown**")
                st.dataframe(
                    [{"Segment": k, "Count": v} for k, v in sorted(sb.items(), key=lambda x: -x[1])],
                    use_container_width=True,
                    hide_index=True,
                )

    # Download buttons — CSV and Excel
    dl1, dl2 = st.columns(2)
    with dl1:
        csv_buf = xlsx_to_csv(output_bytes)
        st.download_button(
            "📥 Download CSV",
            data=csv_buf.getvalue(),
            file_name="optimization_output.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )
    with dl2:
        output_bytes.seek(0)
        st.download_button(
            "📥 Download Excel",
            data=output_bytes.getvalue(),
            file_name="optimization_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
