#!/usr/bin/env python3
# ================================================================
# NEXORA NEWS AI
# Professional Forex News Signal Analyzer
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
VERSION = "1.0 PRO"

# Primary & Fallback Endpoints (FairEconomy / ForexFactory)
PRIMARY_API = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FALLBACK_APIS = [
    "https://nfs.faireconomy.media/ff_calendar.json",
    "https://nfs.faireconomy.media/ff_calendar_today.json"
]

REQUEST_TIMEOUT = 15
UTC_PLUS_6 = timezone(timedelta(hours=6))
LOOKAHEAD_HOURS = 120
MIN_CONFIDENCE = 50.0
ENTRY_BEFORE_SECONDS = 10
EXPIRY_AFTER_SECONDS = 60

# ------------------------------------------------
# ANSI UI & STRIPPER
# ------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
ORANGE = "\033[38;5;208m"

SPINNER = ["◐", "◓", "◑", "◒"]
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def visible_len(text: str) -> int:
    """Calculates visible character length excluding ANSI escape codes."""
    return len(ANSI_ESCAPE.sub('', str(text)))


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def sleep_small(seconds: float) -> None:
    time.sleep(seconds)


def loading_animation(label: str, duration: float = 0.5) -> None:
    end = time.time() + duration
    i = 0
    while time.time() < end:
        print(
            f"\r{CYAN}  {SPINNER[i % len(SPINNER)]}  {label}...{RESET}",
            end="",
            flush=True,
        )
        i += 1
        time.sleep(0.08)
    print(f"\r{GREEN}  ✓  {label}{RESET}" + " " * 20)


def progress_bar(label: str, steps: int = 18, delay: float = 0.015) -> None:
    print(f"{YELLOW}  {label}{RESET}")
    for i in range(steps + 1):
        filled = "█" * i
        empty = "░" * (steps - i)
        pct = int((i / steps) * 100)
        print(f"\r  [{GREEN}{filled}{RESET}{DIM}{empty}{RESET}] {pct:3d}%", end="")
        time.sleep(delay)
    print()


def banner() -> None:
    print(f"""
{ORANGE} ███╗   ██╗ ███████╗ ██╗  ██╗ ██████╗ ██████╗  █████╗
{YELLOW} ████╗  ██║ ██╔════╝ ╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗
{GREEN} ██╔██╗ ██║ █████╗    ╚███╔╝ ██║   ██║██████╔╝███████║
{CYAN} ██║╚██╗██║ ██╔══╝    ██╔██╗ ██║   ██║██╔══██╗██╔══██║
{BLUE} ██║ ╚████║ ███████╗  ██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║
{MAGENTA} ╚═╝  ╚═══╝ ╚══════╝  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝{RESET}

{BOLD}{WHITE}        PROFESSIONAL FOREX NEWS SIGNAL ANALYZER{RESET}
{DIM}              DATA  →  ANALYSIS  →  SIGNALS{RESET}
""")


def section(title: str, width: int = 80) -> None:
    print(f"\n{CYAN}{'═' * width}{RESET}")
    print(f"{BOLD}{YELLOW}  ◆ {title}{RESET}")
    print(f"{CYAN}{'═' * width}{RESET}")


def make_box_row(content: str, width: int = 82) -> str:
    vis_len = visible_len(content)
    pad = max(0, width - 4 - vis_len)
    return f"{ORANGE}│{RESET} {content}{' ' * pad} {ORANGE}│{RESET}"


# ------------------------------------------------
# DATA HELPERS
# ------------------------------------------------

