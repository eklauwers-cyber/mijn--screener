import yfinance as yf
import pandas as pd
import streamlit as st
import requests

st.set_page_config(page_title="Global Continent Stock Screener", layout="wide")
st.title("🌐 Automated Continent Stock Screener")
st.write("Selecteer simpelweg een continent. De app laadt automatisch de tickers en scant ze allemaal in één klik!")

# --- STAP 1: DYNAMISCHE LIJSTEN PER CONTINENT DEFINIËREN ---
@st.cache_data(ttl=86400) # Slaat de lijsten 24 uur op voor maximale snelheid
def get_tickers_by_continent():
    # Basis top-aandelen Noord-Amerika (Grote tech, consumenten, industrie, small-caps mix)
    na_tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NKE", "DIS", "SBUX",
        "KO", "PEP", "COST", "WMT", "PG", "JNJ", "PFE", "MRK", "UNH", "XOM",
        "CVX", "CAT", "DE", "GE", "MMM", "HON", "FEDEX", "UPS", "AMD", "INTC",
        "AAL", "AAON", "CHEF", "EBF", "ENS", "FIZZ", "HELE", "HI", "KFRC", "LANC",
        "LECO", "MGEE", "MMS", "MOV", "MYRG", "NEOG", "OII", "OSIS", "PLPC", "POWI"
    ]
    
    # Basis top-aandelen Europa (Nederland, België, Duitsland, Frankrijk, Zweden mix)
    eu_tickers = [
        "ASML.AS", "INGA.AS", "ASRN.AS", "ADYEN.AS", "HEIA.AS", "UNA.AS", "AALB.AS", "RAND.AS",
        "UCB.BR", "KBC.BR", "SOLB.BR", "EVS.BR", "RECT.BR", "ACKB.BR", "SOF.BR", "UMIB.BR",
        "SAP.DE", "IFX.DE", "HAON.DE", "BOSS.DE", "PUM.DE", "BMW.DE", "VOW3.DE",
        "MC.PA", "OR.PA", "RMS.PA", "NK.PA", "SAN.PA",
        "EVO.ST", "FAGR.ST", "ELUXB.ST", "VOLVB.ST",
        "CNH", "FLS", "JUVE.MI", "TOM2.AS", "POST.AS", "URW.AS"
    ]
    
    return {
        "🇺🇸 Noord-Amerika (Top & Small-Caps Mix)": sorted(list(set(na_tickers))),
        "🇪🇺 Europa (Inclusief NL & BE Parels)": sorted(list(set(eu_tickers)))
    }

# Haal de continent-mappen op
continent_data = get_tickers_by_continent()

# --- STAP 2: INTERFACE (GEEN TICKERS INTYPEN) ---
st.sidebar.header("⚙️ Continent Selectie")

# De gebruiker kiest nu simpelweg een continent uit de dropdown
selected_continent = st.sidebar.selectbox("Kies het continent dat je wilt scannen:", list(continent_data.keys()))
tickers_to_scan = continent_data[selected_continent]

st.sidebar.write(f"Aantal aandelen in deze continent-scan: **{len(tickers_to_scan)}**")

# Filters
min_upside = st.slider("Minimaal gewenste Upside (%)", min_value=-20, max_value=200, value=15)
only_safe = st.checkbox("Toon ALLEEN aandelen in de 🟢 Safe Zone (Altman Z > 2.99)", value=False)

# --- STAP 3: DE GEAUTOMATISEERDE CONTINENT SCANNER ---
if st.button(f"🚀 Start Mega Scan voor {selected_continent}"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker_symbol in enumerate(tickers_to_scan):
        status_text.text(f"Beursdata ophalen ({i+1}/{len(tickers_to_scan)}): {ticker_symbol}...")
        progress_bar.progress((i + 1) / len(tickers_to_scan))
        
        try:
            stock = yf.Ticker(ticker_symbol)
            info = stock.info
            
            current = info.get("currentPrice") or info.get("regularMarketPrice")
            if not current:
                continue
                
            target = info.get("targetMeanPrice")
            upside = ((target - current) / current) * 100 if target else 0
            
            # Filter direct op minimale upside
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
            
            # Altman Z-Score Berekening
            total_assets = latest_bs.get('Total Assets', 1)
            working_capital = latest_bs.get('Current Assets', 0) - latest_bs.get('Current Liabilities', 0)
            retained_earnings = latest_bs.get('Retained Earnings', 0)
            ebit = latest_fin.get('EBIT') or latest_fin.get('Operating Income', 0)
            market_cap = info.get('marketCap', 1)
            total_liab = latest_bs.get('Total Liabilities', 1)
            revenue = latest_fin.get('Total Revenue', 1)
            
            X1 = working_capital / total_assets
            X2 = retained_earnings / total_assets
            X3 = ebit / total_assets
            X4 = market_cap / total_liab
            X5 = revenue / total_assets
            
            z_score = (1.2 * X1) + (1.4 * X2) + (3.3 * X3) + (0.6 * X4) + (0.99 * X5)
            
            if sector == "Financials":
                status = "N/A (Bank/Financieel)"
            elif z_score > 2.99:
                status = "🟢 Safe Zone"
            elif 1.81 <= z_score <= 2.99:
                status = "🟡 Grey Zone"
            else:
                status = "🔴 Value Trap!"
            
            if only_safe and z_score <= 2.99:
                continue
                
            results.append({
                "Ticker": ticker_symbol,
                "Naam": name,
                "Sector": sector,
                "Huidige Koers": f"${current:.2f}" if not ticker_symbol.endswith(('.AS', '.BR', '.DE', '.PA', '.ST', '.SW')) else f"€{current:.2f}",
                "Koersdoel": f"${target:.2f}" if target and not ticker_symbol.endswith(('.AS', '.BR', '.DE', '.PA', '.ST', '.SW')) else (f"€{target:.2f}" if target else "N/A"),
                "Upside Potentieel": f"{upside:.1f}%" if target else "N/A",
                "K/W Verhouding (P/E)": pe_str,
                "Dividend Rendement": div_str,
                "Altman Z-Score": f"{z_score:.2f}",
                "Risiko Status": status
            })
        except Exception:
            pass
            
    status_text.text("Scan voltooid!")
    
    if results:
        df = pd.DataFrame(results)
        if "Upside Potentieel" in df.columns and not df['Upside Potentieel'].isin(['N/A']).all():
            df['sort_col'] = df['Upside Potentieel'].str.rstrip('%').replace('N/A', -999).astype(float)
            # Sorteer direct op de hoogste potentie bovenaan!
            df = df.sort_values(by="sort_col", ascending=False).drop(columns=['sort_col'])
        st.dataframe(df, use_container_width=True)
        
        # Sla de succesvolle resultaten op in de 'session state' voor de grafiek hieronder
        st.session_state['scan_results'] = df
    else:
        st.warning("Geen aandelen gevonden in dit continent die voldoen aan je filters.")

# --- STAP 4: DYNAMISCHE GRAFIEK ONDERAAN VANUIT DE RESULTATEN ---
st.markdown("---")
st.subheader("📈 Bekijk Historische Koersgrafiek (1 Jaar)")

# De grafiek selectiebox kijkt nu slim naar de aandelen die daadwerkelijk uit de scan zijn gerold!
if 'scan_results' in st.session_state and not st.session_state['scan_results'].empty():
    available_tickers = st.session_state['scan_results']['Ticker'].tolist()
else:
    available_tickers = tickers_to_scan[:5]

graph_ticker = st.selectbox("Kies een gescand aandeel om de grafiek te bekijken:", available_tickers)

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
