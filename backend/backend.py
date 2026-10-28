
import json
import requests

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="ArbFinder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com/markets"

HEADERS = {
    "User-Agent": "ArbFinder/1.0",
    "Accept": "application/json",
}


def to_float(value):
    """Convert a price to a float, or return None if invalid."""
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_list(value):
    """Handle API fields that may be JSON strings or actual lists."""
    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    return []


def kalshi_price(market, dollar_field, cents_field):
    """
    Prefer Kalshi's dollar-denominated field.
    Fall back to the legacy integer cents field.
    """
    dollar_value = to_float(market.get(dollar_field))

    if dollar_value is not None:
        return dollar_value

    cents_value = to_float(market.get(cents_field))

    if cents_value is not None:
        return cents_value / 100

    return None


def fetch_kalshi_markets():
    """Fetch open Kalshi markets using pagination."""
    all_markets = []
    cursor = None
    page_size = 1000
    max_pages = 10

    with requests.Session() as session:
        for _ in range(max_pages):
            params = {
                "limit": page_size,
                "status": "open",
                "mve_filter": "exclude",
            }

            if cursor:
                params["cursor"] = cursor

            response = session.get(
                f"{KALSHI_BASE_URL}/markets",
                params=params,
                headers=HEADERS,
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()

            page_markets = payload.get("markets", [])
            all_markets.extend(page_markets)

            cursor = payload.get("cursor")

            if not cursor or not page_markets:
                break

    results = []

    for market in all_markets:
        ticker = market.get("ticker", "")
        event_ticker = market.get("event_ticker", "")

        # Exclude cross-category combo markets.
        if ticker.startswith("KXMVECROSSCATEGORY"):
            continue

        if event_ticker.startswith("KXMVECROSSCATEGORY"):
            continue

        yes_ask = kalshi_price(
            market, "yes_ask_dollars", "yes_ask"
        )
        no_ask = kalshi_price(
            market, "no_ask_dollars", "no_ask"
        )
        yes_bid = kalshi_price(
            market, "yes_bid_dollars", "yes_bid"
        )
        no_bid = kalshi_price(
            market, "no_bid_dollars", "no_bid"
        )
        last_price = kalshi_price(
            market, "last_price_dollars", "last_price"
        )

        results.append({
            "ticker": ticker,
            "event_ticker": event_ticker,
            "event": (
                market.get("title")
                or market.get("subtitle")
                or ticker
            ),
            "yes_ask": yes_ask,
            "no_ask": no_ask,
            "yes_bid": yes_bid,
            "no_bid": no_bid,
            "last_price": last_price,
            "status": market.get("status", "unknown"),
            "source": "Kalshi",
        })

    return len(all_markets), results


def fetch_polymarket_markets():
    """
    Fetch active Polymarket markets.

    Request 100 markets per page and fetch at most five pages.
    Prices from this endpoint are indicative, not guaranteed
    executable prices from the order book.
    """
    all_markets = []
    page_size = 100
    max_pages = 5

    with requests.Session() as session:
        for page in range(max_pages):
            params = {
                "active": "true",
                "closed": "false",
                "limit": page_size,
                "offset": page * page_size,
                "order": "volumeNum",
                "ascending": "false",
            }

            response = session.get(
                POLYMARKET_GAMMA_URL,
                params=params,
                headers=HEADERS,
                timeout=20,
            )
            response.raise_for_status()

            data = response.json()

            if not isinstance(data, list) or not data:
                break

            all_markets.extend(data)

            if len(data) < page_size:
                break

    results = []

    for market in all_markets:
        outcomes = parse_list(market.get("outcomes"))
        prices = parse_list(market.get("outcomePrices"))
        token_ids = parse_list(market.get("clobTokenIds"))

        yes_index = None
        no_index = None

        for index, outcome in enumerate(outcomes):
            outcome_name = str(outcome).strip().lower()

            if outcome_name == "yes":
                yes_index = index
            elif outcome_name == "no":
                no_index = index

        yes_price = None
        no_price = None
        yes_token_id = None
        no_token_id = None

        if yes_index is not None and yes_index < len(prices):
            yes_price = to_float(prices[yes_index])

        if no_index is not None and no_index < len(prices):
            no_price = to_float(prices[no_index])

        if yes_index is not None and yes_index < len(token_ids):
            yes_token_id = token_ids[yes_index]

        if no_index is not None and no_index < len(token_ids):
            no_token_id = token_ids[no_index]

        results.append({
            "id": market.get("id"),
            "condition_id": market.get("conditionId"),
            "event": market.get("question", ""),
            "slug": market.get("slug", ""),
            "outcomes": outcomes,
            "yes_price": yes_price,
            "no_price": no_price,
            "yes_token_id": yes_token_id,
            "no_token_id": no_token_id,
            "active": market.get("active"),
            "source": "Polymarket",
        })

    return len(all_markets), results


@app.get("/")
def home():
    return {
        "message": "ArbFinder API is running",
        "endpoints": [
            "/api/opportunities",
        ],
    }


@app.get("/api/opportunities")
def get_opportunities():
    """Return market data from both platforms."""

    kalshi_raw_count = 0
    kalshi_markets = []
    polymarket_raw_count = 0
    polymarket_markets = []
    errors = {}

    try:
        kalshi_raw_count, kalshi_markets = fetch_kalshi_markets()
    except requests.RequestException as error:
        errors["kalshi"] = str(error)

    try:
        (
            polymarket_raw_count,
            polymarket_markets,
        ) = fetch_polymarket_markets()
    except (requests.RequestException, ValueError) as error:
        errors["polymarket"] = str(error)

    # This endpoint currently gathers market data.
    # It does not yet certify arbitrage opportunities.
    return {
        "source": "Kalshi + Polymarket",
        "raw_kalshi_count": kalshi_raw_count,
        "kalshi_count": len(kalshi_markets),
        "polymarket_raw_count": polymarket_raw_count,
        "polymarket_count": len(polymarket_markets),
        "errors": errors,
        "markets": kalshi_markets,
        "polymarket_markets": polymarket_markets,
        "note": (
            "Market listings are not guaranteed executable prices. "
            "Order books, contract equivalence, fees, and liquidity "
            "must be checked before identifying real arbitrage."
        ),
    }