def normalize(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def get_field(item: Dict[str, Any], *names: str) -> Any:
    lower = {str(k).lower(): v for k, v in item.items()}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def parse_number(value: Any) -> Optional[float]:
    if value is None:
        return None

    s = normalize(value)
    if not s or s.lower() in {"n/a", "na", "none", "null", "-", ""}:
        return None

    m = re.search(r"[-+]?\d+(?:\.\d+)?", s.replace(",", ""))
    if not m:
        return None

    try:
        number = float(m.group())
    except ValueError:
        return None

    upper = s.upper()
    if "K" in upper:
        number *= 1_000
    elif "M" in upper:
        number *= 1_000_000
    elif "B" in upper:
        number *= 1_000_000_000

    return number


def parse_datetime(item: Dict[str, Any]) -> Optional[datetime]:
    raw = get_field(item, "timestamp", "datetime", "date", "time", "event_time")
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        except Exception:
            return None

    text = normalize(raw)
    if not text:
        return None

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m-%d-%Y %H:%M:%S",
        "%m-%d-%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%b %d, %Y %H:%M",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def event_name(item: Dict[str, Any]) -> str:
    return normalize(
        get_field(item, "event", "title", "name", "description", "event_name")
    ) or "Unknown Event"


def currency(item: Dict[str, Any]) -> str:
    value = normalize(get_field(item, "currency", "ccy", "country")).upper()
    country_map = {
        "UNITED STATES": "USD", "US": "USD", "USA": "USD",
        "EURO ZONE": "EUR", "EU": "EUR", "EUROPE": "EUR",
        "UNITED KINGDOM": "GBP", "UK": "GBP", "GREAT BRITAIN": "GBP",
        "JAPAN": "JPY", "CANADA": "CAD", "AUSTRALIA": "AUD",
        "NEW ZEALAND": "NZD", "SWITZERLAND": "CHF",
    }
    return country_map.get(value, value)


def impact(item: Dict[str, Any]) -> str:
    value = normalize(get_field(item, "impact", "importance", "priority")).lower()
    if value in {"high", "3", "red"}:
        return "HIGH"
    if value in {"medium", "moderate", "2", "orange"}:
        return "MEDIUM"
    if value in {"low", "1", "yellow"}:
        return "LOW"
    return value.upper() or "UNKNOWN"


def values(item: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    actual = parse_number(get_field(item, "actual"))
    forecast = parse_number(get_field(item, "forecast", "consensus"))
    previous = parse_number(get_field(item, "previous", "prev"))
    return actual, forecast, previous


# ------------------------------------------------
# NEWS INTELLIGENCE ENGINE
# ------------------------------------------------

EVENT_POLARITY = {
    "non farm payroll": 1, "nonfarm payroll": 1, "employment change": 1,
    "job change": 1, "average hourly earnings": 1, "gdp": 1,
    "gross domestic product": 1, "retail sales": 1, "core retail sales": 1,
    "industrial production": 1, "manufacturing pmi": 1, "services pmi": 1,
    "composite pmi": 1, "pmi": 1, "consumer confidence": 1,
    "consumer sentiment": 1, "durable goods orders": 1, "housing starts": 1,
    "building permits": 1, "jolts": 1, "job openings": 1,
    "unemployment claims": -1, "initial jobless claims": -1, "unemployment rate": -1,
}

SPECIAL_EVENTS = {
    "cpi", "core cpi", "inflation", "ppi", "core ppi", "interest rate",
    "rate decision", "fomc", "fed", "ecb", "boe", "bank of japan",
    "central bank", "press conference", "speech", "testimony", "minutes"
}


def event_polarity(name: str) -> int:
    n = name.lower()
    for key, polarity in EVENT_POLARITY.items():
        if key in n:
            return polarity
    return 0


def is_special_event(name: str) -> bool:
    n = name.lower()
    return any(key in n for key in SPECIAL_EVENTS)


def impact_weight(level: str) -> float:
    return {"HIGH": 1.00, "MEDIUM": 0.70, "LOW": 0.35}.get(level, 0.20)


def relative_surprise(actual: float, forecast: float) -> float:
    denominator = max(abs(forecast), 1.0)
    surprise = (actual - forecast) / denominator
    return max(-1.0, min(1.0, surprise))


def analyze_event(item: Dict[str, Any]) -> Dict[str, Any]:
    name = event_name(item)
    ccy = currency(item)
    level = impact(item)
    actual, forecast, previous = values(item)
    dt = parse_datetime(item)

    polarity = event_polarity(name)
    special = is_special_event(name)

    directional_bias = 0.0
    source_of_direction = "NEUTRAL"

    if actual is not None and forecast is not None and polarity != 0:
        surprise = relative_surprise(actual, forecast)
        directional_bias = surprise * polarity
        source_of_direction = "ACTUAL_vs_FORECAST"
    elif forecast is not None and previous is not None and polarity != 0:
        surprise = relative_surprise(forecast, previous)
        directional_bias = surprise * polarity * 0.55
        source_of_direction = "FORECAST_vs_PREVIOUS"
    elif special:
        directional_bias = 0.25 if level == "HIGH" else 0.15
        source_of_direction = "VOLATILITY_EVENT"

    if special and "ACTUAL" in source_of_direction:
        directional_bias *= 0.70

    confidence = 50.0
    confidence += abs(directional_bias) * 35.0
    confidence += impact_weight(level) * 15.0

    if actual is not None and forecast is not None:
        confidence += 8.0
    elif forecast is not None and previous is not None:
        confidence += 2.0

    confidence = max(30.0, min(95.0, confidence))

    return {
        "event": name,
        "currency": ccy,
        "impact": level,
        "datetime": dt,
        "actual": actual,
        "forecast": forecast,
        "previous": previous,
        "bias": directional_bias,
        "confidence": confidence,
        "source": source_of_direction,
    }


# ------------------------------------------------
# PAIR & SIGNAL ENGINE
# ------------------------------------------------

PAIR_MAP = {
    "USD": ["EUR/USD", "GBP/USD", "AUD/USD", "USD/JPY", "USD/CAD", "USD/CHF"],
    "EUR": ["EUR/USD", "EUR/GBP", "EUR/JPY", "EUR/CAD"],
    "GBP": ["GBP/USD", "GBP/JPY", "EUR/GBP", "GBP/CAD"],
    "JPY": ["USD/JPY", "EUR/JPY", "GBP/JPY", "AUD/JPY"],
    "AUD": ["AUD/USD", "AUD/JPY", "AUD/NZD"],
    "NZD": ["NZD/USD", "AUD/NZD"],
    "CAD": ["USD/CAD", "CAD/JPY", "EUR/CAD"],
    "CHF": ["USD/CHF", "EUR/CHF"],
}


def pair_direction(pair: str, ccy: str, bias: float) -> str:
    base, quote = pair.split("/")
    if bias >= 0:
        return "CALL" if ccy == base else "PUT"
    else:
        return "PUT" if ccy == base else "CALL"


def build_signal(analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ccy = analysis["currency"]
    bias = analysis["bias"]

    if ccy not in PAIR_MAP:
        return None

    if analysis["confidence"] < MIN_CONFIDENCE:
        return None

    pair = PAIR_MAP[ccy][0]
    direction = pair_direction(pair, ccy, bias)

    dt = analysis["datetime"]
    entry = (dt - timedelta(seconds=ENTRY_BEFORE_SECONDS)) if dt else None
    expiry = (dt + timedelta(seconds=EXPIRY_AFTER_SECONDS)) if dt else None

    return {
        "pair": pair,
        "currency": ccy,
        "event": analysis["event"],
        "impact": analysis["impact"],
        "direction": direction,
        "confidence": round(analysis["confidence"], 1),
        "bias": round(bias, 3),
        "source": analysis["source"],
        "actual": analysis["actual"],
        "forecast": analysis["forecast"],
        "previous": analysis["previous"],
        "event_time": dt,
        "entry_time": entry,
        "expiry_time": expiry,
    }


# ------------------------------------------------
# LIVE API FETCH ENGINE
# ------------------------------------------------

def fetch_calendar() -> Tuple[List[Dict[str, Any]], str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Cache-Control": "no-cache"
    }

    urls_to_try = [PRIMARY_API] + FALLBACK_APIS
    last_err = None

    for url in urls_to_try:
        try:
            res = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            res.raise_for_status()
            data = res.json()

            if isinstance(data, list) and len(data) > 0:
                return data, url
            elif isinstance(data, dict):
                for k in ("events", "calendar", "data"):
                    if isinstance(data.get(k), list) and len(data[k]) > 0:
                        return data[k], url
        except Exception as err:
            last_err = err
            continue

    raise RuntimeError(f"All API endpoints failed. Last error: {last_err}")


def filter_upcoming(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc) - timedelta(hours=12)  # Include recent events from today
    end = now + timedelta(hours=LOOKAHEAD_HOURS)
    output = []

    for item in events:
        dt = parse_datetime(item)
        if dt and now <= dt <= end:
            output.append(item)

    output.sort(key=lambda x: parse_datetime(x) or datetime.max.replace(tzinfo=timezone.utc))
    return output


# ------------------------------------------------
# OUTPUT & RENDERING
# ------------------------------------------------

def fmt_value(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.2f}K"
    return f"{value:g}"


def local_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "N/A"
    return dt.astimezone(UTC_PLUS_6).strftime("%d %b %Y  %H:%M:%S")


def meter(confidence: float, width: int = 22) -> str:
    filled = int((confidence / 100.0) * width)
    filled = max(0, min(width, filled))
    label = "STRONG" if confidence >= 80 else "GOOD" if confidence >= 70 else "MODERATE"
    return (
        f"[{GREEN}{'█' * filled}{RESET}"
        f"{DIM}{'░' * (width - filled)}{RESET}] "
        f"{YELLOW}{confidence:.1f}%{RESET}  {BOLD}{label}{RESET}"
    )


def print_events_hud(events: List[Dict[str, Any]]) -> None:
    section("LIVE ECONOMIC NEWS HUD")
    print(f"{DIM}{'#':<4} {'TIME (BD UTC+6)':<22} {'CCY':<6} {'IMPACT':<9} {'EVENT':<35}{RESET}")
    print("-" * 80)

    for idx, item in enumerate(events, 1):
        dt = parse_datetime(item)
        imp = impact(item)
        imp_color = RED if imp == "HIGH" else YELLOW if imp == "MEDIUM" else WHITE
        print(
            f"{YELLOW}{idx:>3}.{RESET} "
            f"{local_dt(dt):<22} "
            f"{currency(item):<6} "
            f"{imp_color}{imp:<9}{RESET} "
            f"{event_name(item)[:33]:<35}"
        )

    if not events:
        print(f"{YELLOW}No upcoming events found in the current time window.{RESET}")


def print_signal_card(signal: Dict[str, Any], number: int) -> None:
    w = 82
    direction = signal["direction"]
    dir_color = GREEN if direction == "CALL" else RED

    print(f"\n{ORANGE}┌{'─' * (w-2)}┐{RESET}")
    print(make_box_row(f"{BOLD}{WHITE}NEXORA NEWS SIGNAL #{number}{RESET} {DIM}v{VERSION}{RESET}", w))
    print(f"{ORANGE}├{'─' * (w-2)}┤{RESET}")

    print(make_box_row(f"{CYAN}PAIR{RESET}              : {BOLD}{WHITE}{signal['pair']}{RESET}", w))
    print(make_box_row(f"{CYAN}CURRENCY{RESET}          : {WHITE}{signal['currency']}{RESET}", w))
    print(f"{ORANGE}├{'─' * (w-2)}┤{RESET}")

    print(make_box_row(f"{CYAN}EVENT NAME{RESET}        : {GREEN}{signal['event']}{RESET}", w))
    print(make_box_row(f"{CYAN}EVENT TIME{RESET}        : {YELLOW}{local_dt(signal['event_time'])}{RESET}", w))

    imp = signal['impact']
    imp_color = RED if imp == "HIGH" else YELLOW if imp == "MEDIUM" else WHITE
    print(make_box_row(f"{CYAN}IMPACT LEVEL{RESET}      : {imp_color}{imp}{RESET}", w))
    print(f"{ORANGE}├{'─' * (w-2)}┤{RESET}")

    print(make_box_row(f"{CYAN}PREVIOUS{RESET}          : {WHITE}{fmt_value(signal['previous'])}{RESET}", w))
    print(make_box_row(f"{CYAN}FORECAST{RESET}          : {WHITE}{fmt_value(signal['forecast'])}{RESET}", w))
    print(make_box_row(f"{CYAN}ACTUAL{RESET}            : {WHITE}{fmt_value(signal['actual'])}{RESET}", w))
    print(make_box_row(f"{CYAN}ANALYSIS MODE{RESET}     : {DIM}{signal['source']}{RESET}", w))
    print(f"{ORANGE}├{'─' * (w-2)}┤{RESET}")

    print(make_box_row(f"{CYAN}CONFIDENCE METER{RESET}  : {meter(signal['confidence'])}", w))
    print(f"{ORANGE}├{'─' * (w-2)}┤{RESET}")

    action_text = f"{dir_color}{BOLD}{direction} / {'BUY' if direction == 'CALL' else 'SELL'} / {'BULLISH' if direction == 'CALL' else 'BEARISH'}{RESET}"
    print(make_box_row(f"{CYAN}TRADE DIRECTION{RESET}   : {action_text}", w))
    print(f"{ORANGE}├{'─' * (w-2)}┤{RESET}")

    print(make_box_row(f"{CYAN}ENTRY TIME{RESET}        : {GREEN}{local_dt(signal['entry_time'])}{RESET}", w))
    print(make_box_row(f"{CYAN}EXPIRY TIME{RESET}       : {GREEN}{local_dt(signal['expiry_time'])}{RESET}", w))
    print(f"{ORANGE}├{'─' * (w-2)}┤{RESET}")

    print(make_box_row(f"{RED}{BOLD}⚠ RISK WARNING:{RESET} {YELLOW}News trading carries high volatility risk.{RESET}", w))
    print(f"{ORANGE}└{'─' * (w-2)}┘{RESET}")


def export_selected_signal(signal: Dict[str, Any]) -> str:
    filename = "NEXORA_NEWS_SIGNALS.json"
    payload = {
        "provider": APP_NAME,
        "version": VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "signal": {}
    }
    row = dict(signal)
    for k in ("event_time", "entry_time", "expiry_time"):
        if row.get(k):
            row[k] = row[k].isoformat()
    payload["signal"] = row

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return filename


# ------------------------------------------------
# MAIN PIPELINE
# ------------------------------------------------

def run_engine() -> None:
    clear_screen()
    banner()

    now_bd = datetime.now(UTC_PLUS_6).strftime("%a, %d %b %Y %H:%M:%S")
    print(f"{DIM}  SYSTEM TIME : {now_bd}  |  ZONE : UTC +06:00 (BD){RESET}")

    section("INITIALIZING NEXORA ENGINE")
    loading_animation("Connecting to Economic Calendar API", 0.5)

    try:
        events, active_url = fetch_calendar()
        print(f"{GREEN}  ✓ Connected to API:{RESET} {DIM}{active_url}{RESET}")
    except Exception as exc:
        print(f"\n{RED}  ✗ API CONNECTION FAILED:{RESET} {exc}")
        return

    progress_bar("Normalizing & Analyzing Calendar Events", 20)
    upcoming = filter_upcoming(events)

    clear_screen()
    banner()
    print(f"{GREEN}  API STATUS : ONLINE{RESET}   {CYAN}EVENTS LOADED : {len(upcoming)}{RESET}")

    while True:
        print_events_hud(upcoming)

        print(f"\n{CYAN}{'═' * 80}{RESET}")
        print(f"{BOLD}{YELLOW}  Select event number to analyze  |  [R] Refresh Data  |  [Q] Exit{RESET}")
        print(f"{CYAN}{'═' * 80}{RESET}")

        choice = input("  Option: ").strip().lower()

        if choice == 'q':
            print(f"\n{MAGENTA}  NEXORA NEWS AI Exited.{RESET}\n")
            break

        if choice == 'r':
            loading_animation("Refreshing API Data", 0.5)
            try:
                events, _ = fetch_calendar()
                upcoming = filter_upcoming(events)
            except Exception as exc:
                print(f"{RED}  Refresh error: {exc}{RESET}")
                sleep_small(1)
            clear_screen()
            banner()
            continue

        try:
            idx = int(choice)
        except ValueError:
            print(f"{RED}  Invalid input! Select a number, R, or Q.{RESET}")
            sleep_small(1)
            continue

        if idx < 1 or idx > len(upcoming):
            print(f"{RED}  Out of range! Choose between 1 and {len(upcoming)}.{RESET}")
            sleep_small(1)
            continue

        selected = upcoming[idx - 1]
        analysis = analyze_event(selected)
        signal = build_signal(analysis)

        if signal is None:
            print(f"\n{YELLOW}  No actionable signal generated for '{analysis['event']}'.{RESET}")
            print(f"{DIM}  (Confidence: {analysis['confidence']:.1f}% | Threshold: {MIN_CONFIDENCE}%){RESET}")
            sleep_small(2)
            clear_screen()
            banner()
            continue

        clear_screen()
        banner()
        print_signal_card(signal, idx)

        fn = export_selected_signal(signal)
        print(f"\n{GREEN}  ✓ Signal exported to {fn}{RESET}")

        input(f"\n{DIM}Press Enter to return to HUD...{RESET}")
        clear_screen()
        banner()


def main() -> None:
    try:
        run_engine()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}  Process interrupted by user.{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
