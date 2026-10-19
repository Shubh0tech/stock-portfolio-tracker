"""
=============================================================================
 STOCK PORTFOLIO TRACKER  (Task 2 - Advanced Edition)
=============================================================================
 Goal: Build a simple stock tracker that calculates total investment based
       on manually defined stock prices.

 Key Concepts Used:
   * dictionary          -> STOCK_PRICES + the user's portfolio dict
   * input / output      -> GUI form (or:  py stock_portfolio_tracker.py --cli)
   * basic arithmetic    -> price * quantity, cost basis, profit & loss
   * file handling       -> .csv / .txt export + portfolio.json auto-save

 Advanced Features:
   * Cost basis + unrealized Profit/Loss per stock and overall (green/red)
   * Sell with realized gain tracking
   * Live price refresh (Stooq CSV via stdlib urllib, offline-safe fallback)
   * Donut allocation chart drawn on a Tkinter canvas
   * Auto-save / auto-load portfolio (portfolio.json)
   * Dark neon eye-catching UI, hover buttons, animated totals

 Run GUI:     py stock_portfolio_tracker.py
 Run CLI:     py stock_portfolio_tracker.py --cli
 Web version: docs/index.html  (open in a browser or GitHub Pages)
=============================================================================
"""

import csv
import json
import os
import sys
import datetime as dt
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from tkinter import (
    Tk, Toplevel, Frame, Label, Entry, Button, Canvas, StringVar,
    messagebox, filedialog, BOTH, END, W, E, X, Y, LEFT, RIGHT,
    TOP, BOTTOM, FLAT,
)
from tkinter import ttk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(APP_DIR, "portfolio.json")

# ---------------------------------------------------------------------------
# 1. HARCODED PRICE DICTIONARY  (key concept: dictionary)
# ---------------------------------------------------------------------------
STOCK_PRICES = {
    "AAPL": 180, "TSLA": 250, "MSFT": 420, "GOOGL": 175, "AMZN": 190,
    "NVDA": 130, "META": 560, "NFLX": 700, "INFY": 1900, "RELIANCE": 2950,
}

# Yahoo Finance ticker mapping for live prices (no API key needed)
YAHOO_SYMBOLS = {
    "AAPL": "AAPL", "TSLA": "TSLA", "MSFT": "MSFT",
    "GOOGL": "GOOGL", "AMZN": "AMZN", "NVDA": "NVDA",
    "META": "META", "NFLX": "NFLX", "INFY": "INFY.NS",
    "RELIANCE": "RELIANCE.NS",
}

# ---------------------------- theme colours -------------------------------
BG, PANEL, PANEL_2, LINE = "#0B0E1A", "#141A2E", "#1C2440", "#2A3357"
TEXT, DIM = "#EDF1FF", "#8A94B8"
GREEN, CYAN, BLUE = "#00E5A0", "#22D3EE", "#4DA3FF"
PURPLE, YELLOW, RED = "#A78BFA", "#FFB84D", "#FF4D6D"
PINK = "#FF5C7A"
UP_BG, DOWN_BG = "#0E2A21", "#2A1220"
HOLDING_COLORS = [GREEN, BLUE, PURPLE, YELLOW, "#FF5C7A", CYAN,
                  "#F472B6", "#34D399"]

# ===========================================================================
#  CORE LOGIC  (shared by GUI and CLI)
# ===========================================================================
def holding_value(symbol, qty, prices):
    """basic arithmetic: value of one holding."""
    return prices.get(symbol.upper(), 0) * qty


def total_value(portfolio, prices):
    return sum(holding_value(s, d["qty"], prices)
               for s, d in portfolio.items())


def total_cost(portfolio):
    return sum(d["qty"] * d["avg"] for d in portfolio.values())


def total_pnl(portfolio, prices):
    return total_value(portfolio, prices) - total_cost(portfolio)


