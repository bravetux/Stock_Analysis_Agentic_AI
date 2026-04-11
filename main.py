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
import logging
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
    parser.add_argument("--pdf", action="store_true", help="Export analysis as PDF to reports/ folder")
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
    from src.ui.pdf_export import markdown_to_pdf, save_pdf_to_disk

    profile = PROFILES[args.profile]
    print(f"Analysis level: {profile.label} — {profile.description}\n")

    store = ReportStore(db_path=settings.db_path, cache_hours=settings.report_cache_hours)

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
                if args.pdf:
                    pdf_bytes = markdown_to_pdf(report_md, ticker, exchange, cached["profile"])
                    pdf_path = save_pdf_to_disk(pdf_bytes, ticker, exchange, settings.reports_dir)
                    print(f"PDF saved: {pdf_path}")
                return report_md
            else:
                print(f"No cached report for {display}. Running fresh analysis...")

        print(f"Analyzing {display} on {exchange}...")
        agent = create_orchestrator(profile=args.profile)
        response = agent(
            f"Analyze the stock {display} on {exchange} exchange. "
            f"Use up to {profile.news_queries} news search queries.\n\n"
            f"{profile.prompt_instructions}"
        )
        report_md = str(response)
        print(report_md)

        pdf_path = None
        if args.pdf:
            pdf_bytes = markdown_to_pdf(report_md, ticker, exchange, args.profile)
            pdf_path = save_pdf_to_disk(pdf_bytes, ticker, exchange, settings.reports_dir)
            print(f"PDF saved: {pdf_path}")

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
