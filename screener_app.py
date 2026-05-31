import yfinance as yf
import pandas as pd
import streamlit as st
import requests

st.set_page_config(page_title="Global Value Screener & Watchlist", layout="wide")

# --- INITIALISEER WATCHLIST IN HET GEHEUGEN ---
if 'watchlist' not in st.session_state:
    st.session_state['watchlist'] = []

st.title("🌐 Ultimate Global Stock Screener & Watchlist")

# We maken twee tabbladen: één om te scannen en één voor jouw persoonlijke volglijst
tab1, tab2 = st.tabs(["🚀 Markt Scanner", "⭐ Mijn Persoonlijke Watchlist"])

# --- STAP 1: LIVE DATABASE INLADEN ---
@st.cache_data(ttl=86400)
def get_all_global_tickers():
    try:
        us_url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
        us_tickers = requests.get(us_url).text.splitlines()
        
        eu_bases = ["ASML", "INGA", "ADYEN", "HEIA", "UNA", "RAND", "AALB", "UCB", "KBC", "SOLB", "SAP", "BMW", "MC", "OR", "BP", "GSK"]
        eu_tickers = []
        for base in eu_bases:
            eu_tickers.extend([f"{base}.AS", f"{base}.BR", f"{base}.DE", f"{base}.PA", f"{base}.L"])
            
        asia_tickers = ["TSM", "SONY", "TM", "BABA", "6758.T", "7203.T"]
        latam_tickers = ["VALE", "PBR", "MELI"]
        africa_tickers = ["GFI", "AU", "SBK.JO"]

        return {
            "🇺🇸 Noord-Amerika": sorted(list(set(us_tickers))),
            "🇪🇺 Europa": sorted(list(set(eu_tickers))),
            "🌏 Azië & Australië": sorted(list(set(asia_tickers))),
            "💃 Latijns-Amerika": sorted(list(set(latam_tickers))),
            "🌍 Afrika": sorted(list(set(africa_tickers)))
        }
    except Exception:
        return {"🇺🇸 Noord-Amerika": ["AAPL", "MSFT", "GOOGL"], "🇪🇺 Europa": ["ASML.AS", "INGA.AS"]}

global_database = get_all_global_tickers()

