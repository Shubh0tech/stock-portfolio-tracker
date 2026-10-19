# Stock Portfolio Tracker (Task 2 — Advanced Edition)

Eye-catching stock tracker in **Python (Tkinter)** plus a matching **web version**.
Calculates total investment from manually defined stock prices, tracks cost basis
and profit/loss, draws an allocation donut chart, can fetch live prices, and
exports reports to `.txt` / `.csv`. Standard library only — no pip installs.

## Run

```
py stock_portfolio_tracker.py          # GUI (dark neon desktop app)
py stock_portfolio_tracker.py --cli    # terminal version (input()/print())
```

Web version: open `docs/index.html` in a browser, or visit the live GitHub Pages site.

## Features

- **Dictionary** — `STOCK_PRICES = {"AAPL": 180, "TSLA": 250, ...}` hardcodes prices;
  holdings live in a second dictionary with quantity + average cost.
- **Input / Output** — GUI form, clickable price board, or the CLI menu.
- **Basic arithmetic** — price × quantity, weighted-average cost, profit/loss,
  percentage share of portfolio.
- **File handling** — export `.txt` (formatted report) and `.csv` (Excel-ready);
  the portfolio auto-saves to `portfolio.json` after every change.
- **Advanced extras**
  - Cost basis + unrealized **Profit/Loss** per stock and overall (green/red rows)
  - **Sell** dialog with realized-gain tracking
  - **Live prices** button — Yahoo Finance (no API key), offline-safe fallback
  - **Donut allocation chart** with legend (Tkinter canvas / HTML canvas)
  - Auto-save / auto-load persistence
  - Animated clock, hover-glow buttons, status messages, input validation

## Project layout

```
stock_portfolio_tracker.py   # Python app (GUI + CLI)
docs/index.html              # web version (GitHub Pages)
portfolio.json               # auto-saved portfolio (local only)
```

## Web version tested

Buy/sell flows, P/L math, donut chart, localStorage persistence, and
.csv/.txt export were verified in a real browser.
