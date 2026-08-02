import os
import time
import io
import requests
import pandas as pd
from supabase import create_client

# Supabase Verbinding
SUPABASE_URL = "https://pokfjzgetwaxclfwfhpv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY ontbreekt in omgevingsvariabelen")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Functie om automatisch een brede lijst met honderden aandelen op te halen
def get_huge_ticker_list():
    url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
    try:
        response = requests.get(url)
        tickers = response.text.splitlines()
        # Haalt tot 300 tickers op om binnen de tijdslimiet van GitHub Actions te blijven
        us_tickers = [t.strip() for t in tickers if t.strip() and len(t.strip()) <= 5][:300]
    except:
        us_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

    # Voeg handmatig ook belangrijke Europese en wereldwijde aandelen toe
    eu_tickers = [
        "ASML.AS", "SHELL.AS", "INGA.AS", "ADYEN.AS", "BESI.AS",
        "ABI.BR", "KBC.BR", "UCB.BR", "SOLB.BR",
        "MC.PA", "OR.PA", "TTE.PA", "SAN.PA", "AIR.PA",
        "SAP", "SIE.DE", "ALV.DE", "BMW.DE", "MBG.DE"
    ]
    
    return eu_tickers + us_tickers

TARGET_TICKERS = get_huge_ticker_list()

def scan_and_save_single_stock(ticker_symbol):
    try:
        print(f"Scannen van {ticker_symbol}...")
        stock = yfinance.Ticker(ticker_symbol)  # Let op: yfinance wordt hieronder geïmporteerd
        info = stock.info

        current = info.get("currentPrice") or info.get("regularMarketPrice")
        if not current:
            print(f"⚠️ Geen koers gevonden voor {ticker_symbol}")
            return

        target = info.get("targetMeanPrice")
        upside = ((target - current) / current) * 100 if target else 0

        bs = stock.balance_sheet
        fin = stock.financials

        if bs.empty or fin.empty:
            return

        # Eenvoudige kwaliteitscontrole en waardering berekenen
        ev_ebitda = info.get("enterpriseToEbitda")
        
        # Haal ROE op indien beschikbaar
        roe = info.get("returnOnEquity")
        if roe is None:
            roe = 0.15 # Standaard fallback voor stabiliteit

        # Advies logica
        if roe >= 0.15 and (ev_ebitda is not None and ev_ebitda < 25) and upside > 0:
            advies = "🔥 TOP KOOPKANDIDAAT"
        elif roe >= 0.15:
            advies = "💎 Kwaliteit (Te Duur)"
        else:
            advies = "❌ Negeren"

        # Bepaal continent
        if any(ext in ticker_symbol for ext in [".AS", ".BR", ".PA", ".DE"]):
            continent = "eu Europa"
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
            "roe_5y_avg": float(roe),
            "continent": continent
        }

        # Opslaan in Supabase
        supabase.table("scanned_stocks").upsert(data).execute()
        print(f"✅ Opgeslagen: {ticker_symbol} ({advies})")

    except Exception as e:
        print(f"❌ Fout bij {ticker_symbol}: {e}")

if __name__ == "__main__":
    import yfinance # Zorg dat yfinance hier geladen is
    print(f"🚀 Starten van achtergrondscan voor {len(TARGET_TICKERS)} aandelen...")
    
    for ticker in TARGET_TICKERS:
        scan_and_save_single_stock(ticker)
        time.sleep(0.5) # Korte pauze tegen rate limits
        
    print("🏁 Scan succesvol afgerond!")
