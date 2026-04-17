# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Settings page: inspect and manage on-disk caches and app state."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

import pandas as pd
import streamlit as st

from src.config.settings import settings

st.title("Settings")
st.caption("Inspect caches, clear buffers, and manage runtime state.")

ROOT = Path(__file__).resolve().parents[3]
TOOL_CACHE_DIR = ROOT / settings.cache_dir          # .cache/
SYMBOL_CACHE_DIR = ROOT / ".cache" / "symbol_resolver"


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _load_tool_cache_entries(cache_dir: Path) -> list[dict]:
    """Read every *.json entry in the tool cache. Entries are written by
    ``src.utils.cache.AnalysisCache`` as ``{value, expires_at}`` with the
    key hashed in the filename (the raw key is not preserved)."""
    rows: list[dict] = []
    if not cache_dir.exists():
        return rows
    now = time.time()
    for p in sorted(cache_dir.iterdir()):
        if not p.is_file() or p.suffix != ".json":
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            rows.append({
                "File": p.name, "Tool": "—", "Key": "—",
                "Expires": "(unreadable)", "Status": "corrupt",
                "Size": _human_size(p.stat().st_size),
                "_path": str(p),
            })
            continue
        exp = float(payload.get("expires_at", 0) or 0)
        status = "valid" if exp > now else "expired"
        exp_str = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S") if exp else "—"
        val = payload.get("value")
        # Heuristic preview: show the first scalar keys of the value dict.
        preview = ""
        if isinstance(val, dict):
            preview = ", ".join(f"{k}={val[k]!r}" for k in list(val.keys())[:3])[:120]
        rows.append({
            "File": p.name,
            "Expires": exp_str,
            "Status": status,
            "Size": _human_size(p.stat().st_size),
            "Preview": preview,
            "_path": str(p),
        })
    return rows


def _load_symbol_cache_entries(cache_dir: Path) -> list[dict]:
    """Symbol-resolver entries: {key, exchange, symbol} per file, grouped
    under an exchange sub-directory."""
    rows: list[dict] = []
    if not cache_dir.exists():
        return rows
    for sub in sorted(cache_dir.iterdir()):
        if not sub.is_dir():
            continue
        for p in sorted(sub.iterdir()):
            if not p.is_file() or p.suffix != ".json":
                continue
            try:
                payload = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            rows.append({
                "Exchange": sub.name,
                "Query": payload.get("key") or p.stem,
                "Resolved Symbol": payload.get("symbol") or "—",
                "Size": _human_size(p.stat().st_size),
                "_path": str(p),
            })
    return rows


def _rm_many(paths: list[str]) -> tuple[int, int]:
    ok, fail = 0, 0
    for p in paths:
        try:
            Path(p).unlink()
            ok += 1
        except Exception:
            fail += 1
    return ok, fail


tab_cache, tab_state = st.tabs(["Cache", "Session State"])

