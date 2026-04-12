# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

"""
AG-UC-0999: Stock Analysis AI Agent
Entry point — run with: streamlit run src/ui/app.py
Or for CLI mode: python main.py <ticker>
"""

import sys
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    import argparse
    from src.config.analysis_profiles import PROFILES, PROFILE_ORDER, DEFAULT_PROFILE

    parser = argparse.ArgumentParser(
        description="AG-UC-0999: Stock Analysis AI Agent",
        epilog="UI mode: streamlit run src/ui/app.py",
    )
    parser.add_argument("ticker", nargs="?", help="Stock ticker (e.g., NSE:RELIANCE, AAPL)")
    parser.add_argument("exchange", nargs="?", help="Exchange override (NSE, BSE, NASDAQ)")
    parser.add_argument("--batch", metavar="FILE", help="Batch mode: path to stocks.txt")
    parser.add_argument(
        "--profile",
        choices=PROFILE_ORDER,
        default=DEFAULT_PROFILE,
        help=f"Analysis level (default: {DEFAULT_PROFILE})",
    )
    parser.add_argument("--cached", action="store_true", help="Use cached report from database if available")
    args = parser.parse_args()

    if not args.ticker and not args.batch:
        parser.print_help()
        sys.exit(1)

    from src.agents.orchestrator import create_orchestrator
    from src.config.exchanges import detect_exchange, get_display_ticker, strip_prefix
    from src.tools.batch_tools import read_stocks_file
    from src.config.settings import settings
    from src.db.report_store import ReportStore
    from src.ui.pdf_export import markdown_to_pdf, save_pdf_to_disk, save_md_to_disk, build_tool_log_markdown

    profile = PROFILES[args.profile]
    print(f"Analysis level: {profile.label} — {profile.description}\n")

    store = ReportStore(db_path=settings.db_path, cache_hours=settings.report_cache_hours)

    # Tool progress tracking for CLI
    tool_log: list[dict] = []
    _tool_starts: dict[str, float] = {}

    def _on_tool_start(tool_name: str):
        _tool_starts[tool_name] = time.time()
        print(f"  ▶ {tool_name} ...", flush=True)

    def _on_tool_end(tool_name: str, elapsed: float):
        start_ts = _tool_starts.pop(tool_name, None)
        started = datetime.fromtimestamp(start_ts).strftime("%H:%M:%S") if start_ts else "—"
        completed = datetime.now().strftime("%H:%M:%S")
        tool_log.append({"Tool": tool_name, "Started": started, "Completed": completed, "Duration (s)": round(elapsed, 2)})
        print(f"  ✓ {tool_name} ({elapsed:.2f}s)", flush=True)

    def _print_tool_summary():
        if not tool_log:
            return
        print(f"\n{'─'*60}")
        print("Tool Execution Summary")
        print(f"{'─'*60}")
        print(f"{'Tool':<35} {'Started':<10} {'Completed':<10} {'Duration':>8}")
        print(f"{'─'*35} {'─'*10} {'─'*10} {'─'*8}")
        for entry in tool_log:
            print(f"{entry['Tool']:<35} {entry['Started']:<10} {entry['Completed']:<10} {entry['Duration (s)']:>7.2f}s")
        total = sum(e["Duration (s)"] for e in tool_log)
        print(f"{'─'*60}")
        print(f"{'Total':<35} {'':10} {'':10} {total:>7.2f}s")
        print(f"{'─'*60}\n")

    def analyze_single(ticker_input: str, exchange_override: str | None = None):
        """Analyze a single stock, save to DB, optionally export PDF."""
        ticker = strip_prefix(ticker_input)
        if exchange_override:
            exchange = exchange_override.upper()
        else:
            exchange = detect_exchange(ticker_input).value
        display = get_display_ticker(ticker_input)

        if args.cached:
            cached = store.get_latest_report(ticker, exchange)
            if cached:
                print(f"[Cached] {display} on {exchange} (from {cached['analyzed_at']})")
                report_md = cached["report_markdown"]
                print(report_md)
                # Auto-save cached report as PDF and MD
                pdf_bytes = markdown_to_pdf(report_md, ticker, exchange, cached["profile"])
                pdf_path = save_pdf_to_disk(pdf_bytes, ticker, exchange, settings.reports_dir)
                md_path = save_md_to_disk(report_md, ticker, exchange, settings.reports_dir)
                print(f"PDF saved: {pdf_path}")
                print(f"MD saved: {md_path}")
                return report_md
            else:
                print(f"No cached report for {display}. Running fresh analysis...")

        print(f"Analyzing {display} on {exchange}...")
        tool_log.clear()
        agent = create_orchestrator(
            profile=args.profile,
            on_tool_start=_on_tool_start,
            on_tool_end=_on_tool_end,
        )
        response = agent(
            f"Analyze the stock {display} on {exchange} exchange. "
            f"Use up to {profile.news_queries} news search queries.\n\n"
            f"{profile.prompt_instructions}"
        )
        report_md = str(response)
        print(report_md)
        _print_tool_summary()

        # Build full report with tool execution log
        tool_log_md = build_tool_log_markdown(tool_log)
        full_report = report_md + tool_log_md

        # Always auto-save PDF and MD to reports/
        pdf_bytes = markdown_to_pdf(full_report, ticker, exchange, args.profile)
        pdf_path = save_pdf_to_disk(pdf_bytes, ticker, exchange, settings.reports_dir)
        md_path = save_md_to_disk(full_report, ticker, exchange, settings.reports_dir)
        print(f"PDF saved: {pdf_path}")
        print(f"MD saved: {md_path}")

        store.save_report(ticker, exchange, args.profile, report_md, pdf_path)
        return report_md

    if args.batch:
        file_path = args.batch
        stocks = read_stocks_file.__wrapped__(file_path)
        if stocks and isinstance(stocks[0], dict) and "error" in stocks[0]:
            print(f"Error: {stocks[0]['error']}")
            sys.exit(1)

        print(f"Batch analyzing {len(stocks)} stocks...\n")
        for i, stock in enumerate(stocks, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(stocks)}] {stock['ticker']} ({stock['exchange']})")
            print(f"{'='*60}\n")
            analyze_single(stock["ticker"], stock["exchange"])
    else:
        analyze_single(args.ticker, args.exchange)


if __name__ == "__main__":
    main()