def buy(portfolio, symbol, qty, cost):
    """Add shares; recompute average cost (weighted mean)."""
    sym = symbol.upper()
    if sym in portfolio:
        old = portfolio[sym]
        new_qty = old["qty"] + qty
        old["avg"] = (old["qty"] * old["avg"] + qty * cost) / new_qty
        old["qty"] = new_qty
    else:
        portfolio[sym] = {"qty": qty, "avg": float(cost)}
    return portfolio


def sell(portfolio, symbol, qty, price):
    """Remove shares; return realized profit/loss."""
    sym = symbol.upper()
    hold = portfolio[sym]
    realized = (price - hold["avg"]) * qty
    hold["qty"] -= qty
    if hold["qty"] <= 1e-9:
        del portfolio[sym]
    return realized


def _fetch_one(sym, timeout):
    """Yahoo chart API -> latest price for one ticker."""
    ticker = YAHOO_SYMBOLS[sym]
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{ticker}?interval=1d&range=1d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    price = float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
    return sym, price


def fetch_live_prices(timeout=6):
    """stdlib urllib -> Yahoo Finance close prices (parallel).
    Returns {} when offline / blocked so callers can fall back."""
    found = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_fetch_one, s, timeout)
                   for s in STOCK_PRICES if s in YAHOO_SYMBOLS]
        for fut in futures:
            try:
                sym, price = fut.result()
            except Exception:
                continue
            if price > 0:
                found[sym] = price
    return found


# ---------------------- persistence (portfolio.json) ----------------------
def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            data = json.load(f)
        pf = {s.upper(): {"qty": float(d["qty"]), "avg": float(d["avg"])}
              for s, d in data.get("portfolio", {}).items() if d.get("qty", 0) > 0}
        return pf, float(data.get("realized", 0))
    except (OSError, ValueError, KeyError, TypeError):
        return {}, 0.0


def persist(portfolio, realized):
    """file handling: auto-save after every change."""
    try:
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump({"portfolio": portfolio, "realized": realized,
                       "saved": dt.datetime.now().isoformat()},
                      f, indent=2)
    except OSError:
        pass


# --------------------------- export txt / csv -----------------------------
def save_to_file(portfolio, prices, path, kind="txt", realized=0.0):
    total = total_value(portfolio, prices)
    cost = total_cost(portfolio)
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = sorted(portfolio.items(),
                  key=lambda kv: -holding_value(kv[0], kv[1]["qty"], prices))

    if kind.lower() == "csv":
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Stock", "Price", "AvgCost", "Quantity",
                        "Value", "Invested", "ProfitLoss"])
            for sym, d in rows:
                val = holding_value(sym, d["qty"], prices)
                inv = d["qty"] * d["avg"]
                w.writerow([sym, prices.get(sym, 0), f"{d['avg']:.2f}",
                            d["qty"], f"{val:.2f}", f"{inv:.2f}",
                            f"{val - inv:.2f}"])
            w.writerow(["TOTAL", "", "", sum(d["qty"] for _, d in rows),
                        f"{total:.2f}", f"{cost:.2f}", f"{total - cost:.2f}"])
    else:
        lines = [
            "=" * 74,
            "            STOCK PORTFOLIO - INVESTMENT REPORT",
            "=" * 74,
            f"Generated : {generated}",
            f"{'Stock':<10}{'Price':>10}{'AvgCost':>10}{'Qty':>7}"
            f"{'Value':>12}{'Invested':>12}{'P/L':>12}",
            "-" * 74,
        ]
        for sym, d in rows:
            val = holding_value(sym, d["qty"], prices)
            inv = d["qty"] * d["avg"]
            lines.append(f"{sym:<10}{prices.get(sym, 0):>10.2f}"
                         f"{d['avg']:>10.2f}{d['qty']:>7g}"
                         f"{val:>12.2f}{inv:>12.2f}{val - inv:>12.2f}")
        lines.append("-" * 74)
        lines.append(f"{'TOTAL':<49}{total:>12.2f}{cost:>12.2f}"
                     f"{total - cost:>12.2f}")
        lines.append(f"Realized P/L so far: {realized:.2f}")
        lines.append("=" * 74)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return total


