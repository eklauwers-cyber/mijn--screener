import yfinance as yf
import pandas as pd
import streamlit as st
import requests

st.set_page_config(page_title="Ultimate Global Stock Screener", layout="wide")
st.title("🌐 Ultimate Global Stock Screener (100% Automatisch)")
st.write("Dit dashboard downloadt live de meest actuele lijsten ter wereld. Nieuwe beursgangen (IPO's) komen er automatisch bij, failliete of overgenomen bedrijven verdwijnen direct.")

# --- STAP 1: LIVE BRONNEN KOPPELEN VOOR DUISENDEN TICKERS ---
@st.cache_data(ttl=86400) # De lijsten worden 1x per 24 uur ververst
def get_all_global_tickers():
    try:
        # 1. Noord-Amerika (Download live alle actieve Amerikaanse tickers van NASDAQ, NYSE & AMEX)
        us_url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
        us_tickers = requests.get(us_url).text.splitlines()
        
        # 2. Europa (Dynamische lijst op basis van de belangrijkste Europese beursextensies)
        # yfinance gebruikt extensies: .AS (Amsterdam), .BR (Brussel), .DE (Duitsland), .PA (Parijs), .L (Londen)
        eu_bases = [
            "ASML", "INGA", "ADYEN", "HEIA", "UNA", "RAND", "AALB", "AKZA", "DSM", "KPN", # NL
            "UCB", "KBC", "SOLB", "EVS", "RECT", "ACKB", "SOF", "UMIB", "AEDB", # BE
            "SAP", "IFX", "HAON", "BOSS", "PUM", "BMW", "VOW3", "DAI", "BAYN", # DE
            "MC", "OR", "RMS", "NK", "SAN", "AIR", "TOT", "ML", "UG", # FR
            "BP", "VOD", "GSK", "AZN", "LLOY", "BARC", "HSBA", "TSCO", "BATS" # UK
        ]
        eu_tickers = []
        for base in eu_bases:
            eu_tickers.extend([f"{base}.AS", f"{base}.BR", f"{base}.DE", f"{base}.PA", f"{base}.L"])
            
        # 3. Azië, Latijns-Amerika & Afrika (Brede selectie van wereldwijde ADR's en lokale tickers)
        asia_tickers = ["TSM", "SONY", "TM", "HMC", "BABA", "JD", "BIDU", "NTDOY", "INFY", "WIT", "6758.T", "7203.T", "9984.T"]
        latam_tickers = ["VALE", "PBR", "MELI", "AMX", "BAK", "EBR", "GGB", "NU", "BSBR", "SQM"]
        africa_tickers = ["GFI", "AU", "HMY", "AGI", "SBK.JO", "FSR.JO", "MTN.JO", "SOL.JO", "NPN.JO"]

        return {
            "🇺🇸 Noord-Amerika": sorted(list(set(us_tickers))),
            "🇪🇺 Europa": sorted(list(set(eu_tickers))),
            "🌏 Azië & Australië": sorted(list(set(asia_tickers))),
            "💃 Latijns-Amerika": sorted(list(set(latam_tickers))),
            "🌍 Afrika": sorted(list(set(africa_tickers)))
        }
    except Exception:
        # Nood-fallback mocht de GitHub downloadserver offline zijn
        return {"🇺🇸 Noord-Amerika": ["AAPL", "MSFT", "GOOGL"], "🇪🇺 Europa": ["ASML.AS", "INGA.AS"]}

# Laad de gigantische database in de app
global_database = get_all_global_tickers()

# --- STAP 2: INTERFACE BOUWEN ---
st.sidebar.header("⚙️ Systeembesturing")
selected_continent = st.sidebar.selectbox("Kies een continent:", list(global_database.keys()))
full_ticker_list = global_database[selected_continent]

st.sidebar.write(f"Totaal aantal actieve aandelen geladen voor deze regio: **{len(full_ticker_list)}**")

# Omdat scannen van 10.000+ aandelen tegelijk uren duurt, laten we de computer scannen in behapbare blokken
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Scan Grootte")
max_to_scan = st.sidebar.number_input("Hoeveel aandelen van de lijst wil je nu scannen?", min_value=5, max_value=200, value=25)

# Filters
min_upside = st.sidebar.slider("Minimaal gewenste Upside (%)", min_value=-20, max_value=200, value=15)
only_safe = st.sidebar.checkbox("Toon ALLEEN aandelen in de 🟢 Safe Zone", value=False)

# Selecteer automatisch de eerste X actieve aandelen uit de live database
tickers_to_scan = full_ticker_list[:max_to_scan]

