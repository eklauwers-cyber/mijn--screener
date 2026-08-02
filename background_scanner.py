import yfinance as yf
import pandas as pd
import requests
import time
import os
from supabase import create_client

# Supabase Verbinding via Omgevingsvariabelen (opgehaald uit GitHub Secrets)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials niet gevonden in omgevingsvariabelen!")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Belangrijkste Wereldwijde Tickers om op de achtergrond te scannen
TARGET_TICKERS = [
    # Europa
    "ASML.AS", "SHELL.AS", "INGA.AS", "ABI.BR", "KBC.BR", "UCB.BR", "SAP", "MC.PA", "OR.PA", "TTE.PA", "NESN.SW", "NOVN.SW",
    # VS Tech & Dividend
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JNJ", "V", "PG", "JPM", "UNH", "HD", "MA", "BAC", "PFE",
    # Azië & Overig
    "TSM", "BABA", "SONY", "TM"
]

def scan_and_save_single_stock(ticker_symbol):
    try:
        print(f"Scannen van {ticker_symbol}...")
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        current = info.get("currentPrice") or info.get("regularMarketPrice")
        if not current: return
            
        target = info.get("targetMeanPrice")
        upside = ((target - current) / current) * 100 if target else 0
        
        bs = stock.balance_sheet
        fin = stock.financials
        if bs.empty or fin.empty: return
            
        ev_ebitda = info.get("enterpriseToEbitda")
        roe = info.get("returnOnEquity") or 0
        
        roe_5y_avg = 0
        if 'Net Income' in fin.index:
            historical_roes = []
            for col in range(min(len(bs.columns), len(fin.columns))):
                net_inc = fin.iloc[:, col].get('Net Income', 0)
                equity = bs.iloc[:, col].get('Stockholders Equity') or bs.iloc[:, col].get('Total Stockholders Equity', 1)
                if equity and equity > 0: historical_roes.append(net_inc / equity)
            if len(historical_roes) > 0: roe_5y_avg = sum(historical_roes[:5]) / min(len(historical_roes), 5)

        is_high_quality = (roe >= 0.15) and (roe_5y_avg >= 0.15)
        is_fairly_priced = (ev_ebitda and ev_ebitda < 25)
        
        if is_high_quality and is_fairly_priced and upside > 0: advies = "🔥 TOP KOOPKANDIDAAT"
        elif is_high_quality and not is_fairly_priced: advies = "💎 Kwaliteit (Te Duur)"
        else: advies = "❌ Negeren"

        continent = "🇪🇺 Europa" if ".AS" in ticker_symbol or ".BR" in ticker_symbol or ".PA" in ticker_symbol else "🇺🇸 Noord-Amerika"

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
        print(f"✅ Opgeslagen: {ticker_symbol} ({advies})")
        
    except Exception as e:
        print(f"❌ Fout bij {ticker_symbol}: {e}")

if __name__ == "__main__":
    for ticker in TARGET_TICKERS:
        scan_and_save_single_stock(ticker)
        time.sleep(1) # Pauze om Rate Limits van Yahoo te voorkomen