# ===========================================================================
#  GRAPHICAL INTERFACE  (eye-catching UI)
# ===========================================================================
class PortfolioApp:
    def __init__(self, root: Tk):
        self.root = root
        self.portfolio, self.realized = load_portfolio()
        self.prices = dict(STOCK_PRICES)
        self._live_busy = False

        root.title("Stock Portfolio Tracker - Advanced")
        root.geometry("1150x740")
        root.minsize(980, 660)
        root.configure(bg=BG)

        body = Frame(root, bg=BG)
        body.pack(fill=BOTH, expand=True, padx=20, pady=(0, 12))

        self._build_styles()
        self._build_header(body)
        self._build_input_panel(body)
        right = Frame(body, bg=BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)
        self._build_dashboard(right)
        self._build_table(right)
        self._build_footer(right)
        self.refresh()

    def _build_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", background=PANEL_2,
                        fieldbackground=PANEL_2, foreground=TEXT,
                        rowheight=30, borderwidth=0, font=("Consolas", 10))
        style.configure("Treeview.Heading", background=PANEL, foreground=CYAN,
                        borderwidth=0, font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#26315C")])

    def _build_header(self, body):
        head = Frame(body, bg=BG)
        head.pack(fill=X, pady=(0, 10))
        Label(head, text="\u25B2", font=("Segoe UI", 24, "bold"),
              fg=GREEN, bg=BG).pack(side=LEFT, padx=(2, 10))
        left = Frame(head, bg=BG)
        left.pack(side=LEFT)
        Label(left, text="STOCK PORTFOLIO TRACKER",
              font=("Segoe UI", 20, "bold"), fg=TEXT, bg=BG).pack(anchor=W)
        Label(left, text="cost basis \u2022 profit & loss \u2022 live prices \u2022 "
                         "donut chart \u2022 auto-save",
              font=("Segoe UI", 9), fg=DIM, bg=BG).pack(anchor=W)
        self.clock = Label(head, font=("Consolas", 10), fg=YELLOW, bg=BG)
        self.clock.pack(side=RIGHT)
        self._tick()

    def _tick(self):
        self.clock.config(text=dt.datetime.now().strftime("%d %b %Y  %H:%M:%S"))
        self.root.after(1000, self._tick)

    def _btn(self, parent, text, bg, fg, command):
        b = Button(parent, text=text, font=("Segoe UI", 10, "bold"), bg=bg,
                   fg=fg, activebackground=fg, activeforeground=bg,
                   relief=FLAT, cursor="hand2", pady=6, command=command)
        b.bind("<Enter>", lambda e: b.config(bg=fg, fg=bg))
        b.bind("<Leave>", lambda e: b.config(bg=bg, fg=fg))
        return b

    def _entry(self, parent, var, placeholder=""):
        return Entry(parent, textvariable=var, font=("Consolas", 12),
                     bg="#0E1326", fg=TEXT, insertbackground=GREEN,
                     relief=FLAT, highlightthickness=1,
                     highlightcolor=GREEN, highlightbackground=LINE)

    def _build_input_panel(self, body):
        panel = Frame(body, bg=PANEL, highlightbackground=LINE,
                      highlightthickness=1, width=330)
        panel.pack(side=LEFT, fill=Y, padx=(0, 16))
        panel.pack_propagate(False)

        Label(panel, text="\U0001F4C8  BUY / SELL", font=("Segoe UI", 13, "bold"),
              fg=GREEN, bg=PANEL, anchor=W).pack(fill=X, padx=16, pady=(14, 10))

        fields = [("STOCK SYMBOL", "sym", "e.g. AAPL"),
                  ("QUANTITY", "qty", "e.g. 5"),
                  ("BUY COST / SHARE (blank = price)", "cost", "optional")]
        for text, key, ph in fields:
            Label(panel, text=text, font=("Segoe UI", 8, "bold"), fg=DIM,
                  bg=PANEL).pack(anchor=W, padx=16)
            var = StringVar()
            setattr(self, key + "_var", var)
            e = self._entry(panel, var, ph)
            e.pack(fill=X, padx=16, pady=(3, 8))
            setattr(self, key + "_entry", e)

        self._btn(panel, "\u25B6  BUY", GREEN, "#06251B",
                  self.add_holding).pack(fill=X, padx=16, pady=(2, 6))
        self._btn(panel, "\u25C0  SELL", YELLOW, "#2A1B05",
                  self.sell_holding).pack(fill=X, padx=16, pady=(0, 6))
        self._btn(panel, "\u2716  REMOVE", PINK, "#2A0B14",
                  self.remove_holding).pack(fill=X, padx=16, pady=(0, 6))
        self._btn(panel, "\u2715  CLEAR ALL", DIM, PANEL,
                  self.clear_all).pack(fill=X, padx=16, pady=(0, 10))

        Label(panel, text="\U0001F4CA  PRICE BOARD  (click to fill)",
              font=("Segoe UI", 11, "bold"), fg=CYAN, bg=PANEL,
              anchor=W).pack(fill=X, padx=16, pady=(4, 6))
        board = Frame(panel, bg=PANEL)
        board.pack(fill=X, padx=12)
        for i, (sym, price) in enumerate(STOCK_PRICES.items()):
            chip = Frame(board, bg=PANEL_2, cursor="hand2")
            chip.grid(row=i // 2, column=i % 2, padx=4, pady=3, sticky="ew")
            chip.bind("<Button-1>", lambda e, s=sym: self._fill(s))
            chip.bind("<Enter>", lambda e, c=chip: c.config(bg="#243055"))
            chip.bind("<Leave>", lambda e, c=chip: c.config(bg=PANEL_2))
            lbl = Label(chip, text=sym, font=("Segoe UI", 9, "bold"),
                        fg=TEXT, bg=PANEL_2)
            lbl.pack(side=LEFT, padx=(8, 2), pady=4)
            pr = Label(chip, text=f"${price:,.0f}", font=("Consolas", 9),
                       fg=GREEN, bg=PANEL_2)
            pr.pack(side=RIGHT, padx=(2, 8), pady=4)
            for wdg in (lbl, pr):
                wdg.bind("<Button-1>", lambda e, s=sym: self._fill(s))
            setattr(self, f"chip_{sym}", pr)
        board.columnconfigure((0, 1), weight=1)

    def _fill(self, sym):
        self.sym_var.set(sym)
        self.qty_entry.focus_set()

    # =========================== ACTIONS ==================================
    def add_holding(self):
        sym = self.sym_var.get().strip().upper()
        qty_raw = self.qty_var.get().strip()
        cost_raw = self.cost_var.get().strip()

        if not sym:
            return self._flash("Enter a stock symbol first", RED)
        if sym not in self.prices:
            return self._flash(f"'{sym}' is not in the price dictionary", RED)
        try:
            qty = float(qty_raw)
            if qty <= 0:
                raise ValueError
        except ValueError:
            return self._flash("Quantity must be a positive number", RED)
        if cost_raw:
            try:
                cost = float(cost_raw)
                if cost <= 0:
                    raise ValueError
            except ValueError:
                return self._flash("Buy cost must be a positive number", RED)
        else:
            cost = self.prices[sym]

        buy(self.portfolio, sym, qty, cost)
        persist(self.portfolio, self.realized)
        self.sym_var.set("")
        self.qty_var.set("")
        self.cost_var.set("")
        self.sym_entry.focus_set()
        self._flash(f"Bought {qty:g} {sym} @ ${cost:,.2f} \u2022 "
                    f"value ${holding_value(sym, qty, self.prices):,.2f}", GREEN)
        self.refresh()

    def sell_holding(self):
        sel = self.tree.selection()
        if not sel:
            return self._flash("Select a holding in the table to sell", RED)
        sym = sel[0]
        hold = self.portfolio[sym]

        top = Toplevel(self.root, bg=PANEL)
        top.title(f"Sell {sym}")
        top.geometry("320x190")
        top.resizable(False, False)
        Label(top, text=f"SELL {sym}", font=("Segoe UI", 14, "bold"),
              fg=YELLOW, bg=PANEL).pack(pady=(14, 2))
        Label(top, text=f"You own {hold['qty']:g} shares "
                        f"(avg cost ${hold['avg']:,.2f})",
              font=("Segoe UI", 9), fg=DIM, bg=PANEL).pack()
        qty_var = StringVar()
        e = Entry(top, textvariable=qty_var, font=("Consolas", 13),
                  bg="#0E1326", fg=TEXT, insertbackground=YELLOW,
                  relief=FLAT, highlightthickness=1, highlightcolor=YELLOW,
                  highlightbackground=LINE)
        e.pack(padx=30, pady=12, fill=X)
        e.focus_set()

        def confirm():
            try:
                qty = float(qty_var.get())
                if qty <= 0 or qty > hold["qty"]:
                    raise ValueError
            except ValueError:
                return self._flash(f"Enter a quantity between 1 and "
                                   f"{hold['qty']:g}", RED)
            realized = sell(self.portfolio, sym, qty, self.prices.get(sym, 0))
            self.realized += realized
            persist(self.portfolio, self.realized)
            top.destroy()
            self._flash(f"Sold {qty:g} {sym} \u2022 realized "
                        f"${realized:+,.2f}", GREEN if realized >= 0 else RED)
            self.refresh()

        self._btn(top, "\u25C0  CONFIRM SELL", YELLOW, "#2A1B05",
                  confirm).pack(padx=30, fill=X)
        top.bind("<Return>", lambda e: confirm())

    def remove_holding(self):
        sel = self.tree.selection()
        if not sel:
            return self._flash("Select a row to remove", RED)
        sym = sel[0]
        del self.portfolio[sym]
        persist(self.portfolio, self.realized)
        self._flash(f"{sym} removed (no realized P/L)", YELLOW)
        self.refresh()

    def clear_all(self):
        if not self.portfolio:
            return self._flash("Portfolio is already empty", DIM)
        if messagebox.askyesno("Clear portfolio",
                               "Remove ALL holdings? (keeps realized P/L)"):
            self.portfolio.clear()
            persist(self.portfolio, self.realized)
            self._flash("Portfolio cleared", YELLOW)
            self.refresh()

    def save(self, kind):
        if not self.portfolio:
            return self._flash("Add at least one holding before saving", RED)
        ext = f".{kind}"
        path = filedialog.asksaveasfilename(
            defaultextension=ext, filetypes=[(f"{kind.upper()} file", f"*{ext}")],
            initialfile=f"portfolio{ext}")
        if not path:
            return
        try:
            total = save_to_file(self.portfolio, self.prices, path, kind,
                                 self.realized)
            self._flash(f"Saved \u2713  {os.path.basename(path)}  "
                        f"(${total:,.2f})", GREEN)
        except OSError as err:
            messagebox.showerror("Save failed", str(err))

    def _flash(self, msg, color):
        self.status.config(text=msg, fg=color)

    # ========================== DASHBOARD =================================
    def _build_dashboard(self, parent):
        dash = Frame(parent, bg=BG)
        dash.pack(fill=X, pady=(0, 10))

        card = Frame(dash, bg=PANEL, highlightbackground=LINE,
                     highlightthickness=1)
        card.pack(side=LEFT, fill=X, expand=True, padx=(0, 12))
        Label(card, text="TOTAL PORTFOLIO VALUE", font=("Segoe UI", 9, "bold"),
              fg=DIM, bg=PANEL).pack(anchor=W, padx=20, pady=(12, 0))
        self.total_lbl = Label(card, text="$0.00",
                               font=("Segoe UI", 34, "bold"), fg=GREEN,
                               bg=PANEL)
        self.total_lbl.pack(anchor=W, padx=20)
        self.pnl_lbl = Label(card, text="P/L $0.00 (0.0%)",
                             font=("Segoe UI", 12, "bold"), fg=DIM, bg=PANEL)
        self.pnl_lbl.pack(anchor=W, padx=20)
        self.sub_lbl = Label(card,
                             text="cost $0.00 \u2022 realized $0.00 \u2022 "
                                  "0 holdings",
                             font=("Segoe UI", 9), fg=CYAN, bg=PANEL)
        self.sub_lbl.pack(anchor=W, padx=20, pady=(2, 12))

        donut_box = Frame(dash, bg=PANEL, highlightbackground=LINE,
                          highlightthickness=1)
        donut_box.pack(side=LEFT, fill=Y)
        Label(donut_box, text="ALLOCATION", font=("Segoe UI", 9, "bold"),
              fg=DIM, bg=PANEL).pack(pady=(10, 0))
        row = Frame(donut_box, bg=PANEL)
        row.pack(pady=(0, 8))
        self.donut = Canvas(row, width=150, height=150, bg=PANEL,
                            highlightthickness=0)
        self.donut.pack(side=LEFT, padx=(10, 4))
        self.legend = Frame(row, bg=PANEL)
        self.legend.pack(side=LEFT, padx=(0, 10), fill=Y)

    # ============================ TABLE ===================================
    def _build_table(self, parent):
        wrap = Frame(parent, bg=PANEL, highlightbackground=LINE,
                     highlightthickness=1)
        wrap.pack(fill=BOTH, expand=True)
        cols = ("stock", "price", "avg", "qty", "value", "cost", "pnl", "share")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 selectmode="browse")
        heads = [("STOCK", W, 90), ("PRICE", E, 90), ("AVG COST", E, 90),
                 ("QTY", E, 70), ("VALUE", E, 100), ("INVESTED", E, 100),
                 ("P/L", E, 110), ("SHARE OF PORTFOLIO", E, 180)]
        for c, (txt, anchor, width) in zip(cols, heads):
            self.tree.heading(c, text=txt)
            self.tree.column(c, anchor=anchor, width=width,
                             stretch=(c == "share"))
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True, padx=(8, 0), pady=8)
        sb.pack(side=RIGHT, fill=Y, pady=8, padx=(0, 4))
        self.tree.tag_configure("up", background=UP_BG)
        self.tree.tag_configure("down", background=DOWN_BG)
        self.tree.tag_configure("even", background=PANEL_2)
        self.tree.tag_configure("odd", background="#171E38")

    def _build_footer(self, parent):
        foot = Frame(parent, bg=BG)
        foot.pack(fill=X, pady=(8, 0))
        self._btn(foot, "\U0001F504  LIVE PRICES", CYAN, "#072430",
                  self.refresh_live).pack(side=LEFT, padx=(0, 8))
        self._btn(foot, "\U0001F4BE  SAVE .TXT", BLUE, "#0A1B33",
                  lambda: self.save("txt")).pack(side=LEFT, padx=(0, 8))
        self._btn(foot, "\U0001F4E6  SAVE .CSV", YELLOW, "#2A1B05",
                  lambda: self.save("csv")).pack(side=LEFT, padx=(0, 8))
        self.status = Label(foot, text="Ready \u2022 portfolio auto-saved",
                            font=("Segoe UI", 10), fg=GREEN, bg=BG)
        self.status.pack(side=RIGHT)

    # ======================= LIVE PRICE FETCH =============================
    def refresh_live(self):
        if self._live_busy:
            return
        self._live_busy = True
        self._flash("Fetching live prices...", CYAN)
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            found = fetch_live_prices()
        except Exception:
            found = {}
        self.root.after(0, self._apply_live, found)

    def _apply_live(self, found):
        self._live_busy = False
        if found:
            self.prices.update(found)
            for sym in STOCK_PRICES:
                chip = getattr(self, f"chip_{sym}", None)
                if chip is not None:
                    chip.config(text=f"${self.prices[sym]:,.2f}")
            self._flash(f"Live prices updated ({len(found)} stocks)",
                        GREEN)
        else:
            self._flash("Offline \u2014 using manual/hardcoded prices", YELLOW)
        self.refresh()

    # =========================== RENDERING ================================
    def refresh(self):
        total = total_value(self.portfolio, self.prices)
        cost = total_cost(self.portfolio)
        pnl = total - cost
        pnl_pct = (pnl / cost * 100) if cost else 0.0
        sign = "+" if pnl >= 0 else ""
        self.total_lbl.config(text=f"${total:,.2f}")
        self.pnl_lbl.config(
            text=f"Profit/Loss  {sign}${pnl:,.2f}  ({sign}{pnl_pct:.2f}%)",
            fg=GREEN if pnl >= 0 else RED)
        qty_total = sum(d["qty"] for d in self.portfolio.values())
        self.sub_lbl.config(
            text=f"cost ${cost:,.2f} \u2022 realized ${self.realized:,.2f} "
                 f"\u2022 {len(self.portfolio)} holdings \u2022 "
                 f"{qty_total:g} shares")

        self.tree.delete(*self.tree.get_children())
        rows = sorted(self.portfolio.items(),
                      key=lambda kv: -holding_value(kv[0], kv[1]["qty"],
                                                    self.prices))
        for i, (sym, d) in enumerate(rows):
            val = holding_value(sym, d["qty"], self.prices)
            inv = d["qty"] * d["avg"]
            hpnl = val - inv
            share = (val / total * 100) if total else 0
            bar = "\u2588" * max(1, int(round(share / 4))) if share else ""
            if hpnl >= 0.005:
                tag = "up"
            elif hpnl <= -0.005:
                tag = "down"
            else:
                tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", END, iid=sym, tags=(tag,),
                             values=(sym, f"{self.prices.get(sym, 0):,.2f}",
                                     f"{d['avg']:,.2f}", f"{d['qty']:g}",
                                     f"{val:,.2f}", f"{inv:,.2f}",
                                     f"{'+' if hpnl >= 0 else ''}{hpnl:,.2f}",
                                     f"{share:5.1f}%  {bar}"))
        self._draw_donut(rows, total)

    def _draw_donut(self, rows, total):
        c = self.donut
        c.delete("all")
        for w in self.legend.winfo_children():
            w.destroy()
        if not rows or total <= 0:
            c.create_text(75, 75, text="NO DATA", fill=DIM,
                          font=("Segoe UI", 10, "bold"))
            return
        box = (6, 6, 144, 144)
        start = 90.0
        for i, (sym, d) in enumerate(rows[:8]):
            val = holding_value(sym, d["qty"], self.prices)
            extent = 360.0 * val / total
            color = HOLDING_COLORS[i % len(HOLDING_COLORS)]
            c.create_arc(box, start=start - extent, extent=extent,
                         style="arc", width=24, outline=color)
            start -= extent
            pct = val / total * 100
            lr = Frame(self.legend, bg=PANEL)
            lr.pack(anchor=W, pady=1)
            Label(lr, text="  ", bg=color, fg=color, width=1).pack(side=LEFT)
            Label(lr, text=f" {sym} {pct:4.1f}%", font=("Consolas", 8),
                  fg=TEXT, bg=PANEL).pack(side=LEFT)
        c.create_text(75, 70, text="TOTAL", font=("Segoe UI", 7),
                      fill=DIM)
        c.create_text(75, 84, text=f"${total:,.0f}",
                      font=("Segoe UI", 10, "bold"), fill=TEXT)


