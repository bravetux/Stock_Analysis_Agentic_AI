# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Author: B.Vignesh Kumar aka Bravetux
# Email:  ic19939@gmail.com
# Developed: 10th April 2026

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

import streamlit as st
import pandas as pd
from src.config.settings import settings
from src.db.report_store import ReportStore
from src.ui.pdf_export import markdown_to_pdf
from src.reports.diff import (
    compare_fields,
    compare_sections,
    summarise_section_changes,
    build_ai_delta_prompt,
)


@st.cache_resource
def get_report_store():
    return ReportStore(db_path=settings.db_path, cache_hours=settings.report_cache_hours)

store = get_report_store()

st.title("Report History")
st.caption(f"Reports retained for {settings.report_cache_hours} hours ({settings.report_cache_hours // 24} days). Set REPORT_CACHE_HOURS=0 to keep forever.")

search_query = st.text_input("Search ticker", placeholder="e.g., RELIANCE, AAPL")

if search_query:
    tickers = store.search_tickers(search_query)
    if not tickers:
        st.info("No reports found matching that ticker.")
    else:
        selected_ticker = st.selectbox("Select ticker", tickers)
        if selected_ticker:
            history = store.get_report_history(selected_ticker)
            if not history:
                st.info("No reports found.")
            else:
                st.caption(f"Found {len(history)} report(s) for {selected_ticker}")

                # Comparison selector
                if len(history) >= 2:
                    st.subheader("Compare Reports")
                    compare_options = [
                        f"#{r['id']} \u2014 {r['exchange']}:{r['ticker']} | {r['profile']} | {r['analyzed_at']}"
                        for r in history
                    ]
                    col_a, col_b = st.columns(2)
                    with col_a:
                        sel_a = st.selectbox("Report A (newer)", compare_options, index=0, key="cmp_a")
                    with col_b:
                        sel_b = st.selectbox("Report B (older)", compare_options, index=1, key="cmp_b")

                    if st.button("Compare", key="compare_btn"):
                        st.session_state["cmp_selection"] = (sel_a, sel_b)

                    # Render diff when a comparison selection is pinned.
                    # (Pinning avoids losing the view when AI-explain is clicked.)
                    if "cmp_selection" in st.session_state:
                        sel_a_cur, sel_b_cur = st.session_state["cmp_selection"]
                        if sel_a_cur in compare_options and sel_b_cur in compare_options:
                            idx_a = compare_options.index(sel_a_cur)
                            idx_b = compare_options.index(sel_b_cur)
                            report_after = history[idx_a]   # A = newer
                            report_before = history[idx_b]  # B = older
                            md_after = report_after["report_markdown"]
                            md_before = report_before["report_markdown"]

                            st.divider()
                            st.markdown(
                                f"#### Comparing **{report_before['analyzed_at']}** → **{report_after['analyzed_at']}** "
                                f"({report_before['profile']} vs {report_after['profile']})"
                            )

                            # ---- 1. Headline metrics delta table ----
                            def _fmt_ts(ts) -> str:
                                """Render timestamps as DDMMYYYY-HHMMSS."""
                                from datetime import datetime
                                if ts is None:
                                    return ""
                                s = str(ts)
                                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                                            "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                                    try:
                                        return datetime.strptime(s.split("+")[0].strip(), fmt).strftime("%d%m%Y-%H%M%S")
                                    except ValueError:
                                        continue
                                return s

                            field_changes = compare_fields(md_before, md_after)
                            if field_changes:
                                st.subheader("What changed (metrics)")
                                before_col = f"Before\n{_fmt_ts(report_before['analyzed_at'])}"
                                after_col = f"After\n{_fmt_ts(report_after['analyzed_at'])}"
                                rows = []
                                for c in field_changes:
                                    rows.append({
                                        "Field": c.field,
                                        before_col: c.fmt_before(),
                                        after_col: c.fmt_after(),
                                        "Δ / Direction": c.fmt_delta(),
                                        "Status": c.direction,
                                    })
                                df = pd.DataFrame(rows)
                                # Highlight status cells.
                                def _row_style(s):
                                    color_map = {
                                        "up": "background-color: #e7f5e7",
                                        "down": "background-color: #fbe7e7",
                                        "changed": "background-color: #fff4d6",
                                        "added": "background-color: #e7eefb",
                                        "removed": "background-color: #f0e7fb",
                                        "same": "color: #888",
                                    }
                                    return [color_map.get(s["Status"], "") for _ in s]
                                # Size the table so every row is visible (no vertical scroll)
                                # and columns auto-fit the content (no horizontal scroll).
                                table_height = 38 * (len(df) + 1) + 6
                                col_cfg = {
                                    "Field": st.column_config.TextColumn("Field", width="medium"),
                                    before_col: st.column_config.TextColumn(before_col, width="medium"),
                                    after_col: st.column_config.TextColumn(after_col, width="medium"),
                                    "Δ / Direction": st.column_config.TextColumn("Δ / Direction", width="small"),
                                    "Status": st.column_config.TextColumn("Status", width="small"),
                                }
                                try:
                                    st.dataframe(
                                        df.style.apply(_row_style, axis=1),
                                        width="stretch",
                                        hide_index=True,
                                        height=table_height,
                                        column_config=col_cfg,
                                    )
                                except Exception:
                                    st.dataframe(
                                        df,
                                        width="stretch",
                                        hide_index=True,
                                        height=table_height,
                                        column_config=col_cfg,
                                    )
                            else:
                                st.info("No extractable metrics found in either report.")

                            # ---- 2. Heading-based section diff ----
                            st.subheader("What changed (sections)")
                            section_changes = compare_sections(md_before, md_after)
                            counts = summarise_section_changes(section_changes)
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Unchanged", counts.get("unchanged", 0))
                            c2.metric("Changed", counts.get("changed", 0))
                            c3.metric("Added", counts.get("added", 0))
                            c4.metric("Removed", counts.get("removed", 0))

                            # Show changed + added + removed sections side-by-side.
                            notable = [c for c in section_changes if c.status != "unchanged"]
                            if not notable:
                                st.success("No section-level changes detected — only cosmetic wording differs.")
                            else:
                                status_label = {
                                    "changed": "Modified",
                                    "added": "Added in newer",
                                    "removed": "Removed in newer",
                                }
                                for sc in notable:
                                    icon = {"changed": "🔄", "added": "➕", "removed": "➖"}.get(sc.status, "•")
                                    with st.expander(
                                        f"{icon} [{status_label.get(sc.status, sc.status)}] {sc.display_path}",
                                        expanded=(sc.status != "changed") and len(notable) < 6,
                                    ):
                                        if sc.status == "changed":
                                            cL, cR = st.columns(2)
                                            with cL:
                                                st.caption(f"Before — {report_before['analyzed_at']}")
                                                st.markdown(sc.before_body or "*(empty)*")
                                            with cR:
                                                st.caption(f"After — {report_after['analyzed_at']}")
                                                st.markdown(sc.after_body or "*(empty)*")
                                        elif sc.status == "added":
                                            st.markdown(sc.after_body or "*(empty)*")
                                        else:  # removed
                                            st.markdown(sc.before_body or "*(empty)*")

                            # ---- 3. Optional: AI-narrated delta ----
                            st.divider()
                            col_ai, _ = st.columns([1, 3])
                            with col_ai:
                                if st.button("Explain changes (AI)", key="ai_delta_btn"):
                                    st.session_state["_ai_delta_request"] = True
                            if st.session_state.pop("_ai_delta_request", False):
                                with st.spinner("Asking Bedrock to narrate the delta..."):
                                    try:
                                        from src.agents.bedrock_call import converse
                                        sys_p, usr_p = build_ai_delta_prompt(
                                            ticker=report_after["ticker"],
                                            exchange=report_after["exchange"],
                                            before_md=md_before,
                                            after_md=md_after,
                                            before_label=f"report_{report_before['analyzed_at']}",
                                            after_label=f"report_{report_after['analyzed_at']}",
                                        )
                                        narrative = converse(sys_p, usr_p, temperature=0.2, max_tokens=800)
                                        st.session_state["_ai_delta_narrative"] = narrative or "*(empty response)*"
                                    except Exception as e:
                                        st.session_state["_ai_delta_narrative"] = None
                                        st.error(f"AI narration failed: {e}")
                            if st.session_state.get("_ai_delta_narrative"):
                                st.markdown("#### AI Narrative")
                                st.markdown(st.session_state["_ai_delta_narrative"])

                            # ---- 4. Full reports, collapsed ----
                            with st.expander("Full reports side-by-side", expanded=False):
                                col_left, col_right = st.columns(2)
                                with col_left:
                                    st.markdown(f"##### Before — {report_before['analyzed_at']}")
                                    st.markdown(md_before)
                                with col_right:
                                    st.markdown(f"##### After — {report_after['analyzed_at']}")
                                    st.markdown(md_after)

                            if st.button("Clear comparison", key="clear_cmp_btn"):
                                st.session_state.pop("cmp_selection", None)
                                st.session_state.pop("_ai_delta_narrative", None)
                                st.rerun()

                    st.divider()

                # Individual report history
                for report in history:
                    label = f"{report['exchange']}:{report['ticker']} | {report['profile']} | {report['analyzed_at']}"
                    with st.expander(label, expanded=False):
                        st.markdown(report["report_markdown"])

                        col1, col2 = st.columns(2)
                        with col1:
                            st.download_button(
                                label="Download MD",
                                data=report["report_markdown"],
                                file_name=f"{report['exchange']}_{report['ticker']}_{report['id']}.md",
                                mime="text/markdown",
                                key=f"hist_md_{report['id']}",
                            )
                        with col2:
                            pdf_bytes = markdown_to_pdf(
                                report["report_markdown"],
                                report["ticker"],
                                report["exchange"],
                                report["profile"],
                            )
                            st.download_button(
                                label="Download PDF",
                                data=pdf_bytes,
                                file_name=f"{report['exchange']}_{report['ticker']}_{report['id']}.pdf",
                                mime="application/pdf",
                                key=f"hist_pdf_{report['id']}",
                            )
else:
    st.caption("Enter a ticker symbol above to browse past reports.")
