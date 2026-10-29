
import json
import re
import requests

from collections import defaultdict
from difflib import SequenceMatcher

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

KALSHI_BASE_URL = (
    "https://api.elections.kalshi.com/trade-api/v2"
)
POLYMARKET_GAMMA_URL = (
    "https://gamma-api.polymarket.com/markets"
)

HEADERS = {
    "User-Agent": "ArbFinder/1.0",
    "Accept": "application/json",
}

# Limits for initial testing. Increase after validating results.
KALSHI_PAGE_SIZE = 1000
KALSHI_MAX_PAGES = 10
POLYMARKET_PAGE_SIZE = 100
POLYMARKET_MAX_PAGES = 10

SIMILARITY_THRESHOLD = 0.70
MIN_SHARED_WORDS = 2
MAX_OPPORTUNITIES = 100

SPORTS_KEYWORDS = [
    "nba", "wnba", "nfl", "nhl", "mlb", "ncaa",
    "ufc", "mma", "atp", "wta", "pga", "f1",
    "formula 1", "premier league", "champions league",
    "la liga", "mls", "epl", "ncaaf", "ncaab",
    "basketball", "football", "baseball", "hockey",
    "soccer", "tennis", "golf", "boxing", "cricket",
    "rugby", "volleyball", "nascar", "motogp",
    "super bowl", "playoffs", "world series",
    "stanley cup", "world cup", "grand slam",
    "touchdown", "quarterback", "home run",
    "point spread", "moneyline", "over under",
    " vs ", " versus ",
]

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were",
    "will", "would", "could", "should", "be", "been",
    "before", "after", "by", "in", "on", "at", "to",
    "of", "for", "and", "or", "with", "from", "this",
    "that", "it", "do", "does", "did", "win", "wins",
    "who", "what", "which", "against",
}


def to_float(value):
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_list(value):
    """Parse a list returned either as JSON text or an actual list."""
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


def valid_price(price):
    return price is not None and 0 <= price <= 1


def kalshi_price(market, dollar_field, cents_field):
    """Prefer dollar prices, falling back to legacy cents fields."""
    dollar_value = to_float(market.get(dollar_field))

    if dollar_value is not None:
        return dollar_value

    cents_value = to_float(market.get(cents_field))

    if cents_value is not None:
        return cents_value / 100

    return None


