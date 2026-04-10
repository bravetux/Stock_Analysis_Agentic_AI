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
    args = parser.parse_args()

    if not args.ticker and not args.batch:
        parser.print_help()
        sys.exit(1)

    from src.agents.orchestrator import create_orchestrator
    from src.config.exchanges import detect_exchange, get_display_ticker
    from src.tools.batch_tools import read_stocks_file

    profile = PROFILES[args.profile]
    print(f"Analysis level: {profile.label} — {profile.description}\n")

    if args.batch:
        file_path = args.batch
        stocks = read_stocks_file.__wrapped__(file_path)
        if stocks and isinstance(stocks[0], dict) and "error" in stocks[0]:
            print(f"Error: {stocks[0]['error']}")
            sys.exit(1)

        print(f"Batch analyzing {len(stocks)} stocks...")
        agent = create_orchestrator(profile=args.profile)
        stock_list = ", ".join(f"{s['ticker']} ({s['exchange']})" for s in stocks)
        response = agent(
            f"Analyze these stocks: {stock_list}. "
            f"Use up to {profile.news_queries} news search queries per stock. "
            f"Provide individual analysis for each, then a summary comparison.\n\n"
            f"{profile.prompt_instructions}"
        )
        print(str(response))
    else:
        ticker_input = args.ticker
        if args.exchange:
            exchange = args.exchange.upper()
        else:
            exchange = detect_exchange(ticker_input).value

        display = get_display_ticker(ticker_input)
        print(f"Analyzing {display} on {exchange}...")

        agent = create_orchestrator(profile=args.profile)
        response = agent(
            f"Analyze the stock {display} on {exchange} exchange. "
            f"Use up to {profile.news_queries} news search queries.\n\n"
            f"{profile.prompt_instructions}"
        )
        print(str(response))


if __name__ == "__main__":
    main()
