import yfinance as yf
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Global Micro-Cap & Hidden Gems Screener", layout="wide")
st.title("🔍 Advanced Hidden Gems & Stock Screener")
st.write("Dit dashboard scant aandelen op potentie, risico (Altman Z) en toont nu ook Europese markten en koersgrafieken.")

# 1. UITBREIDING: Meer landen (Nederland & België toegevoegd)
CATEGORIES = {
    CATEGORIES = {
    "🇳🇱🇧🇪 Nederlandse & Belgische Topaandelen": [
        "ASML.AS", "INGA.AS", "ASRN.AS", "ADYEN.AS", "HEIA.AS", "UNA.AS", "AALB.AS", "RAND.AS",
        "UCB.BR", "KBC.BR", "SOLB.BR", "EVS.BR", "RECT.BR", "ACKB.BR", "SOF.BR", "UMIB.BR"
    ],
    "👑 Dividend Aristocrats (Veilig & Stabiel)": [
        "KO", "PEP", "PG", "JNJ", "MMM", "XOM", "CVX", "LOW", "TGT", "WMT", 
        "ABBV", "MO", "PM", "BEN", "GPC", "NUE", "SPGI", "GWW"
    ],
    "🇪🇺 Europese Groei- & Techparels": [
        "SAP.DE", "IFX.DE", "STMPA.PA", "RMS.PA", "MC.PA", "OR.PA", "EVO.ST", 
        "DSV.CO", "NOVO-B.CO", "ADEN.SW", "LONN.SW"
    ],
    "💎 Onbekende Amerikaanse Small-Caps (S&P 600)": [
        "AAL", "AAON", "CHEF", "EBF", "ENS", "FIZZ", "HELE", "HI", "KFRC", "LANC",
        "LECO", "MGEE", "MMS", "MOV", "MYRG", "NEOG", "OII", "OSIS", "PLPC", "POWI"
    ],
    "🌍 Europese 'Hidden Gems'": [
        "CNH", "FLS", "HAON.DE", "BOSS.DE", "PUM.DE", "JUVE.MI", "TOM2.AS", "POST.AS",
        "FAGR.ST", "ELUXB.ST", "NK.PA", "URW.AS"
    ]
}


selected_category = st.selectbox("Kies een aandelenlijst om te scannen:", list(CATEGORIES.keys()))
tickers = CATEGORIES[selected_category]

st.write(f"Aantal aandelen in deze selectie: **{len(tickers)}**")

min_upside = st.slider("Minimaal gewenste Upside (%)", min_value=-20, max_value=200, value=15)
only_safe = st.checkbox("Toon ALLEEN aandelen in de 🟢 Safe Zone (Altman Z > 2.99)", value=False)

if st.button("Start Geavanceerde Scan"):
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker_symbol in enumerate(tickers):
        status_text.text(f"Analyseren van {i+1}/{len(tickers)}: {ticker_symbol}...")
        progress_bar.progress((i + 1) / len(tickers))
        
        try:
            stock = yf.Ticker(ticker_symbol)
            info = stock.info
            
            target = info.get("targetMeanPrice")
            current = info.get("currentPrice") or info.get("regularMarketPrice", 1)
            if not target:
                continue
                
            upside = ((target - current) / current) * 100
            if upside < min_upside:
                continue
                
            bs = stock.balance_sheet
            fin = stock.financials
            if bs.empty or fin.empty:
                continue
                
            latest_bs = bs.iloc[:, 0]
            latest_fin = fin.iloc[:, 0]
            
            name = info.get("longName", ticker_symbol)
            sector = info.get("sector", "Onbekend")
            
            # 2. UITBREIDING: Extra financiële data ophalen
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
                "Huidige Koers": f"${current:.2f}" if not ticker_symbol.endswith(('.AS', '.BR', '.DE')) else f"€{current:.2f}",
                "Koersdoel": f"${target:.2f}" if not ticker_symbol.endswith(('.AS', '.BR', '.DE')) else f"€{target:.2f}",
                "Upside Potentieel": f"{upside:.1f}%",
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
        df['sort_col'] = df['Upside Potentieel'].str.rstrip('%').astype(float)
        df = df.sort_values(by="sort_col", ascending=False).drop(columns=['sort_col'])
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Geen aandelen gevonden die aan de criteria voldoen.")

# 3. UITBREIDING: Interactieve Grafieksectie onderaan
st.markdown("---")
st.subheader("📈 Bekijk Historische Koersgrafiek (1 Jaar)")
graph_ticker = st.selectbox("Selecteer een ticker voor de grafiek:", tickers)

if graph_ticker:
    try:
        stock_data = yf.Ticker(graph_ticker)
        # Haal de geschiedenis van 1 jaar op
        hist = stock_data.history(period="1y")
        if not hist.empty:
            # Toon een mooie interactieve lijnkaart van de sluitingskoersen
            st.line_chart(hist['Close'])
            st.write(f"Bovenstaande grafiek toont het koersverloop van **{graph_ticker}** over de afgelopen 12 maanden.")
        else:
            st.info("Geen historische koersdata beschikbaar voor deze ticker.")
    except Exception as e:
        st.error(f"Kon grafiek niet laden: {e}")
