#!/usr/bin/env python3
# ================================================================
# NEXORA NEWS AI - RED EDITION
# Professional Forex News Signal Analyzer
# 
# DATA SOURCE: TradingView Economic Calendar API
# API: https://economic-calendar.tradingview.com/events
# STRATEGY ENGINE: Guru.py Fundamental Logic
# ================================================================

import os
import re
import sys
import time
import json
import requests
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

APP_NAME = "NEXORA NEWS AI"
VERSION = " RED PRO"
API_URL = "https://economic-calendar.tradingview.com/events"

REQUEST_TIMEOUT = 15
UTC_PLUS_6 = timezone(timedelta(hours=6))

# ------------------------------------------------
# ANSI RED THEME PALETTE
# ------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

BRIGHT_RED = "\033[91m"
RED = "\033[31m"
DARK_RED = "\033[38;5;88m"
CRIMSON = "\033[38;5;160m"
ORANGE = "\033[38;5;208m"
GOLD = "\033[38;5;220m"
WHITE = "\033[97m"
GRAY = "\033[90m"
BG_RED = "\033[41m"

SPINNER = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def sleep_small(seconds: float) -> None:
    time.sleep(seconds)


def loading_animation(label: str, duration: float = 0.65) -> None:
    end = time.time() + duration
    i = 0
    while time.time() < end:
        print(
            f"\r{BRIGHT_RED}  {SPINNER[i % len(SPINNER)]}  {WHITE}{label}...{RESET}",
            end="",
            flush=True,
        )
        i += 1
        time.sleep(0.08)
    print(f"\r{CRIMSON}  ✔  {WHITE}{label}{RESET}" + " " * 20)


def progress_bar(label: str, steps: int = 24, delay: float = 0.02) -> None:
    print(f"{ORANGE}  {label}{RESET}")
    for i in range(steps + 1):
        filled = "█" * i
        empty = "░" * (steps - i)
        pct = int((i / steps) * 100)
        print(f"\r  [{BRIGHT_RED}{filled}{RESET}{DIM}{empty}{RESET}] {GOLD}{pct:3d}%{RESET}", end="")
        time.sleep(delay)
    print()


def banner() -> None:
    print(f"""
{BRIGHT_RED} ███╗   ██╗ ███████╗ ██╗  ██╗ ██████╗ ██████╗  █████╗ 
{CRIMSON} ████╗  ██║ ██╔════╝ ╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗
{RED} ██╔██╗ ██║ █████╗    ╚███╔╝ ██║   ██║██████╔╝███████║
{DARK_RED} ██║╚██╗██║ ██╔══╝    ██╔██╗ ██║   ██║██╔══██╗██╔══██║
{BRIGHT_RED} ██║ ╚████║ ███████╗  ██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║
{RED} ╚═╝  ╚═══╝ ╚══════╝  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝{RESET}

{BOLD}{WHITE}        GURU STRATEGY ENGINE  |  TRADINGVIEW API{RESET}
{DIM}{ORANGE}              NEXORA FUNDAMENTAL INTELLIGENCE{RESET}
""")


def section(title: str, width: int = 76) -> None:
    print(f"\n{BRIGHT_RED}{'═' * width}{RESET}")
    print(f"{BOLD}{GOLD}  ◆ {title}{RESET}")
    print(f"{BRIGHT_RED}{'═' * width}{RESET}")


def box_line(top: bool = False, bottom: bool = False, width: int = 78) -> str:
    if top:
        return f"┌{'─' * (width-2)}┐"
    if bottom:
        return f"└{'─' * (width-2)}┘"
    return f"│{' ' * (width-2)}│"


# ------------------------------------------------
# TRADINGVIEW API FETCH & PARSER
# ------------------------------------------------