# ===========================================================================
#  TERMINAL VERSION  (classic input() / print())
# ===========================================================================
def run_cli():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    portfolio, realized = load_portfolio()
    prices = dict(STOCK_PRICES)
    print("=" * 58)
    print("     STOCK PORTFOLIO TRACKER  (CLI - Advanced)")
    print("=" * 58)
    print("Stocks:", ", ".join(f"{k}=${v}" for k, v in prices.items()))
    if portfolio:
        print(f"(loaded {len(portfolio)} holding(s) from portfolio.json)")

    while True:
        print("\n1) Buy   2) Sell   3) View   4) Totals")
        print("5) Live prices   6) Save file   7) Quit")
        choice = input("> ").strip()

        if choice == "1":
            sym = input("  Stock symbol: ").strip().upper()
            if sym not in prices:
                print("  Unknown stock. Options:", ", ".join(prices))
                continue
            try:
                qty = float(input("  Quantity: "))
                if qty <= 0:
                    raise ValueError
            except ValueError:
                print("  Quantity must be a positive number.")
                continue
            raw = input(f"  Buy cost/share [{prices[sym]}]: ").strip()
            try:
                cost = float(raw) if raw else prices[sym]
                if cost <= 0:
                    raise ValueError
            except ValueError:
                print("  Invalid cost.")
                continue
            buy(portfolio, sym, qty, cost)
            persist(portfolio, realized)
            print(f"  Bought {qty:g} {sym} @ ${cost:,.2f}")

        elif choice == "2":
            sym = input("  Stock symbol to sell: ").strip().upper()
            if sym not in portfolio:
                print("  You do not own that stock.")
                continue
            try:
                qty = float(input(f"  Quantity (you own {portfolio[sym]['qty']:g}): "))
                if qty <= 0 or qty > portfolio[sym]["qty"]:
                    raise ValueError
            except ValueError:
                print("  Invalid quantity.")
                continue
            realized += sell(portfolio, sym, qty, prices.get(sym, 0))
            persist(portfolio, realized)
            print(f"  Sold {qty:g} {sym} \u2022 realized P/L ${realized:,.2f} total")

        elif choice == "3":
            print(f"\n  {'STOCK':<9}{'PRICE':>9}{'AVG':>9}{'QTY':>7}"
                  f"{'VALUE':>11}{'P/L':>11}")
            print("  " + "-" * 56)
            for sym, d in portfolio.items():
                val = holding_value(sym, d["qty"], prices)
                pnl = val - d["qty"] * d["avg"]
                print(f"  {sym:<9}{prices.get(sym, 0):>9.2f}"
                      f"{d['avg']:>9.2f}{d['qty']:>7g}{val:>11.2f}"
                      f"{pnl:>+11.2f}")
            print("  " + "-" * 56)

        elif choice == "4":
            tv = total_value(portfolio, prices)
            tc = total_cost(portfolio)
            print(f"  Value  : ${tv:,.2f}")
            print(f"  Invested: ${tc:,.2f}")
            print(f"  Unrealized P/L: ${tv - tc:+,.2f}")
            print(f"  Realized P/L  : ${realized:+,.2f}")

        elif choice == "5":
            print("  Fetching live prices...")
            try:
                found = fetch_live_prices()
            except Exception:
                found = {}
            if found:
                prices.update(found)
                print(f"  Updated {len(found)} prices. e.g. " +
                      ", ".join(f"{k}=${v:,.2f}" for k, v in
                                list(found.items())[:4]))
            else:
                print("  Offline - keeping manual prices.")

        elif choice == "6":
            if not portfolio:
                print("  Portfolio is empty.")
                continue
            kind = input("  Save as (txt/csv): ").strip().lower() or "txt"
            if kind not in ("txt", "csv"):
                kind = "txt"
            path = input(f"  File path [portfolio.{kind}]: ").strip() \
                or f"portfolio.{kind}"
            try:
                total = save_to_file(portfolio, prices, path, kind, realized)
                print(f"  Saved \u2713 {path}  (total ${total:,.2f})")
            except OSError as err:
                print("  Save failed:", err)

        elif choice == "7":
            print("  Goodbye!")
            break


# ===========================================================================
def main():
    if "--cli" in sys.argv:
        run_cli()
        return
    root = Tk()
    PortfolioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
