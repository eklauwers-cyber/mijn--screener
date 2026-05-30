import yfinance as yf
import pandas as pd
import streamlit as st
import requests

st.set_page_config(page_title="Global Automated Stock Screener", layout="wide")
st.title("🌐 Live World Stock Screener (100% Automatisch)")
st.write("Dit dashboard haalt ELKE dag de meest actuele lijst van actieve aandelen op. Nieuwe aandelen worden automatisch toegevoegd, verdwenen aandelen automatisch gewist.")

# --- STAP 1: AUTOMATISCH ACTUELE AANDELEN OPHALEN VAN DE BEURS ---
@st.cache_data(ttl=86400) # De lijst wordt 1x per 24 uur ververst (86400 seconden)
def get_all_active_tickers():
    try:
        # We halen de officiële, live lijst van actieve Amerikaanse aandelen op via FTP/NASDAQ
        url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
        response = requests.get(url)
        us_tickers = response.text.splitlines()
        
        # We voegen handmatig de belangrijkste Europese extensies toe zodat het script weet dat ze bestaan
        # (yfinance heeft voor Europa altijd een extensie nodig zoals .AS voor Amsterdam of .BR voor Brussel)
        eu_bases = ["ASML", "INGA", "ADYEN", "HEIA", "UNA", "RAND", "AALB", "UCB", "KBC", "SOLB", "EVS", "RECT"]
        eu_tickers = [f"{t}.AS" for t in eu_bases] + [f"{t}.BR" for t in eu_bases if not t.endswith('A')]
        
        total_list = sorted(list(set(us_tickers + eu_tickers)))
        return total_list
    except Exception:
        # Back-up lijst voor het geval de externe server even offline is
        return ["ASML.AS", "INGA.AS", "AAPL", "MSFT", "GOOG", "AMZN", "KO", "PEP"]

# Haal de dynamische lijst op
all_tickers_list = get_all_active_tickers()

# --- STAP 2: INTERFACE BOUWEN ---
st.sidebar.header("⚙️ Instellingen")
st.sidebar.write(f"Totaal aantal actieve aandelen in database: **{len(all_tickers_list)}**")

# Laat de gebruiker filteren op beginletter om de lijst behapbaar te houden (anders crasht de browser op 10.000+ items)
letter_filter = st.sidebar.selectbox("Filter aandelen op beginletter:", ["Alles"] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))

if letter_filter != "Alles":
    filtered_tickers = [t for t in all_tickers_list if t.startswith(letter_filter)]
else:
    filtered_tickers = all_tickers_list[:200] # Toon er standaard maximaal 200 om het snel te houden

# Selectiebox waarin ALLE actuele aandelen ter wereld live doorzoekbaar zijn!
selected_tickers = st.multiselect(
    "Typ of kies de aandelen die je vandaag wilt scannen (Nieuwe aandelen staan hier automatisch tussen!):", 
    options=filtered_tickers,
    default=filtered_tickers[:5] # Selecteer er standaard alvast 5
)

min_upside = st.slider("Minimaal gewenste Upside (%)", min_value=-20, max_value=200, value=15)
only_safe = st.checkbox("Toon ALLEEN aandelen in de 🟢 Safe Zone (Altman Z > 2.99)", value=False)

# --- STAP 3: DE SCANNER ---
if st.button("Start Live Beursscan"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker_symbol in enumerate(selected_tickers):
        status_text.text(f"Live data ophalen voor {i+1}/{len(selected_tickers)}: {ticker_symbol}...")
        progress_bar.progress((i + 1) / len(selected_tickers))
        
        try:
            stock = yf.Ticker(ticker_symbol)
            info = stock.info
            
            current = info.get("currentPrice") or info.get("regularMarketPrice")
            # Als een aandeel van de beurs is gehaald, geeft yfinance geen koers meer terug. 
            # Dit zorgt ervoor dat we hem automatisch overslaan!
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
            
            # Altman Z-Score
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
                "Huidige Koers": f"${current:.2f}" if not ticker_symbol.endswith(('.AS', '.BR')) else f"€{current:.2f}",
                "Koersdoel": f"${target:.2f}" if target and not ticker_symbol.endswith(('.AS', '.BR')) else (f"€{target:.2f}" if target else "N/A"),
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
            df = df.sort_values(by="sort_col", ascending=False).drop(columns=['sort_col'])
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Geen resultaten gevonden voor deze selectie.")

# --- STAP 4: INTERACTIEVE GRAFIEK ONDERAAN ---
st.markdown("---")
st.subheader("📈 Bekijk Historische Koersgrafiek (1 Jaar)")
graph_ticker = st.selectbox("Selecteer een ticker voor de grafiek:", selected_tickers if selected_tickers else ["AAPL"])

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