def fetch_tradingview_calendar() -> List[Dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    now = datetime.now(timezone.utc)
    from_date = now.strftime("%Y-%m-%dT00:00:00.000Z")
    to_date = (now + timedelta(days=7)).strftime("%Y-%m-%dT23:59:59.000Z")

    payload = {
        "from": from_date,
        "to": to_date,
        "countries": "US,EU,GB,JP,CA,AU,CH,NZ",
        "minImportance": -1  # All impact levels
    }

    response = requests.post(API_URL, headers=headers, data=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()

    events = data.get("result", [])
    formatted_events = []

    for item in events:
        # Convert TradingView schema to standard schema
        dt_str = item.get("date")
        dt = None
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                dt = None

        imp_val = item.get("importance", -1)
        imp_label = "HIGH" if imp_val == 1 else "MEDIUM" if imp_val == 0 else "LOW"

        formatted_events.append({
            "id": item.get("id"),
            "event": item.get("title", "Unknown Event"),
            "country": item.get("country", "US"),
            "currency": get_currency_from_country(item.get("country", "US")),
            "impact": imp_label,
            "datetime": dt,
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "previous": item.get("previous"),
        })

    formatted_events.sort(key=lambda x: x["datetime"] or datetime.now(timezone.utc))
    return formatted_events


def get_currency_from_country(country: str) -> str:
    mapping = {
        "US": "USD", "EU": "EUR", "GB": "GBP", "JP": "JPY",
        "CA": "CAD", "AU": "AUD", "NZ": "NZD", "CH": "CHF"
    }
    return mapping.get(country.upper(), country.upper())


# ------------------------------------------------
# GURU.PY STRATEGY ENGINE
# ------------------------------------------------

PAIR_OPTIONS = {
    "CAD": ["CADJPY", "EURCAD", "GBPCAD", "USDCAD"],
    "USD": ["USDCAD", "USDJPY", "EURUSD", "GBPUSD"],
    "EUR": ["EURUSD", "EURGBP", "EURJPY", "EURCAD"],
    "GBP": ["GBPUSD", "GBPJPY", "EURGBP", "GBPCAD"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "CADJPY"],
    "AUD": ["AUDUSD", "AUDJPY"],
    "NZD": ["NZDUSD"],
    "CHF": ["USDCHF", "EURCHF"]
}

# Cross vs Inverse rules from Guru.py
CAD_CROSS = ["CADJPY"]
CAD_INVERSE = ["EURCAD", "GBPCAD", "USDCAD"]

USD_CROSS = ["USDCAD", "USDJPY"]
USD_INVERSE = ["EURUSD", "GBPUSD"]

EUR_CROSS = ["EURGBP", "EURCAD", "EURJPY", "EURUSD"]
GBP_CROSS = ["GBPCAD", "GBPUSD", "GBPJPY"]
EURGBP = ["EURGBP"]


def evaluate_guru_strategy(event_title: str, country: str, market: str, val1: float, val2: float) -> List[str]:
    """
    Implements the fundamental matrix strategy logic.
    val1 = Previous / Current Comparison value
    val2 = Forecast / Baseline value
    Returns list of directional keywords: ['CALL', 'BUY', 'BULLISH'] or ['PUT', 'SELL', 'BEARISH']
    """
    up = ["CALL", "BUY", "BULLISH"]
    down = ["PUT", "SELL", "BEARISH"]
    title_upper = event_title.upper()

    # 1. CAD CPI / GDP
    if "CPI" in title_upper or "GDP" in title_upper:
        if country == "CA":
            if market in CAD_CROSS:
                return up if val1 < val2 else down
            elif market in CAD_INVERSE:
                return down if val1 < val2 else up

    # 2. Core PPI / CPI / Core Retail Sales / NFP / ISM / JOLTS
    if any(k in title_upper for k in ["PPI", "CPI", "RETAIL SALES", "PAYROLL", "ISM", "JOLTS", "EMPLOYMENT"]):
        if country == "US":
            if market in USD_CROSS:
                return up if val1 < val2 else down
            elif market in USD_INVERSE:
                return down if val1 < val2 else up

    # 3. Unemployment Claim (Inverted Logic)
    if "UNEMPLOYMENT" in title_upper or "JOBLESS" in title_upper:
        if country == "US":
            if market in USD_CROSS:
                return up if val1 > val2 else down
            elif market in USD_INVERSE:
                return down if val1 > val2 else up

    # 4. Flash Service PMI (EUR, USD, GBP)
    if "PMI" in title_upper:
        if country == "EU" and market in EUR_CROSS:
            return up if val1 < val2 else down
        elif country == "US":
            if market in USD_CROSS:
                return up if val1 < val2 else down
            elif market in USD_INVERSE:
                return down if val1 < val2 else up
        elif country == "GB":
            if market in GBP_CROSS:
                return up if val1 < val2 else down
            elif market in EURGBP:
                return down if val1 < val2 else up

    # Fallback Generic Fundamental Matrix Rule
    if val1 < val2:
        return up if country in market[:3] else down
    else:
        return down if country in market[:3] else up


# ------------------------------------------------
# FORMATTERS & OUTPUTS
# ------------------------------------------------

def fmt_val(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v:g}"


def local_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "N/A"
    return dt.astimezone(UTC_PLUS_6).strftime("%d %b %Y  %H:%M:%S")


def print_events_hud(events: List[Dict[str, Any]]) -> None:
    section("TRADINGVIEW ECONOMIC CALENDAR HUD")
    print(
        f"{DIM}{'#':<4} {'TIME (BD)':<22} {'CCY':<6} "
        f"{'IMPACT':<9} {'EVENT':<55}{RESET}"
    )
    print("-" * 100)

    for idx, item in enumerate(events[:30], 1):
        dt = item["datetime"]
        imp = item["impact"]
        imp_color = BRIGHT_RED if imp == "HIGH" else ORANGE if imp == "MEDIUM" else WHITE
        print(
            f"{GOLD}{idx:>3}.{RESET} "
            f"{local_dt(dt):<22} "
            f"{item['currency']:<6} "
            f"{imp_color}{imp:<9}{RESET} "
            f"{item['event'][:53]:<55}"
        )


def print_signal_card(event_item: Dict[str, Any], market: str, directions: List[str]) -> None:
    width = 82
    direction_main = directions[0]
    direction_color = BRIGHT_RED if direction_main == "PUT" else GOLD

    dt = event_item["datetime"] or datetime.now(timezone.utc)
    entry_dt = dt - timedelta(seconds=10)
    expiry_dt = dt + timedelta(minutes=1)

    print(f"\n{BRIGHT_RED}{box_line(top=True, width=width)}{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {BOLD}{WHITE}NEXORA GURU NEWS ALERT{RESET} "
          f"{DIM}v{VERSION}{RESET} {' ' * (width - 37)} {BRIGHT_RED}│{RESET}")
    print(f"{BRIGHT_RED}├{'─' * (width-2)}┤{RESET}")

    # Market & Pair
    print(f"{BRIGHT_RED}│{RESET} {ORANGE}MARKET PAIR{RESET}      {BOLD}{WHITE}{market}{RESET}"
          f"{' ' * (width - 24 - len(market))} {BRIGHT_RED}│{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {ORANGE}EVENT NAME{RESET}       {WHITE}{event_item['event']}{RESET}"
          f"{' ' * (width - 24 - len(event_item['event']))} {BRIGHT_RED}│{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {ORANGE}CURRENCY{RESET}         {WHITE}{event_item['currency']} ({event_item['country']}){RESET}"
          f"{' ' * (width - 29 - len(event_item['currency']))} {BRIGHT_RED}│{RESET}")

    # Values
    print(f"{BRIGHT_RED}├{'─' * (width-2)}┤{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {ORANGE}PREVIOUS{RESET}         {GOLD}{fmt_val(event_item['previous'])}{RESET}"
          f"{' ' * (width - 26 - len(fmt_val(event_item['previous'])))} {BRIGHT_RED}│{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {ORANGE}FORECAST{RESET}         {GOLD}{fmt_val(event_item['forecast'])}{RESET}"
          f"{' ' * (width - 26 - len(fmt_val(event_item['forecast'])))} {BRIGHT_RED}│{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {ORANGE}ACTUAL{RESET}           {GOLD}{fmt_val(event_item['actual'])}{RESET}"
          f"{' ' * (width - 24 - len(fmt_val(event_item['actual'])))} {BRIGHT_RED}│{RESET}")

    # Execution Timing
    print(f"{BRIGHT_RED}├{'─' * (width-2)}┤{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {ORANGE}NEWS TIME{RESET}        {WHITE}{local_dt(dt)}{RESET}"
          f"{' ' * (width - 32 - len(local_dt(dt)))} {BRIGHT_RED}│{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {ORANGE}ENTRY TIME{RESET}       {GOLD}{entry_dt.astimezone(UTC_PLUS_6).strftime('%H:%M:%S')}{RESET}"
          f"{' ' * (width - 26)} {BRIGHT_RED}│{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {ORANGE}EXPIRY TIME{RESET}      {GOLD}{expiry_dt.astimezone(UTC_PLUS_6).strftime('%H:%M:%S')}{RESET}"
          f"{' ' * (width - 26)} {BRIGHT_RED}│{RESET}")

    # Direction
    print(f"{BRIGHT_RED}├{'─' * (width-2)}┤{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {ORANGE}◆◆◆  GURU DIRECTIONAL SIGNAL  ◆◆◆{RESET}"
          f"{' ' * (width - 40)} {BRIGHT_RED}│{RESET}")
    dir_str = f"{direction_color}{BOLD}{'/'.join(directions)}{RESET}"
    print(f"{BRIGHT_RED}│{RESET}       {dir_str}"
          f"{' ' * (width - 10 - len('/'.join(directions)))} {BRIGHT_RED}│{RESET}")

    # Warnings
    print(f"{BRIGHT_RED}├{'─' * (width-2)}┤{RESET}")
    print(f"{BRIGHT_RED}│{RESET} {BRIGHT_RED}{BOLD}⚠ HIGH RISK FUNDAMENTAL TRADE WARNING{RESET}"
          f"{' ' * (width - 43)} {BRIGHT_RED}│{RESET}")
    print(f"{BRIGHT_RED}│{RESET}   {GOLD}News Trade is Risky! Mind your Own Risk!{RESET}"
          f"{' ' * (width - 48)} {BRIGHT_RED}│{RESET}")
    print(f"{BRIGHT_RED}│{RESET}   {GOLD}NEXORA GURU is based on Fundamental Matrix Analysis!{RESET}"
          f"{' ' * (width - 60)} {BRIGHT_RED}│{RESET}")

    print(f"{BRIGHT_RED}{box_line(bottom=True, width=width)}{RESET}")


# ------------------------------------------------
# MAIN PIPELINE
# ------------------------------------------------

def run_engine() -> None:
    clear_screen()
    banner()

    now_bd = datetime.now(UTC_PLUS_6).strftime("%a, %d %b %Y  %H:%M:%S")
    print(f"{DIM}  SYSTEM TIME : {now_bd}  |  ZONE : UTC +06:00{RESET}")
    print(f"{DIM}  DATA SOURCE  : TradingView Economic Calendar API{RESET}")

    section("INITIALIZING NEXORA SYSTEM")
    loading_animation("Connecting TradingView API Endpoint", 0.6)

    try:
        events = fetch_tradingview_calendar()
    except Exception as exc:
        print(f"\n{BRIGHT_RED}  ✗ TRADINGVIEW API CONNECTION FAILED{RESET}")
        print(f"{ORANGE}  {exc}{RESET}")
        return

    loading_animation("Fetching Economic Events", 0.5)
    progress_bar("Parsing TradingView Data Structure", 20)
    progress_bar("Applying Guru.py Fundamental Rules", 20)

    clear_screen()
    banner()
    print(f"{GOLD}  API STATUS : ONLINE{RESET}   "
          f"{BRIGHT_RED}EVENTS LOADED : {len(events)}{RESET}")

    while True:
        print_events_hud(events)

        print(f"""
{BRIGHT_RED}════════════════════════════════════════════════════════════════════{RESET}
{BOLD}{GOLD}  Select an event index number to generate Guru strategy signal.{RESET}
{BOLD}{ORANGE}  [R] REFRESH API     [Q] QUIT{RESET}
{BRIGHT_RED}════════════════════════════════════════════════════════════════════{RESET}
""")

        choice = input("  Your choice: ").strip().lower()

        if choice == 'q':
            print(f"\n{BRIGHT_RED}  NEXORA Engine Closed.{RESET}\n")
            break

        if choice == 'r':
            try:
                events = fetch_tradingview_calendar()
            except Exception as e:
                print(f"{BRIGHT_RED}Refresh failed: {e}{RESET}")
            clear_screen()
            banner()
            continue

        if not choice.isdigit():
            print(f"{BRIGHT_RED}Invalid choice! Enter index number.{RESET}")
            sleep_small(1)
            clear_screen()
            banner()
            continue

        idx = int(choice)
        if idx < 1 or idx > len(events):
            print(f"{BRIGHT_RED}Index out of bounds.{RESET}")
            sleep_small(1)
            clear_screen()
            banner()
            continue

        selected_event = events[idx - 1]
        ccy = selected_event["currency"]

        # Market Selection
        available_markets = PAIR_OPTIONS.get(ccy, ["EURUSD", "GBPUSD", "USDJPY", "USDCAD"])
        print(f"\n{GOLD}Available Markets for {ccy}:{RESET}")
        for m_idx, m_name in enumerate(available_markets, 1):
            print(f"  {BRIGHT_RED}{m_idx}.{RESET} {WHITE}{m_name}{RESET}")

        m_choice = input(f"\n  Select market (1-{len(available_markets)}) [Default 1]: ").strip()
        selected_market = available_markets[0]
        if m_choice.isdigit() and 1 <= int(m_choice) <= len(available_markets):
            selected_market = available_markets[int(m_choice) - 1]

        # Values check
        prev_val = selected_event["previous"]
        fore_val = selected_event["forecast"]

        if prev_val is None or fore_val is None:
            print(f"\n{ORANGE}Missing forecast/previous values in API. Manual input required:{RESET}")
            try:
                prev_val = float(input("  Enter Previous Value: ").strip())
                fore_val = float(input("  Enter Forecast Value: ").strip())
            except ValueError:
                print(f"{BRIGHT_RED}Invalid numeric input!{RESET}")
                sleep_small(1.5)
                clear_screen()
                banner()
                continue

        # Generate Direction using Guru Strategy
        directions = evaluate_guru_strategy(
            selected_event["event"],
            selected_event["country"],
            selected_market,
            prev_val,
            fore_val
        )

        clear_screen()
        banner()
        print_signal_card(selected_event, selected_market, directions)

        input(f"\n{DIM}Press Enter to return to HUD...{RESET}")
        clear_screen()
        banner()


def main() -> None:
    try:
        run_engine()
    except KeyboardInterrupt:
        print(f"\n\n{BRIGHT_RED}  Exited by user.{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
