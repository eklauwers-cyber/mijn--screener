import os
import time
import yfinance as yf
from supabase import create_client


# Supabase Verbinding
SUPABASE_URL = "https://pokfjzgetwaxclfwfhpv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials niet gevonden in omgevingsvariabelen!")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Belangrijkste Wereldwijde Tickers
TARGET_TICKERS = [
    "ASML.AS", "SHELL.AS", "INGA.AS", "ABI.BR", "KBC.BR", "UCB.BR", "SAP", "MC.PA",
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JNJ", "V"
]

def scan_and_save_single_stock(ticker_symbol):
    try:
        print(f"Scannen van {ticker_symbol}...")
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        current = info.get("currentPrice") or info.get("regularMarketPrice")
        if not current: 
            print(f"⚠️ Geen koers gevonden voor {ticker_symbol}")
            return
            
        target = info.get("targetMeanPrice")
        upside = ((target - current) / current) * 100 if target else 0
        
        ev_ebitda = info.get("enterpriseToEbitda")
        roe = info.get("returnOnEquity") or 0
        
        # Simpele kwaliteitscheck om crashes te voorkomen
        is_high_quality = (roe >= 0.15)
        is_fairly_priced = (ev_ebitda is not None and ev_ebitda < 25)
        
        if is_high_quality and is_fairly_priced and upside > 0:
            advies = "🔥 TOP KOOPKANDIDAAT"
        elif is_high_quality:
            advies = "💎 Kwaliteit (Te Duur)"
        else:
            advies = "❌ Negeren"

        continent = "🇪🇺 Europa" if any(ext in ticker_symbol for ext in [".AS", ".BR", ".PA"]) else "🇺🇸 Noord-Amerika"

        data = {
            "ticker": ticker_symbol,
            "naam": info.get("longName", ticker_symbol),
            "advies": advies,
            "huidige_koers": float(current),
            "upside": float(upside),
            "ev_ebitda": float(ev_ebitda) if ev_ebitda else None,
            "roe": float(roe),
            "roe_5y_avg": float(roe), # Vereenvoudigd voor stabiliteit
            "continent": continent
        }
        
        # Opslaan in Supabase
        supabase.table("scanned_stocks").upsert(data).execute()
        print(f"✅ Opgeslagen: {ticker_symbol} ({advies})")
        
    except Exception as e:
        print(f"❌ Fout bij {ticker_symbol}: {e}")

if __name__ == "__main__":
    print("🚀 Starten van achtergrondscan...")
    for ticker in TARGET_TICKERS:
        scan_and_save_single_stock(ticker)
        time.sleep(1)
    print("🎉 Scan succesvol afgerond!")
