import yfinance as yf
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Global Micro-Cap & Hidden Gems Screener", layout="wide")
st.title("🔍 Hidden Gems & Small-Cap Value Screener")
st.write("Dit dashboard scant de minder bekende en micro-cap aandelen op zoek naar extreme upside en veilige balansen.")

# We breiden de categorieën uit met indices voor kleinere/onbekende bedrijven
CATEGORIES = {
    "💎 Onbekende Amerikaanse Small-Caps (S&P 600 selectie)": [
        "AAL", "AAON", "CHEF", "EBF", "ENS", "FIZZ", "HELE", "HI", "KFRC", "LANC",
        "LECO", "MGEE", "MMS", "MOV", "MYRG", "NEOG", "OII", "OSIS", "PLPC", "POWI",
        "RBC", "RGR", "SFBS", "SHEN", "SMP", "SPXC", "TREX", "UFPI", "VMI", "WMS"
    ],
    "🌍 Europese 'Hidden Gems' (Minder bekende mid/small caps)": [
        "CNH", "FLS", "HAON.DE", "BOSS.DE", "PUM.DE", "JUVE.MI", "TOM2.AS", "POST.AS",
        "FAGR.ST", "ELUXB.ST", "NK.PA", "URW.AS", "SOLB.BR", "EVS.BR", "RECT.BR"
    ],
    "🚀 Micro-Caps & Turnaround Kandidaten (Hoog Risico)": [
        "AOUT", "BCOV", "ELYM", "GENC", "JAKK", "LCUT", "MIND", "PRTS", "RELL", "SOHO",
        "TAST", "UEC", "VHC", "VUZI", "XPER"
    ]
}

selected_category = st.selectbox("Kies een Small-Cap lijst om te scannen:", list(CATEGORIES.keys()))
tickers = CATEGORIES[selected_category]

st.write(f"Aantal onbekende aandelen in deze selectie: **{len(tickers)}**")

# Belangrijk: Small-caps zijn volatieler, dus we zetten de filters scherper!
min_upside = st.slider("Minimaal gewenste Upside (%)", min_value=0, max_value=200, value=25)
only_safe = st.checkbox("Toon ALLEEN aandelen in de 🟢 Safe Zone (Altman Z > 2.99)", value=False)

if st.button("Start Hidden Gem Scan"):
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker_symbol in enumerate(tickers):
        status_text.text(f"Analyseren van small-cap {i+1}/{len(tickers)}: {ticker_symbol}...")
        progress_bar.progress((i + 1) / len(tickers))
        
        try:
            stock = yf.Ticker(ticker_symbol)
            info = stock.info
            
            # Snelkoppeling: als er geen analistendoel is, slaan we hem direct over
            target = info.get("targetMeanPrice")
            current = info.get("currentPrice") or info.get("regularMarketPrice", 1)
            if not target or target <= current:
                continue
                
            upside = ((target - current) / current) * 100
            
            # Filter direct op upside
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
            
            # Altman Z-Score berekening
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
                status = "🔴 Value Trap Gevaar!"
            
            # Filter voor de 'Alleen Veilige Aandelen' checkbox
            if only_safe and z_score <= 2.99:
                continue
                
            results.append({
                "Ticker": ticker_symbol,
                "Naam": name,
                "Sector": sector,
                "Huidige Koers": f"${current:.2f}",
                "Koersdoel": f"${target:.2f}",
                "Upside Potentieel": f"{upside:.1f}%",
                "Altman Z-Score": f"{z_score:.2f}",
                "Risiko Status": status
            })
        except Exception:
            pass
            
    status_text.text("Scan voltooid!")
    
    if results:
        df = pd.DataFrame(results)
        # Sorteer op de allerhoogste upside
        df['sort_col'] = df['Upside Potentieel'].str.rstrip('%').astype(float)
        df = df.sort_values(by="sort_col", ascending=False).drop(columns=['sort_col'])
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Geen onbekende pareltjes gevonden die aan de strenge criteria voldoen. Verlaag eventueel de minimale Upside.")