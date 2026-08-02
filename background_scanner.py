import os
import time
import io
import requests
import pandas as pd
import yfinance
from supabase import create_client

# Supabase Verbinding
SUPABASE_URL = "https://pokfjzgetwaxclfwfhpv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY ontbreekt in omgevingsvariabelen")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_unlimited_market_tickers():
    # Haalt een massieve lijst op van duizenden wereldwijde/Amerikaanse en Europese tickers
    urls = [
        "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt",
        "https://raw.githubusercontent.com/sven-seidel/all-stock-symbols/main/data/countries/Netherlands.txt",
        "https://raw.githubusercontent.com/sven-seidel/all-stock-symbols/main/data/countries/Germany.txt",
        "https://raw.githubusercontent.com/sven-seidel/all-stock-symbols/main/data/countries/France.txt"
    ]
    
    all_tickers = set()
    for url in urls:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                lines = response.text.splitlines()
                for t in lines:
                    t_clean = t.strip()
                    if t_clean and len(t_clean) <= 6:
                        all_tickers.add(t_clean)
        except:
            continue

    if not all_tickers:
        return ["AAPL", "MSFT", "GOOGL", "ASML.AS", "SAP", "TSM"]

    # Selecteer een willekeurige steekproef van 500 aandelen per dag voor een brede marktscan
    ticker_list = list(all_tickers)
    import random
    random.shuffle(ticker_list)
    return ticker_list[:500]

TARGET_TICKERS = get_unlimited_market_tickers()

def scan_and_save_single_stock(ticker_symbol):
    try:
        stock = yfinance.Ticker(ticker_symbol)
        info = stock.info

        current = info.get("currentPrice") or info.get("regularMarketPrice")
        if not current:
            return

        # 1. Upside berekenen
        target = info.get("targetMeanPrice")
        upside = ((target - current) / current) * 100 if target else 0.0

        # 2. ROE (Return on Equity) ophalen
        roe = info.get("returnOnEquity")
        if roe is None:
            roe = 0.10 # Conservatieve fallback

        # 3. ROE 5 jaar gemiddelde ophalen of schatten
        # Soms heeft yfinance 'fiveYearAvgReturn', anders gebruiken we de huidige ROE als veilige basis
        roe_5y_avg = info.get("fiveYearAvgReturn")
        if roe_5y_avg is None:
            roe_5y_avg = roe 
        else:
            # Soms geeft yfinance dit als percentage of decimaal, even normaliseren
            if roe_5y_avg > 1.0:
                roe_5y_avg = roe_5y_avg / 100.0

        ev_ebitda = info.get("enterpriseToEbitda")

        # Advies logica
        if roe >= 0.15 and (ev_ebitda is not None and ev_ebitda < 20) and upside > 5:
            advies = "🔥 TOP KOOPKANDIDAAT"
        elif roe >= 0.12:
            advies = "💎 Kwaliteit (Te Duur)"
        else:
            advies = "❌ Negeren"

        # Bepaal continent automatisch
        if any(ext in ticker_symbol for ext in [".AS", ".BR", ".PA", ".DE", ".L", ".SW", ".XPAR", ".XAMS"]):
            continent = "eu Europa"
        elif ticker_symbol in ["TSM", "BABA", "SONY", "TM", "TCEHY", "JD", "BIDU"]:
            continent = "asia Azië"
        else:
            continent = "us Noord-Amerika"

        data = {
            "ticker": ticker_symbol,
            "naam": info.get("longName", ticker_symbol),
            "advies": advies,
            "huidige_koers": float(current),
            "upside": float(upside),
            "ev_ebitda": float(ev_ebitda) if ev_ebitda else None,
            "roe": float(roe),
            "roe_5y_avg": float(roe_5y_avg),
            "continent": continent
        }

        # Opslaan in Supabase
        supabase.table("scanned_stocks").upsert(data).execute()
        
        if "TOP KOOPKANDIDAAT" in advies:
            print(f"🎯 PAREL: {ticker_symbol} | Koers: {current} | Upside: {upside:.1f}% | ROE: {roe*100:.1f}%")

    except Exception as e:
        pass

if __name__ == "__main__":
    print(f"🚀 Starten van wereldwijde scan met Upside & ROE (5v) voor {len(TARGET_TICKERS)} aandelen...")
    
    for idx, ticker in enumerate(TARGET_TICKERS):
        scan_and_save_single_stock(ticker)
        time.sleep(0.2)
        
    print("🏁 Wereldwijde scan succesvol afgerond!")