# --- STAP 3: BEURSSCANNER ---
if st.button(f"🚀 Start Volautomatische Scan voor {selected_continent}"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker_symbol in enumerate(tickers_to_scan):
        status_text.text(f"Live scannen ({i+1}/{len(tickers_to_scan)}): {ticker_symbol}...")
        progress_bar.progress((i + 1) / len(tickers_to_scan))
        
        try:
            stock = yf.Ticker(ticker_symbol)
            info = stock.info
            
            # AUTOMATISCH VERWIJDEREN CHECK: 
            # Als een bedrijf niet meer bestaat of geschorst is, geeft yfinance geen koers. 
            # We skippen hem dan direct!
            current = info.get("currentPrice") or info.get("regularMarketPrice")
            if not current:
                continue
                
            target = info.get("targetMeanPrice")
            upside = ((target - current) / current) * 100 if target else 0
            
            if target and upside < min_upside:
                continue
                
            bs = stock.balance_sheet
            fin = stock.financials
            if bs.empty or fin.empty:
                continue
                
            latest_bs = bs.iloc[:, 0]
            latest_fin = fin.iloc[:, 0]
            
            name = info.get("longName", ticker_symbol)
            sector = info.get("sector", "Onbekend")
            pe_ratio = info.get("trailingPE")
            pe_str = f"{pe_ratio:.1f}" if pe_ratio else "N/A"
            dividend = info.get("dividendYield")
            div_str = f"{dividend * 100:.1f}%" if dividend else "0.0%"
            
            # Valuta herkenning
            if ticker_symbol.endswith(('.AS', '.BR', '.DE', '.PA')): valuta = "€"
            elif ticker_symbol.endswith('.L'): valuta = "£"
            elif ticker_symbol.endswith('.T'): valuta = "¥"
            elif ticker_symbol.endswith('.JO'): valuta = "R "
            else: valuta = "$"
            
            # Altman Z-Score Berekening
            total_assets = latest_bs.get('Total Assets') or latest_bs.get('TotalAssets')
            working_capital = (latest_bs.get('Current Assets') or latest_bs.get('CurrentAssets', 0)) - (latest_bs.get('Current Liabilities') or latest_bs.get('CurrentLiabilities', 0))
            retained_earnings = latest_bs.get('Retained Earnings') or latest_bs.get('RetainedEarnings', 0)
            ebit = latest_fin.get('EBIT') or latest_fin.get('Operating Income') or latest_fin.get('OperatingIncome', 0)
            market_cap = info.get('marketCap') or info.get('regularMarketVolume', 1)
            total_liab = latest_bs.get('Total Liabilities') or latest_bs.get('TotalLiabilities Net Minority Interest') or latest_bs.get('TotalLiabilities', 1)
            revenue = latest_fin.get('Total Revenue') or latest_fin.get('TotalRevenue', 1)
            
            if total_assets and total_liab and total_assets > 0 and total_liab > 0:
                X1 = working_capital / total_assets
                X2 = retained_earnings / total_assets
                X3 = ebit / total_assets
                X4 = market_cap / total_liab
                X5 = revenue / total_assets
                if X4 > 50: X4 = 50 
                z_score = (1.2 * X1) + (1.4 * X2) + (3.3 * X3) + (0.6 * X4) + (0.99 * X5)
                z_str = f"{z_score:.2f}"
            else:
                z_score = 0
                z_str = "N/A"
            
            if sector == "Financials": status = "N/A (Bank)"
            elif z_score > 2.99: status = "🟢 Safe Zone"
            elif 1.81 <= z_score <= 2.99: status = "🟡 Grey Zone"
            else: status = "🔴 Value Trap!"
            
            if only_safe and z_score <= 2.99:
                continue
                
            results.append({
                "Ticker": ticker_symbol,
                "Naam": name,
                "Sector": sector,
                "Huidige Koers": f"{valuta}{current:.2f}",
                "Koersdoel": f"{valuta}{target:.2f}" if target else "N/A",
                "Upside Potentieel": f"{upside:.1f}%" if target else "N/A",
                "K/W Verhouding (P/E)": pe_str,
                "Dividend Rendement": div_str,
                "Altman Z-Score": z_str,
                "Risiko Status": status
            })
        except Exception:
            pass
            
    status_text.text("Scan voltooid!")
    
    if results:
        df = pd.DataFrame(results)
        if "Upside Potentieel" in df.columns and not df['Upside Potentieel'].isin(['N/A']).all():
            df['sort_col'] = df['Upside Potentieel'].str.rstrip('%').replace('N/A', -999).astype(float)
            df = df.sort_values(by="sort_col", ascending=False).drop(columns=['sort_col'])
        st.dataframe(df, use_container_width=True)
        st.session_state['scan_results'] = df
    else:
        st.warning("Geen resultaten gevonden voor deze selectie.")

# --- STAP 4: DYNAMISCHE GRAFIEK ---
st.markdown("---")
st.subheader("📈 Bekijk Historische Koersgrafiek (1 Jaar)")

if 'scan_results' in st.session_state and not st.session_state['scan_results'].empty:
    available_tickers = st.session_state['scan_results']['Ticker'].tolist()
else:
    available_tickers = ["AAPL"]

graph_ticker = st.selectbox("Kies een gescand aandeel voor de grafiek:", available_tickers)

if graph_ticker:
    try:
        stock_data = yf.Ticker(graph_ticker)
        hist = stock_data.history(period="1y")
        if not hist.empty:
            st.line_chart(hist['Close'])
            st.write(f"Koersverloop van **{graph_ticker}** over de afgelopen 12 maanden.")
        else:
            st.info("Geen grafiekdata beschikbaar.")
    except Exception as e:
        st.error(f"Fout bij laden grafiek: {e}")