def normalize_question(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def question_words(text):
    return {
        word
        for word in normalize_question(text).split()
        if word not in STOP_WORDS and len(word) > 1
    }


def is_sports_market(question):
    """
    Starter sports filter based on keywords.
    This can miss markets that mention only team names.
    """
    text = normalize_question(question)

    for keyword in SPORTS_KEYWORDS:
        normalized_keyword = normalize_question(keyword)

        if not normalized_keyword:
            continue

        if normalized_keyword in {"vs", "versus"}:
            if re.search(
                r"\b(vs|versus)\b",
                text,
            ):
                return True
        elif re.search(
            r"\b" + re.escape(normalized_keyword) + r"\b",
            text,
        ):
            return True

    return False


def question_similarity(question_a, question_b):
    a = normalize_question(question_a)
    b = normalize_question(question_b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def fetch_kalshi_markets():
    """Fetch open Kalshi markets, then keep likely sports markets."""
    all_markets = []
    cursor = None

    with requests.Session() as session:
        for _ in range(KALSHI_MAX_PAGES):
            params = {
                "limit": KALSHI_PAGE_SIZE,
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

        if ticker.startswith("KXMVECROSSCATEGORY"):
            continue

        if event_ticker.startswith("KXMVECROSSCATEGORY"):
            continue

        title = (
            market.get("title")
            or market.get("subtitle")
            or ticker
        )

        # Keep likely sports markets only.
        if not is_sports_market(title):
            continue

        results.append({
            "ticker": ticker,
            "event_ticker": event_ticker,
            "event": title,
            "yes_ask": kalshi_price(
                market, "yes_ask_dollars", "yes_ask"
            ),
            "no_ask": kalshi_price(
                market, "no_ask_dollars", "no_ask"
            ),
            "yes_bid": kalshi_price(
                market, "yes_bid_dollars", "yes_bid"
            ),
            "no_bid": kalshi_price(
                market, "no_bid_dollars", "no_bid"
            ),
            "last_price": kalshi_price(
                market, "last_price_dollars", "last_price"
            ),
            "status": market.get("status", "unknown"),
            "source": "Kalshi",
        })

    return len(all_markets), results


def fetch_polymarket_markets():
    """
    Fetch active Polymarket markets and retain likely sports markets.
    Gamma outcome prices are indicative and may not be executable.
    """
    all_markets = []

    with requests.Session() as session:
        for page in range(POLYMARKET_MAX_PAGES):
            params = {
                "active": "true",
                "closed": "false",
                "limit": POLYMARKET_PAGE_SIZE,
                "offset": page * POLYMARKET_PAGE_SIZE,
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

            if len(data) < POLYMARKET_PAGE_SIZE:
                break

    results = []

    for market in all_markets:
        question = market.get("question", "")

        if not is_sports_market(question):
            continue

        outcomes = parse_list(market.get("outcomes"))
        prices = parse_list(market.get("outcomePrices"))
        token_ids = parse_list(market.get("clobTokenIds"))

        # Preserve every outcome, not just Yes/No.
        outcome_details = []

        for index, outcome in enumerate(outcomes):
            price = (
                to_float(prices[index])
                if index < len(prices)
                else None
            )

            token_id = (
                token_ids[index]
                if index < len(token_ids)
                else None
            )

            outcome_details.append({
                "name": str(outcome),
                "price": price,
                "token_id": token_id,
            })

        yes_price = None
        no_price = None

        for detail in outcome_details:
            name = detail["name"].strip().lower()

            if name == "yes":
                yes_price = detail["price"]
            elif name == "no":
                no_price = detail["price"]

        results.append({
            "id": market.get("id"),
            "condition_id": market.get("conditionId"),
            "event": question,
            "slug": market.get("slug", ""),
            "outcomes": outcomes,
            "outcome_details": outcome_details,
            "yes_price": yes_price,
            "no_price": no_price,
            "active": market.get("active"),
            "source": "Polymarket",
        })

    return len(all_markets), results


def find_potential_arbitrage(kalshi_markets, polymarket_markets):
    """
    Find textually similar sports questions.

    Only calculate a price comparison when the Polymarket market
    explicitly has Yes/No outcomes. Team-based outcome matching
    needs additional event and outcome normalization.
    """
    opportunities = []
    comparisons = 0
    candidate_pairs = 0

    poly_index = defaultdict(set)
    poly_words = {}

    for index, market in enumerate(polymarket_markets):
        words = question_words(market.get("event", ""))
        poly_words[index] = words

        for word in words:
            poly_index[word].add(index)

    for kalshi in kalshi_markets:
        k_words = question_words(kalshi.get("event", ""))

        if not k_words:
            continue

        candidates = set()

        for word in k_words:
            candidates.update(poly_index.get(word, set()))

        for index in candidates:
            poly = polymarket_markets[index]
            p_words = poly_words[index]

            if len(k_words.intersection(p_words)) < MIN_SHARED_WORDS:
                continue

            comparisons += 1

            similarity = question_similarity(
                kalshi.get("event", ""),
                poly.get("event", ""),
            )

            if similarity < SIMILARITY_THRESHOLD:
                continue

            candidate_pairs += 1

            k_yes = kalshi.get("yes_ask")
            k_no = kalshi.get("no_ask")
            p_yes = poly.get("yes_price")
            p_no = poly.get("no_price")

            # Strategy 1: buy YES on Kalshi and NO on Polymarket.
            if valid_price(k_yes) and valid_price(p_no):
                total_cost = k_yes + p_no

                if total_cost < 1:
                    opportunities.append({
                        "kalshi_event": kalshi["event"],
                        "polymarket_event": poly["event"],
                        "kalshi_ticker": kalshi["ticker"],
                        "polymarket_slug": poly["slug"],
                        "strategy": (
                            "Buy YES on Kalshi + "
                            "NO on Polymarket"
                        ),
                        "kalshi_price": k_yes,
                        "polymarket_price": p_no,
                        "total_cost": round(total_cost, 4),
                        "potential_profit_per_contract": round(
                            1 - total_cost, 4
                        ),
                        "similarity": round(similarity, 4),
                        "status": "Unverified potential opportunity",
                    })

            # Strategy 2: buy NO on Kalshi and YES on Polymarket.
            if valid_price(k_no) and valid_price(p_yes):
                total_cost = k_no + p_yes

                if total_cost < 1:
                    opportunities.append({
                        "kalshi_event": kalshi["event"],
                        "polymarket_event": poly["event"],
                        "kalshi_ticker": kalshi["ticker"],
                        "polymarket_slug": poly["slug"],
                        "strategy": (
                            "Buy NO on Kalshi + "
                            "YES on Polymarket"
                        ),
                        "kalshi_price": k_no,
                        "polymarket_price": p_yes,
                        "total_cost": round(total_cost, 4),
                        "potential_profit_per_contract": round(
                            1 - total_cost, 4
                        ),
                        "similarity": round(similarity, 4),
                        "status": "Unverified potential opportunity",
                    })

    opportunities.sort(
        key=lambda item: item["potential_profit_per_contract"],
        reverse=True,
    )

    return (
        opportunities[:MAX_OPPORTUNITIES],
        comparisons,
        candidate_pairs,
    )


@app.get("/")
def home():
    return {
        "message": "ArbFinder API is running",
        "endpoints": ["/api/opportunities"],
        "mode": "Read-only; no trading functionality",
    }


@app.get("/api/opportunities")
def get_opportunities():
    kalshi_raw_count = 0
    kalshi_markets = []
    polymarket_raw_count = 0
    polymarket_markets = []
    errors = {}

    try:
        kalshi_raw_count, kalshi_markets = fetch_kalshi_markets()
    except (requests.RequestException, ValueError, TypeError) as error:
        errors["kalshi"] = str(error)

    try:
        (
            polymarket_raw_count,
            polymarket_markets,
        ) = fetch_polymarket_markets()
    except (requests.RequestException, ValueError, TypeError) as error:
        errors["polymarket"] = str(error)

    (
        opportunities,
        comparisons,
        candidate_pairs,
    ) = find_potential_arbitrage(
        kalshi_markets,
        polymarket_markets,
    )

    return {
        "source": "Kalshi + Polymarket",
        "market_category": "Sports",
        "raw_kalshi_count": kalshi_raw_count,
        "kalshi_count": len(kalshi_markets),
        "polymarket_raw_count": polymarket_raw_count,
        "polymarket_count": len(polymarket_markets),
        "opportunity_count": len(opportunities),
        "opportunities": opportunities,
        "matching_stats": {
            "comparisons": comparisons,
            "candidate_pairs": candidate_pairs,
            "similarity_threshold": SIMILARITY_THRESHOLD,
        },
        "errors": errors,
        "markets": kalshi_markets,
        "polymarket_markets": polymarket_markets,
        "note": (
            "Sports filtering and question matching are preliminary. "
            "Text similarity does not prove two contracts are equivalent. "
            "This version calculates price comparisons only for markets "
            "with explicit Yes/No outcomes. Team-based outcome matching, "
            "settlement rules, executable order-book prices, fees, and "
            "liquidity must be validated before treating a result as "
            "real arbitrage. This API does not place trades."
        ),
    }
