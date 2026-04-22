import os
from dotenv import load_dotenv
from alpaca_trade_api.rest import REST, TimeFrame, APIError

load_dotenv("/Users/s1961590/Downloads/25-26 Compsci/SportsBot/.env")

API_KEY = os.getenv("APCA_API_KEY_ID")
API_SECRET = os.getenv("APCA_API_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"

print("DEBUG KEY:", API_KEY)
print("DEBUG SECRET:", API_SECRET)

if API_KEY is None or API_SECRET is None:
    print("ERROR: .env file NOT LOADING. Check path or variable names.")
    exit()

api = REST(API_KEY, API_SECRET, BASE_URL)



class BSTNode:
    def __init__(self, score, symbol):
        self.score = score
        self.symbol = symbol
        self.left = None
        self.right = None

def insert_bst(root, score, symbol):
    if root is None:
        return BSTNode(score, symbol)
    if score < root.score:
        root.left = insert_bst(root.left, score, symbol)
    else:
        root.right = insert_bst(root.right, score, symbol)
    return root

def find_min(root):
    while root.left is not None:
        root = root.left
    return root.symbol

def find_max(root):
    while root.right is not None:
        root = root.right
    return root.symbol


MAX_SHARES = 100
COOLDOWN_LIMIT = 3

def get_latest_price(symbol):
    try:
        bars = api.get_bars(symbol, TimeFrame.Hour, limit=1)
        if len(bars) == 0:
            print(f"NO DATA for {symbol} — skipping.")
            return None
        return float(bars[0].c)
    except Exception as e:
        print(f"ERROR fetching {symbol}: {e}")
        return None

def std_dev(values):
    avg = sum(values) / len(values)
    variance = sum((v - avg)**2 for v in values) / len(values)
    return variance ** 0.5


def get_position_qty(symbol):
    try:
        pos = api.get_position(symbol)
        return float(pos.qty)
    except APIError as e:
        if "position does not exist" in str(e).lower():
            return 0.0
        print(f"Error getting position for {symbol}: {e}")
        return 0.0
    except Exception as e:
        print(f"Unexpected error getting position for {symbol}: {e}")
        return 0.0

def place_buy_order(symbol, qty):
    try:
        print(f"PLACING BUY ORDER: {symbol} x {qty}")
        api.submit_order(
            symbol=symbol,
            qty=qty,
            side="buy",
            type="market",
            time_in_force="day"
        )
    except Exception as e:
        print(f"Error placing BUY for {symbol}: {e}")

def place_sell_order(symbol):
    qty = get_position_qty(symbol)
    if qty <= 0:
        print(f"No position to sell for {symbol}")
        return
    try:
        print(f"PLACING SELL ORDER: {symbol} x {qty}")
        api.submit_order(
            symbol=symbol,
            qty=qty,
            side="sell",
            type="market",
            time_in_force="day"
        )
    except Exception as e:
        print(f"Error placing SELL for {symbol}: {e}")



def load_initial_history(watchlist, price_history):
    print("\n--- Loading initial historical data (1-hour bars) ---")
    for stock in watchlist:
        try:
            bars = api.get_bars(
                stock,
                TimeFrame.Hour,
                limit=50,
                adjustment='raw'
            )

            prices = [float(b.c) for b in bars]

            if len(prices) < 5:
                print(f"Not enough hourly history for {stock} ({len(prices)} bars) — skipping.")
                continue

            price_history[stock] = prices
            print(f"Loaded {len(prices)} hourly bars for {stock}")

        except Exception as e:
            print(f"Error loading history for {stock}: {e}")


def run_trading_bot(watchlist, price_history, portfolio, cooldown):

    print("\n--- Running Trading Bot ---")

    # Fetch latest hourly price
    for stock in watchlist:
        new_price = get_latest_price(stock)
        if new_price is None:
            continue
        price_history[stock].append(new_price)

        # Keep last 200 hours
        if len(price_history[stock]) > 200:
            price_history[stock] = price_history[stock][-200:]

    scores = {}

    # Compute indicators
    for stock in watchlist:
        prices = price_history[stock]

        if len(prices) < 5:
            continue

        shortMA = sum(prices[-3:]) / 3
        longMA = sum(prices[-5:]) / 5
        volatility = std_dev(prices)

        gains = []
        losses = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            if diff > 0:
                gains.append(diff)
            else:
                losses.append(abs(diff))

        if len(gains) == 0: gains = [0]
        if len(losses) == 0: losses = [0]

        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)

        RSI = 100 - (100 / (1 + (avg_gain / avg_loss)))

        score = (shortMA - longMA) - volatility + (50 - abs(RSI - 50))
        scores[stock] = score

    # Build BST
    bst_root = None
    for stock, score in scores.items():
        bst_root = insert_bst(bst_root, score, stock)

    if bst_root is None:
        print("Not enough data yet to score stocks.")
        return

    best_stock = find_max(bst_root)
    worst_stock = find_min(bst_root)

    trade_made = False

    # Sync portfolio dict with real Alpaca positions
    for stock in watchlist:
        portfolio[stock] = get_position_qty(stock)

    # ---------------- BUY RULE (with real order) ----------------
    # Threshold tuned for 5-bar data
    if portfolio[best_stock] == 0 and scores[best_stock] > -1 and cooldown[best_stock] >= COOLDOWN_LIMIT:
        print("SIGNAL: BUY", best_stock)
        place_buy_order(best_stock, MAX_SHARES)
        portfolio[best_stock] = MAX_SHARES
        cooldown[best_stock] = 0
        trade_made = True

    # ---------------- SELL RULE (with real order) ---------------
    if portfolio[worst_stock] > 0 and scores[worst_stock] < -1 and cooldown[worst_stock] >= COOLDOWN_LIMIT:
        print("SIGNAL: SELL", worst_stock)
        place_sell_order(worst_stock)
        portfolio[worst_stock] = 0
        cooldown[worst_stock] = 0
        trade_made = True

    if not trade_made:
        print("HOLD")

    # Update cooldowns
    for stock in watchlist:
        cooldown[stock] += 1

    print("Run complete.")
    print("Scores:", scores)
    print("Portfolio (sim):", portfolio)


watchlist = [
    "EA", "TTWO", "SONY", "MSFT", "NVDA", "AMD", "INTC", "LOGI", "CRSR",
    "NTES", "BILI", "HUYA", "DOYU", "U", "RBLX", "IMMR", "GREE", "SE", "META"
]



price_history = {s: [] for s in watchlist}
portfolio = {s: 0 for s in watchlist}
cooldown = {s: 999 for s in watchlist}


load_initial_history(watchlist, price_history)
run_trading_bot(watchlist, price_history, portfolio, cooldown)