# --- FUNCTIONALITEIT VOOR HET OPHALEN VAN BEURSDATA ---
def scan_ticker_data(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        current = info.get("currentPrice") or info.get("regularMarketPrice")
        if not current: return None
            
        target = info.get("targetMeanPrice")
        upside = ((target - current) / current) * 100 if target else 0
        
        bs = stock.balance_sheet
        fin = stock.financials
        cf = stock.cashflow
        if bs.empty or fin.empty: return None
            
        latest_bs = bs.iloc[:, 0]
        latest_fin = fin.iloc[:, 0]
        
        market_cap = info.get("marketCap")
        enterprise_value = info.get("enterpriseValue")
        ev_ebitda = info.get("enterpriseToEbitda")
        
        free_cash_flow = info.get("freeCashflow") or (cf.iloc[0].get('Free Cash Flow') if not cf.empty else None)
        ev_fcf = enterprise_value / free_cash_flow if enterprise_value and free_cash_flow and free_cash_flow > 0 else None
            
        roe = info.get("returnOnEquity")
        roic = (latest_fin.get('EBIT', 0) * 0.75) / (info.get('totalDebt', 0) + latest_bs.get('Stockholders Equity', 1) - info.get('totalCash', 0)) if latest_fin.get('EBIT') else None

        if ticker_symbol.endswith(('.AS', '.BR', '.DE', '.PA')): valuta = "€"
        elif ticker_symbol.endswith('.L'): valuta = "£"
        else: valuta = "$"

        return {
            "Ticker": ticker_symbol,
            "Naam": info.get("longName", ticker_symbol),
            "Huidige Koers": f"{valuta}{current:.2f}",
            "Koersdoel": f"{valuta}{target:.2f}" if target else "N/A",
            "Upside": f"{upside:.1f}%" if target else "N/A",
            "EV/EBITDA": f"{ev_ebitda:.1f}" if ev_ebitda else "N/A",
            "EV/FCF": f"{ev_fcf:.1f}" if ev_fcf else "N/A",
            "ROE (Huidig)": f"{roe * 100:.1f}%" if roe else "N/A",
            "ROIC": f"{roic * 100:.1f}%" if roic and roic > 0 else "N/A",
            "raw_upside": upside # Dit verborgen getal gebruiken we puur om mee te sorteren en filteren
        }
    except:
        return None

# ==========================================
# TAB 1: DE MARKT SCANNER
# ==========================================
with tab1:
    st.header("🔍 Scan de Wereldwijde Markten")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        selected_continent = st.selectbox("Kies een continent:", list(global_database.keys()))
        full_ticker_list = global_database[selected_continent]
        max_to_scan = st.number_input("Hoeveel aandelen wil je scannen?", min_value=5, max_value=50, value=15)
        
        # HIER ZAT HET PROBLEEM: De slider staat nu weer netjes op zijn plek
        min_upside = st.slider("Minimaal gewenste Upside (%)", min_value=-20, max_value=200, value=15)
    
    tickers_to_scan = full_ticker_list[:max_to_scan]
    
    if st.button(f"🚀 Start Mega Scan"):
        results = []
        progress_bar = st.progress(0)
        
        for i, ticker_symbol in enumerate(tickers_to_scan):
            progress_bar.progress((i + 1) / len(tickers_to_scan))
            data = scan_ticker_data(ticker_symbol)
            if data:
                # Filter toepassen van de slider:
                if data['raw_upside'] >= min_upside:
                    results.append(data)
                
        if results:
            df = pd.DataFrame(results)
            # Sorteer netjes op de verborgen 'raw_upside' waarde zodat de hoogste bovenaan staan
            df = df.sort_values(by="raw_upside", ascending=False).drop(columns=['raw_upside'])
            st.dataframe(df, use_container_width=True)
            st.session_state['last_scan_results'] = df
        else:
            st.warning("Geen resultaten gevonden die voldoen aan de minimale Upside.")

    # --- WATCHLIST TOEVOEG SECTIE ---
    st.markdown("---")
    st.subheader("⭐ Voeg een aandeel toe aan je Watchlist")
    
    suggestions = []
    if 'last_scan_results' in st.session_state:
        suggestions = st.session_state['last_scan_results']['Ticker'].tolist()
        
    ticker_to_add = st.selectbox("Selecteer een ticker om te volgen:", suggestions if suggestions else ["AAPL", "MSFT", "ASML.AS"])
    
    if st.button("➕ Voeg toe aan mijn Watchlist"):
        if ticker_to_add not in st.session_state['watchlist']:
            st.session_state['watchlist'].append(ticker_to_add)
            st.success(f"**{ticker_to_add}** is succesvol toegevoegd aan je volglijst!")
        else:
            st.info(f"**{ticker_to_add}** staat al in je volglijst.")

# ==========================================
# TAB 2: DE PERSOONLIJKE WATCHLIST
# ==========================================
with tab2:
    st.header("⭐ Jouw Geselecteerde Aandelen")
    st.write("De app volgt deze aandelen volledig automatisch en haalt bij elke opening de nieuwste live data op.")
    
    if not st.session_state['watchlist']:
        st.info("Je watchlist is nog leeg. Ga naar het tabblad 'Markt Scanner' om aandelen toe te voegen!")
    else:
        st.write(f"Aandelen in je volglijst: {', '.join(st.session_state['watchlist'])}")
        
        if st.button("🔄 Ververs Live Data van mijn Watchlist"):
            watchlist_results = []
            wl_progress = st.progress(0)
            
            for idx, ticker in enumerate(st.session_state['watchlist']):
                wl_progress.progress((idx + 1) / len(st.session_state['watchlist']))
                w_data = scan_ticker_data(ticker)
                if w_data:
                    watchlist_results.append(w_data)
                    
            if watchlist_results:
                w_df = pd.DataFrame(watchlist_results)
                if "raw_upside" in w_df.columns:
                    w_df = w_df.sort_values(by="raw_upside", ascending=False).drop(columns=['raw_upside'])
                st.session_state['watchlist_df'] = w_df
        
        if 'watchlist_df' in st.session_state:
            st.dataframe(st.session_state['watchlist_df'], use_container_width=True)
            
            st.markdown("---")
            st.subheader("📈 Snelgrafiek van je favorieten")
            wl_ticker_graph = st.selectbox("Kies een aandeel uit je watchlist voor de 1-jaars grafiek:", st.session_state['watchlist'], key="wl_graph")
            
            if wl_ticker_graph:
                try:
                    hist = yf.Ticker(wl_ticker_graph).history(period="1y")
                    if not hist.empty:
                        st.line_chart(hist['Close'])
                    else:
                        st.info("Geen grafiekdata.")
                except:
                    st.error("Fout bij laden grafiek.")
        else:
            st.write("Klik op de knop hierboven om de live data van je volglijst op te starten!")

        st.markdown("---")
        if st.button("🗑️ Watchlist Volledig Wissen"):
            st.session_state['watchlist'] = []
            if 'watchlist_df' in st.session_state:
                del st.session_state['watchlist_df']
            st.success("Je watchlist is volledig leeggemaakt!")
            st.rerun()
