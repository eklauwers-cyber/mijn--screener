import yfinance as yf
import pandas as pd
import streamlit as st
import requests
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Global Value Screener & Portfolio Simulator", layout="wide")

# --- PERMANENTE OPSLAG IMPLEMENTATIE (JSON DATABASE) ---
DATA_FILE = "user_data.json"

def load_user_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "watchlist": [],
        "portfolio_cash": 20000.0,
        "portfolio_shares": {}
    }

def save_user_data():
    data = {
        "watchlist": st.session_state['watchlist'],
        "portfolio_cash": st.session_state['portfolio_cash'],
        "portfolio_shares": st.session_state['portfolio_shares']
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if 'initialized' not in st.session_state:
    saved_data = load_user_data()
    st.session_state['watchlist'] = saved_data.get("watchlist", [])
    st.session_state['portfolio_cash'] = saved_data.get("portfolio_cash", 20000.0)
    st.session_state['portfolio_shares'] = saved_data.get("portfolio_shares", {})
    st.session_state['initialized'] = True

st.title("🌐 Ultimate Screener & Simulator (€ 20.000)")

tab1, tab2, tab3 = st.tabs(["🚀 Markt Scanner", "⭐ Watchlist", "💼 Fictieve Portefeuille (€20k)"])

# --- STAP 1: DATABASE INLADEN ---
@st.cache_data(ttl=86400)
def get_all_global_tickers():
    try:
        us_url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
        us_tickers = requests.get(us_url).text.splitlines()
        
        eu_bases = [
            "AALB", "ABI", "ACKB", "ADYEN", "AGN", "AIR", "ALV", "AMG", "ASML", "ASRNL", "BESI", "BNP", "BP", "BSGR",
            "COLR", "CPR", "DSM", "DTE", "ENEL", "EXOR", "FLOW", "GSK", "HEIA", "INGA", "KBC", "LIGHT", "MC", "NN",
            "NOVN", "NWG", "OR", "PHI", "PRX", "RAND", "REN", "ROG", "SAN", "SAP", "SBMO", "SHELL", "SIE", "SOLB",
            "TTE", "UCB", "UNA", "VNA", "VPK", "WKL"
        ]
        eu_tickers = [f"{base}.AS" for base in eu_bases]
        asia_tickers = ["BABA", "BIDU", "9984.T", "7267.T", "6758.T", "SONY", "TM", "TSM"]

        return {
            "🇺🇸 Noord-Amerika": sorted(list(set(us_tickers))),
            "🇪🇺 Europa": sorted(list(set(eu_tickers))),
            "🌏 Azië": sorted(list(set(asia_tickers)))
        }
    except Exception:
        return {"🇺🇸 Noord-Amerika": ["AAPL", "AMZN", "BAC", "CSCO"], "🇪🇺 Europa": ["AALB.AS", "ASML.AS", "BESI.AS"]}

global_database = get_all_global_tickers()

# --- BEURSDATA OPHALEN & ANALYSEREN ---
def scan_ticker_data(ticker_symbol):
    try:
        # Korte time.sleep om Yahoo Rate Limits te voorkomen
        time.sleep(0.05)
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        current = info.get("currentPrice") or info.get("regularMarketPrice")
        if not current: return None
            
        target = info.get("targetMeanPrice")
        upside = ((target - current) / current) * 100 if target else 0
        
        bs = stock.balance_sheet
        fin = stock.financials
        if bs.empty or fin.empty: return None
            
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

        return {
            "Ticker": ticker_symbol,
            "Naam": info.get("longName", ticker_symbol),
            "Systeem Advies": advies,
            "Huidige Koers Raw": current,
            "Huidige Koers": f"€{current:.2f}",
            "Upside": f"{upside:.1f}%" if target else "N/A",
            "EV/EBITDA": f"{ev_ebitda:.1f}" if ev_ebitda else "N/A",
            "ROE (Huidig)": f"{roe * 100:.1f}%",
            "ROE 5Y Avg": f"{roe_5y_avg * 100:.1f}%",
            "raw_upside": upside,
            "raw_advies": advies
        }
    except Exception:
        return None

# ==========================================
# TAB 1: MARKT SCANNER
# ==========================================
with tab1:
    st.header("🔍 Slimme Markt Scanner")
    
    col_cont, col_alpha, col_max = st.columns(3)
    
    with col_cont:
        selected_continent = st.selectbox("1. Kies een continent:", list(global_database.keys()))
    
    # Maak fijnmazigere letterkeuzes per enkele/dubbele letter om blokkades te vermijden
    alphabet_options = ["Alle Letters", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
    
    with col_alpha:
        selected_letter = st.selectbox("2. Kies een Beginletter:", alphabet_options)
        
    with col_max:
        max_scan_count = st.slider("3. Max. aantal te scannen aandelen:", min_value=10, max_value=300, value=50, step=10)
        
    all_tickers_in_cont = global_database[selected_continent]
    
    if selected_letter != "Alle Letters":
        filtered_tickers = [t for t in all_tickers_in_cont if t.startswith(selected_letter)]
    else:
        filtered_tickers = all_tickers_in_cont

    st.info(f"📍 Er zijn **{len(filtered_tickers)}** aandelen met beginletter **'{selected_letter}'**. (Er worden er maximaal **{min(max_scan_count, len(filtered_tickers))}** gescand om blokkades te voorkomen).")
    
    only_show_best = st.checkbox("🎯 Toon ALLEEN de '🔥 TOP KOOPKANDIDATEN'", value=False)
    
    if st.button("🚀 Scan Selectie"):
        tickers_to_scan = filtered_tickers[:max_scan_count]
        
        if len(tickers_to_scan) == 0:
            st.warning("Geen aandelen gevonden voor deze filter.")
        else:
            results = []
            progress_bar = st.progress(0)
            
            # Verlaagd naar max_workers=3 om Rate Limit te vermijden
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(scan_ticker_data, t) for t in tickers_to_scan]
                for i, future in enumerate(futures):
                    data = future.result()
                    progress_bar.progress((i + 1) / len(tickers_to_scan))
                    if data:
                        if only_show_best and data['raw_advies'] != "🔥 TOP KOOPKANDIDAAT": continue
                        results.append(data)
                    
            if results:
                df = pd.DataFrame(results)
                st.session_state['last_scan_results'] = df
                st.dataframe(df.drop(columns=['raw_upside', 'raw_advies', 'Huidige Koers Raw']), use_container_width=True)
            else:
                st.warning("Geen resultaten gevonden voor deze criteria (of Yahoo blokkeert tijdelijk verzoeken). Probeer het over een minuutje weer.")

    st.markdown("---")
    st.subheader("🛒 Virtueel Beleggen met je € 20.000 Budget")
    
    has_results = 'last_scan_results' in st.session_state and not st.session_state['last_scan_results'].empty
    
    if has_results:
        suggestions = st.session_state['last_scan_results']['Ticker'].tolist()
        selected_buy_ticker = st.selectbox("Kies een aandeel om te kopen uit je scanningsresultaten:", suggestions)
        buy_amount = st.number_input("Hoeveel euro wil je in dit aandeel steken?", min_value=100.0, max_value=20000.0, value=2000.0, step=500.0)
        
        if st.button("💰 Koop Aandeel voor Portefeuille"):
            if buy_amount > st.session_state['portfolio_cash']:
                st.error("Je hebt niet genoeg virtueel cashgeld meer over!")
            else:
                # Gebruik de reeds opgehaalde koers uit de tabel in plaats van een nieuwe verzoek naar Yahoo
                scan_df = st.session_state['last_scan_results']
                selected_row = scan_df[scan_df['Ticker'] == selected_buy_ticker].iloc[0]
                price = selected_row['Huidige Koers Raw']
                
                shares_bought = buy_amount / price
                st.session_state['portfolio_cash'] -= buy_amount
                
                if selected_buy_ticker in st.session_state['portfolio_shares']:
                    st.session_state['portfolio_shares'][selected_buy_ticker]['aantal'] += shares_bought
                    st.session_state['portfolio_shares'][selected_buy_ticker]['totaal_belegd'] += buy_amount
                else:
                    st.session_state['portfolio_shares'][selected_buy_ticker] = {
                        'aantal': shares_bought,
                        'gem_aankoopkoers': price,
                        'totaal_belegd': buy_amount
                    }
                save_user_data()
                st.success(f"Gefeliciteerd! Je hebt virtueel **{shares_bought:.2f} aandelen {selected_buy_ticker}** gekocht!")
    else:
        st.info("Voer eerst een scan uit hierboven om aandelen te kunnen kopen.")

# ==========================================
# TAB 2: WATCHLIST
# ==========================================
with tab2:
    st.header("⭐ Watchlist")
    st.write("Aandelen in je watchlist blijven hier permanent bewaard.")
    
    if 'last_scan_results' in st.session_state and not st.session_state['last_scan_results'].empty:
        suggestions = st.session_state['last_scan_results']['Ticker'].tolist()
        ticker_to_wl = st.selectbox("Kies aandeel uit de scan voor je watchlist:", suggestions)
        if st.button("➕ Voeg toe aan Watchlist"):
            if ticker_to_wl not in st.session_state['watchlist']:
                st.session_state['watchlist'].append(ticker_to_wl)
                save_user_data()
                st.success(f"{ticker_to_wl} opgeslagen in je watchlist!")
    else:
        st.info("Voer eerst een scan uit op het eerste tabblad om aandelen aan de watchlist toe te voegen.")
            
    st.write("Mijn gevolgde aandelen:", st.session_state['watchlist'])

# ==========================================
# TAB 3: PORTEFEUILLE (PERMANENT)
# ==========================================
with tab3:
    st.header("💼 Jouw Permanente Virtuele Portefeuille")
    
    current_invested_value = 0.0
    portfolio_rows = []
    
    for ticker, pos in st.session_state['portfolio_shares'].items():
        try:
            live_price = yf.Ticker(ticker).info.get("currentPrice", pos['gem_aankoopkoers'])
        except Exception:
            live_price = pos['gem_aankoopkoers']
            
        live_val = pos['aantal'] * live_price
        winst_verlies = live_val - pos['totaal_belegd']
        winst_verlies_pct = (winst_verlies / pos['totaal_belegd']) * 100
        
        current_invested_value += live_val
        portfolio_rows.append({
            "Ticker": ticker,
            "Aantal Aandelen": f"{pos['aantal']:.2f}",
            "Aankoopwaarde": f"€{pos['totaal_belegd']:.2f}",
            "Huidige Waarde": f"€{live_val:.2f}",
            "Winst / Verlies (€)": f"€{winst_verlies:.2f}",
            "Rendement (%)": f"{winst_verlies_pct:.2f}%"
        })
        
    totale_portefeuille_waarde = st.session_state['portfolio_cash'] + current_invested_value
    totale_winst = totale_portefeuille_waarde - 20000.0
    totaal_rendement = (totale_winst / 20000.0) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Totale Portefeuille Waarde", f"€ {totale_portefeuille_waarde:,.2f}", f"{totaal_rendement:.2f}%")
    c2.metric("Beschikbaar Cashgeld", f"€ {st.session_state['portfolio_cash']:,.2f}")
    c3.metric("Totaal Belegd Vermogen", f"€ {current_invested_value:,.2f}")
    
    st.markdown("---")
    if portfolio_rows:
        st.subheader("📊 Investeringen Overzicht")
        st.dataframe(pd.DataFrame(portfolio_rows), use_container_width=True)
    else:
        st.info("Je hebt nog geen aandelen gekocht. Ga naar de Markt Scanner om een aandeel te kopen!")
        
    if st.button("🔄 Reset Portefeuille (Terug naar €20.000 Cash)"):
        st.session_state['portfolio_cash'] = 20000.0
        st.session_state['portfolio_shares'] = {}
        st.session_state['watchlist'] = []
        save_user_data()
        st.rerun()
                