# -------------------------- CACHE TAB --------------------------
with tab_cache:
    st.subheader("Tool Cache")
    st.caption(
        f"Directory: `{TOOL_CACHE_DIR}` • TTL controlled by individual tool calls • "
        "Keys are hashed into filenames (raw keys not stored)."
    )

    tool_rows = _load_tool_cache_entries(TOOL_CACHE_DIR)
    if tool_rows:
        total_size = sum(Path(r["_path"]).stat().st_size for r in tool_rows if Path(r["_path"]).exists())
        valid = sum(1 for r in tool_rows if r.get("Status") == "valid")
        expired = sum(1 for r in tool_rows if r.get("Status") == "expired")

        c1, c2, c3 = st.columns(3)
        c1.metric("Entries", len(tool_rows))
        c2.metric("Valid / Expired", f"{valid} / {expired}")
        c3.metric("Total Size", _human_size(total_size))

        df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in tool_rows])
        st.dataframe(df, width="stretch", hide_index=True)

        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("Clear expired", key="clear_exp_tool",
                         disabled=expired == 0, width="stretch"):
                paths = [r["_path"] for r in tool_rows if r.get("Status") == "expired"]
                ok, fail = _rm_many(paths)
                st.success(f"Removed {ok} expired entries" + (f" ({fail} failed)" if fail else ""))
                st.rerun()
        with b2:
            confirm = st.session_state.get("_confirm_clear_tool", False)
            label = "Confirm clear ALL" if confirm else "Clear all"
            if st.button(label, key="clear_all_tool",
                         disabled=len(tool_rows) == 0, width="stretch",
                         type="primary" if confirm else "secondary"):
                if confirm:
                    ok, fail = _rm_many([r["_path"] for r in tool_rows])
                    st.session_state._confirm_clear_tool = False
                    st.success(f"Removed {ok} entries" + (f" ({fail} failed)" if fail else ""))
                    st.rerun()
                else:
                    st.session_state._confirm_clear_tool = True
                    st.warning("Click again to confirm.")
        with b3:
            if st.button("Refresh", key="refresh_tool", width="stretch"):
                st.rerun()
    else:
        st.info(f"Tool cache is empty (or directory does not exist): `{TOOL_CACHE_DIR}`")

    st.divider()

    st.subheader("Symbol Resolver Cache")
    st.caption(
        f"Directory: `{SYMBOL_CACHE_DIR}` • Persists `yf.Search` lookups so the same "
        "free-form ticker (e.g. `natco`) only hits Yahoo once."
    )
    sym_rows = _load_symbol_cache_entries(SYMBOL_CACHE_DIR)
    if sym_rows:
        c1, c2 = st.columns(2)
        c1.metric("Entries", len(sym_rows))
        total = sum(Path(r["_path"]).stat().st_size for r in sym_rows if Path(r["_path"]).exists())
        c2.metric("Total Size", _human_size(total))

        df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in sym_rows])
        st.dataframe(df, width="stretch", hide_index=True)

        if st.button("Clear symbol cache", key="clear_sym", width="stretch"):
            ok, fail = _rm_many([r["_path"] for r in sym_rows])
            st.success(f"Removed {ok} entries" + (f" ({fail} failed)" if fail else ""))
            # Also drop any empty exchange sub-dirs.
            if SYMBOL_CACHE_DIR.exists():
                for sub in SYMBOL_CACHE_DIR.iterdir():
                    try:
                        if sub.is_dir() and not any(sub.iterdir()):
                            sub.rmdir()
                    except Exception:
                        pass
            # Also clear the lru_cache in the resolver.
            try:
                from src.config import symbol_resolver as sr
                sr._load_catalog.cache_clear()
            except Exception:
                pass
            st.rerun()
    else:
        st.info(f"Symbol resolver cache is empty: `{SYMBOL_CACHE_DIR}`")

# -------------------------- SESSION STATE TAB --------------------------
with tab_state:
    st.subheader("Streamlit Session State")
    st.caption("In-memory state for this browser session. Cleared on server restart.")

    def _summarize(v):
        if isinstance(v, (str, int, float, bool)) or v is None:
            s = repr(v)
            return s if len(s) < 200 else s[:197] + "..."
        if isinstance(v, (list, tuple, set)):
            return f"{type(v).__name__}(len={len(v)})"
        if isinstance(v, dict):
            return f"dict(keys={len(v)})"
        return f"<{type(v).__name__}>"

    keys = sorted(k for k in st.session_state.keys() if not str(k).startswith("_"))
    if keys:
        rows = [{"Key": k, "Summary": _summarize(st.session_state[k])} for k in keys]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("Session state is empty.")

    if st.button("Reset tool tracker (clear Stream Data & Tool Log)",
                 key="reset_tracker", width="stretch"):
        tracker = st.session_state.get("tool_tracker")
        if tracker is not None:
            tracker.reset()
            st.success("Tool tracker reset.")
        else:
            st.info("No tool tracker in session state.")
