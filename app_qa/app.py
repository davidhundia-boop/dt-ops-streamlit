"""
Play Integrity Pre-Sales Screener
Streamlit front-end for play_integrity_analyzer.py.
"""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import time

import pandas as pd
import streamlit as st

# Ensure the analyzer module resolves from the same directory as this script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apk_fetcher import extract_package_name, fetch_apk
from play_integrity_analyzer import PlayIntegrityAnalyzer


# ============================================================================
# Helpers
# ============================================================================

def get_app_metadata(package_name: str) -> dict:
    """Return {title, icon} from Google Play. Falls back gracefully."""
    try:
        from google_play_scraper import app as gps_app
        data = gps_app(package_name, lang="en", country="us")
        return {
            "title": data.get("title") or package_name,
            "icon": data.get("icon"),
        }
    except Exception:
        return {"title": package_name, "icon": None}


def run_analyzer(apk_path: str) -> tuple[dict, str]:
    """
    Run PlayIntegrityAnalyzer silently.
    Returns (to_json() dict, captured stdout text).
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        analyzer = PlayIntegrityAnalyzer(apk_path)
        analyzer.analyze()
    return analyzer.to_json(), buf.getvalue()


def verdict_display(result: dict) -> dict:
    """Map an analyzer result dict to display metadata."""
    verdict = result.get("verdict", "ERROR")
    fail_ids = [
        item.get("id", "")
        for item in result.get("details", {}).get("fail", [])
    ]

    if verdict == "FAIL":
        messages = []
        if "pairip_auto_protect" in fail_ids:
            messages.append(
                "❌ FAIL — Auto Protect enabled. "
                "Client must disable in Play Console + upload new build."
            )
        if "legacy_play_licensing" in fail_ids:
            messages.append(
                "❌ FAIL — Legacy Play Licensing blocks sideloaded installs."
            )
        if not messages:
            messages.append("❌ FAIL — Blocking protection detected.")
        return {"messages": messages, "color": "#FF4B4B", "bg": "#2d0f0f", "border": "#FF4B4B"}

    if verdict == "WARNING":
        return {
            "messages": [
                "⚠️ WARNING — Uses Play Integrity API. "
                "Server-side enforcement unknown. Verify with client."
            ],
            "color": "#FFA500",
            "bg": "#2d1e00",
            "border": "#FFA500",
        }

    if verdict == "PASS":
        return {
            "messages": ["✅ PASS — No Play Integrity blockers detected."],
            "color": "#21c55d",
            "bg": "#0d2d1a",
            "border": "#21c55d",
        }

    if verdict == "INCONCLUSIVE":
        return {
            "messages": [
                "⚙️ INCONCLUSIVE — Could not fully analyze APK. Manual testing required."
            ],
            "color": "#aaaaaa",
            "bg": "#1e1e1e",
            "border": "#555555",
        }

    # ERROR / fetch failed
    return {
        "messages": ["⚙️ ERROR — Could not download APK."],
        "color": "#aaaaaa",
        "bg": "#1e1e1e",
        "border": "#555555",
    }


def _card_html(message: str, color: str, bg: str, border: str) -> str:
    return (
        f'<div style="background:{bg};border-left:4px solid {border};'
        f'padding:12px 16px;border-radius:6px;margin:6px 0;'
        f'font-size:1rem;color:{color};font-weight:500;">'
        f"{message}</div>"
    )


def render_details_expander(result: dict):
    fail_items = result.get("details", {}).get("fail", [])
    warn_items = result.get("details", {}).get("warning", [])
    error_msg = result.get("error")

    has_content = bool(error_msg or fail_items or warn_items)

    with st.expander("Details  *(internal — do not share with client)*"):
        if error_msg:
            st.code(error_msg)
            return

        if not has_content:
            st.write("No issues detected.")
            st.caption(f"DEX strings analyzed: {result.get('dex_string_count', 'N/A')}")
            return

        for item in fail_items:
            st.markdown(f"**[FAIL] {item['name']}**")
            st.write(item.get("description", ""))
            if item.get("evidence"):
                st.code("\n".join(item["evidence"][:10]))

        for item in warn_items:
            st.markdown(f"**[WARNING] {item['name']}**")
            st.write(item.get("description", ""))
            if item.get("evidence"):
                st.code("\n".join(item["evidence"][:10]))


def render_result_card(result: dict):
    disp = verdict_display(result)
    app_name = result.get("app_name") or result.get("package", "Unknown")
    package = result.get("package", "")
    icon_url = result.get("icon")

    icon_col, info_col = st.columns([1, 11])
    with icon_col:
        if icon_url:
            st.image(icon_url, width=56)
        else:
            st.markdown("📦")
    with info_col:
        st.markdown(f"### {app_name}")
        if package and package != app_name:
            st.caption(package)

    for msg in disp["messages"]:
        st.markdown(
            _card_html(msg, disp["color"], disp["bg"], disp["border"]),
            unsafe_allow_html=True,
        )

    render_details_expander(result)


# ============================================================================
# Page config
# ============================================================================

st.set_page_config(
    page_title="Play Integrity Screener",
    page_icon="🔍",
    layout="centered",
)

st.title("🔍 Play Integrity Screener")
st.caption(
    "Pre-sales tool — checks whether an app will block Digital Turbine preloads"
)

# ============================================================================
# Session state
# ============================================================================

if "single_result" not in st.session_state:
    st.session_state.single_result = None
if "bulk_results" not in st.session_state:
    st.session_state.bulk_results = []

# ============================================================================
# Tabs
# ============================================================================

tab_single, tab_bulk = st.tabs(["Single App", "Bulk"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Single App
# ─────────────────────────────────────────────────────────────────────────────

with tab_single:
    st.subheader("Analyze a single app")

    input_val = st.text_input(
        "Paste a Google Play URL or package name",
        placeholder="https://play.google.com/store/apps/details?id=com.example.app",
        key="single_input",
    )

    if st.button("Analyze", type="primary", key="single_btn"):
        if not input_val.strip():
            st.warning("Please enter a URL or package name.")
        else:
            try:
                package_name = extract_package_name(input_val.strip())
            except ValueError as exc:
                st.error(str(exc))
                st.stop()

            result: dict = {"package": package_name}

            with st.spinner("Fetching app metadata…"):
                meta = get_app_metadata(package_name)
                result["app_name"] = meta["title"]
                result["icon"] = meta.get("icon")

            tmp_dir = tempfile.mkdtemp(prefix="pi_screener_")
            try:
                with st.spinner(f"Downloading APK for **{meta['title']}**…"):
                    apk_path = fetch_apk(package_name, tmp_dir)

                with st.spinner("Analyzing…"):
                    analysis, _ = run_analyzer(apk_path)
                    result.update(analysis)
                    # restore scraper name (analyzer may write "unknown")
                    result["app_name"] = meta["title"]
                    result["icon"] = meta.get("icon")

            except Exception as exc:
                result["verdict"] = "ERROR"
                result["error"] = str(exc)
                result.setdefault("details", {})

            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

            st.session_state.single_result = result

    # Render persisted result so expanders survive reruns
    if st.session_state.single_result:
        st.markdown("---")
        render_result_card(st.session_state.single_result)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Bulk
# ─────────────────────────────────────────────────────────────────────────────

with tab_bulk:
    st.subheader("Analyze multiple apps")

    col_text, col_upload = st.columns([2, 1])

    with col_text:
        bulk_text = st.text_area(
            "One URL or package name per line",
            height=160,
            placeholder=(
                "com.example.app1\n"
                "https://play.google.com/store/apps/details?id=com.example.app2\n"
                "com.example.app3"
            ),
            key="bulk_text",
        )

    with col_upload:
        st.write("")
        st.write("")
        uploaded_csv = st.file_uploader(
            "Or upload CSV",
            type=["csv"],
            help="CSV must have a **url** or **package_name** column",
            key="bulk_csv",
        )

    if st.button("Analyze All", type="primary", key="bulk_btn"):
        inputs: list[str] = []

        if uploaded_csv:
            try:
                df_up = pd.read_csv(uploaded_csv)
                col = next(
                    (c for c in ("url", "package_name") if c in df_up.columns), None
                )
                if col:
                    inputs.extend(str(v) for v in df_up[col].dropna().tolist())
                else:
                    st.warning(
                        "CSV must have a 'url' or 'package_name' column. File ignored."
                    )
            except Exception as exc:
                st.warning(f"Could not read CSV: {exc}")

        if bulk_text.strip():
            for line in bulk_text.strip().splitlines():
                line = line.strip()
                if line:
                    inputs.append(line)

        if not inputs:
            st.warning("No inputs provided.")
        else:
            # Parse package names; record parse errors immediately
            parsed: list[tuple[str, str | None, str | None]] = []
            for raw in inputs:
                try:
                    pkg = extract_package_name(raw.strip())
                    parsed.append((raw, pkg, None))
                except ValueError as exc:
                    parsed.append((raw, None, str(exc)))

            total = len(parsed)
            st.info(f"Processing {total} app(s)…")
            progress = st.progress(0)
            status = st.empty()

            results: list[dict] = []

            for idx, (original, pkg, parse_err) in enumerate(parsed):
                label = pkg or original
                status.text(f"[{idx + 1}/{total}] {label}…")

                if parse_err:
                    results.append(
                        {
                            "input": original,
                            "package": original,
                            "app_name": original,
                            "verdict": "ERROR",
                            "error": parse_err,
                            "icon": None,
                            "details": {},
                        }
                    )
                else:
                    tmp_dir = tempfile.mkdtemp(prefix="pi_screener_")
                    try:
                        meta = get_app_metadata(pkg)
                        apk_path = fetch_apk(pkg, tmp_dir)
                        analysis, _ = run_analyzer(apk_path)
                        r = dict(analysis)
                        r["input"] = original
                        r["app_name"] = meta["title"]
                        r["icon"] = meta.get("icon")
                        r["package"] = pkg
                        results.append(r)
                    except Exception as exc:
                        meta = get_app_metadata(pkg) if pkg else {"title": original}
                        results.append(
                            {
                                "input": original,
                                "package": pkg or original,
                                "app_name": meta["title"],
                                "verdict": "ERROR",
                                "error": str(exc),
                                "icon": None,
                                "details": {},
                            }
                        )
                    finally:
                        shutil.rmtree(tmp_dir, ignore_errors=True)

                progress.progress((idx + 1) / total)

                # Polite delay between fetches (skip after last item)
                if idx < total - 1:
                    time.sleep(2)

            status.text("Analysis complete.")
            st.session_state.bulk_results = results

    # ── Render persisted bulk results ──────────────────────────────────────

    if st.session_state.bulk_results:
        results = st.session_state.bulk_results

        SORT_KEY = {"FAIL": 0, "WARNING": 1, "INCONCLUSIVE": 2, "PASS": 3, "ERROR": 4}
        sorted_results = sorted(
            results, key=lambda r: SORT_KEY.get(r.get("verdict", "ERROR"), 99)
        )

        st.markdown("---")
        st.subheader("Results")

        for r in sorted_results:
            disp = verdict_display(r)
            app_name = r.get("app_name") or r.get("package", "")
            package = r.get("package", "")
            icon_url = r.get("icon")
            msg = disp["messages"][0] if disp["messages"] else ""

            with st.container():
                c1, c2, c3 = st.columns([3, 3, 4])
                with c1:
                    if icon_url:
                        ic, nm = st.columns([1, 5])
                        with ic:
                            st.image(icon_url, width=32)
                        with nm:
                            st.markdown(f"**{app_name}**")
                    else:
                        st.markdown(f"**{app_name}**")
                with c2:
                    st.caption(package)
                with c3:
                    st.markdown(
                        f'<span style="color:{disp["color"]};font-weight:500">'
                        f"{msg}</span>",
                        unsafe_allow_html=True,
                    )

            render_details_expander(r)
            st.divider()

        # ── CSV Export ──────────────────────────────────────────────────────
        VERDICT_LABEL = {
            "FAIL": "❌ FAIL",
            "WARNING": "⚠️ WARNING",
            "PASS": "✅ PASS",
            "INCONCLUSIVE": "⚙️ INCONCLUSIVE",
            "ERROR": "⚙️ ERROR",
        }

        export_rows = []
        for r in sorted_results:
            disp = verdict_display(r)
            verdict = r.get("verdict", "ERROR")
            export_rows.append(
                {
                    "App Name": r.get("app_name", ""),
                    "Package": r.get("package", ""),
                    "Verdict": VERDICT_LABEL.get(verdict, verdict),
                    "Message": "; ".join(disp["messages"]),
                    "Fail Reasons": ", ".join(
                        item["name"]
                        for item in r.get("details", {}).get("fail", [])
                    ),
                    "Warning Reasons": ", ".join(
                        item["name"]
                        for item in r.get("details", {}).get("warning", [])
                    ),
                    "Error": r.get("error", ""),
                }
            )

        df_export = pd.DataFrame(export_rows)
        st.download_button(
            label="⬇️ Export CSV",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name="play_integrity_results.csv",
            mime="text/csv",
        )
