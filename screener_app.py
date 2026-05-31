import yfinance as yf
import pandas as pd
import streamlit as st
import requests

st.set_page_config(page_title="Ultimate Global Value & Quality Screener", layout="wide")
st.title("🌐 Ultimate Global Value & Quality Screener")
st.write("Dit dashboard scant continenten op geavanceerde waardering (EV/EBITDA, EV/FCF) en kapitaalrendement (ROE, ROIC inclusief historie).")

# --- STAP 1: LIVE BRONNEN KOPPELEN ---
@st.cache_data(ttl=86400)
def get_all_global_tickers():
    try:
        us_url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
        us_tickers = requests.get(us_url).text.splitlines()
        
        eu_bases = [
            "ASML", "INGA", "ADYEN", "HEIA", "UNA", "RAND", "AALB", "AKZA", "KPN",
            "UCB", "KBC", "SOLB", "EVS", "RECT", "ACKB", "SOF", "UMIB",
            "SAP", "IFX", "HAON", "BOSS", "PUM", "BMW", "VOW3",
            "MC", "OR", "RMS", "NK", "SAN", "AIR",
            "BP", "VOD", "GSK", "AZN", "LLOY"
        ]
        eu_tickers = []
        for base in eu_bases:
            eu_tickers.extend([f"{base}.AS", f"{base}.BR", f"{base}.DE", f"{base".PA", f"{base}.L"])
            
        asia_tickers = ["TSM", "SONY", "TM", "HMC", "BABA", "JD", "NTDOY", "6758.T", "7203.T"]
        latam_tickers = ["VALE", "PBR", "MELI", "AMX", "SQM"]
        africa_tickers = ["GFI", "AU", "HMY", "SBK.JO", "MTN.JO", "SOL.JO"]

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

# --- STAP 2: INTERFACE ---
st.sidebar.header("⚙️ Systeembesturing")
selected_continent = st.sidebar.selectbox("Kies een continent:", list(global_database.keys()))
full_ticker_list = global_database[selected_continent]

st.sidebar.write(f"Totaal aantal aandelen in database: **{len(full_ticker_list)}**")

st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Scan Grootte")
max_to_scan = st.sidebar.number_input("Hoeveel aandelen wil je scannen?", min_value=5, max_value=100, value=15)

# Filters
min_upside = st.sidebar.slider("Minimaal gewenste Upside (%)", min_value=-20, max_value=200, value=15)
only_safe = st.sidebar.checkbox("Toon ALLEEN aandelen in de 🟢 Safe Zone", value=False)

tickers_to_scan = full_ticker_list[:max_to_scan]

# --- STAP 3: BEURSSCANNER ---
if st.button(f"🚀 Start Uitgebreide Waarde & Kwaliteit Scan"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker_symbol in enumerate(tickers_to_scan):
        status_text.text(f"Diepgaande analyse ({i+1}/{len(tickers_to_scan)}): {ticker_symbol}...")
        progress_bar.progress((i + 1) / len(tickers_to_scan))
        
        try:
            stock = yf.Ticker(ticker_symbol)
            info = stock.info
            
            current = info.get("currentPrice") or info.get("regularMarketPrice")
            if not current:
                continue
                
            target = info.get("targetMeanPrice")
            upside = ((target - current) / current) * 100 if target else 0
            if target and upside < min_upside:
                continue
                
            # Haal balans, winst-en-verlies en kasstroom op voor historische berekeningen
            bs = stock.balance_sheet
            fin = stock.financials
            cf = stock.cashflow
            
            if bs.empty or fin.empty:
                continue
                
            latest_bs = bs.iloc[:, 0]
            latest_fin = fin.iloc[:, 0]
            
            # --- NIEUWE CRITERIA LIVE OPHALEN & BEREKENEN ---
            market_cap = info.get("marketCap")
            enterprise_value = info.get("enterpriseValue")
            
            ev_ebitda = info.get("enterpriseToEbitda")
            fwd_ev_ebitda = info.get("forwardEbitda") # Soms berekend door YF, anders N/A
            
            # EV / Free Cash Flow handmatig berekenen voor nauwkeurigheid
            free_cash_flow = info.get("freeCashflow") or (cf.iloc[0].get('Free Cash Flow') if not cf.empty else None)
            if enterprise_value and free_cash_flow and free_cash_flow > 0:
                ev_fcf = enterprise_value / free_cash_flow
            else:
                ev_fcf = None
                
            # Return on Equity (Huidig)
            roe = info.get("returnOnEquity")
            
            # ROE 5-jaar en 10-jaar gemiddelde berekenen uit de historie
            roe_5y_avg = "N/A"
            roe_10y_avg = "N/A"
            
            if 'Retained Earnings' in bs.index and 'Net Income' in fin.index:
                # Bereken historische ROE's (Net Income / Total Equity)
                historical_roes = []
                for col in range(min(len(bs.columns), len(fin.columns))):
                    net_inc = fin.iloc[:, col].get('Net Income', 0)
                    equity = bs.iloc[:, col].get('Stockholders Equity') or bs.iloc[:, col].get('Total Stockholders Equity', 1)
                    if equity and equity > 0:
                        historical_roes.append(net_inc / equity)
                
                if len(historical_roes) >= 3:
                    roe_5y_avg = sum(historical_roes[:5]) / min(len(historical_roes), 5)
                if len(historical_roes) >= 7:
                    roe_10y_avg = sum(historical_roes[:10]) / min(len(historical_roes), 10)

            # Return on Invested Capital (ROIC) berekenen: EBIT * (1 - Tax) / (Debt + Equity - Cash)
            ebit = latest_fin.get('EBIT') or latest_fin.get('Operating Income', 0)
            total_debt = info.get('totalDebt') or (latest_bs.get('Total Debt') or 0)
            total_equity = latest_bs.get('Stockholders Equity') or latest_bs.get('Total Stockholders Equity', 1)
            cash = info.get('totalCash') or (latest_bs.get('Cash And Cash Equivalents') or 0)
            invested_capital = total_debt + total_equity - cash
            
            if invested_capital > 0 and ebit:
                # Geschatte belastingdruk van 25% voor de NOPAT
                nopat = ebit * 0.75 
                roic = nopat / invested_capital
            else:
                roic = None

            # --- FORMATTERING NAAR STRINGS ---
            def format_big_number(num, valuta_sign):
                if not num: return "N/A"
                if num >= 1e12: return f"{valuta_sign}{num/1e12:.2f}T"
                if num >= 1e9: return f"{valuta_sign}{num/1e9:.2f}B"
                if num >= 1e6: return f"{valuta_sign}{num/1e6:.2f}M"
                return f"{valuta_sign}{num:.2f}"

            if ticker_symbol.endswith(('.AS', '.BR', '.DE', '.PA')): valuta = "€"
            elif ticker_symbol.endswith('.L'): valuta = "£"
            elif ticker_symbol.endswith('.T'): valuta = "¥"
            else: valuta = "$"

            # Altman Z-Score
            total_assets = latest_bs.get('Total Assets') or latest_bs.get('TotalAssets')
            working_capital = (latest_bs.get('Current Assets') or latest_bs.get('CurrentAssets', 0)) - (latest_bs.get('Current Liabilities') or latest_bs.get('CurrentLiabilities', 0))
            retained_earnings = latest_bs.get('Retained Earnings') or latest_bs.get('RetainedEarnings', 0)
            market_cap_z = info.get('marketCap', 1)
            total_liab = latest_bs.get('Total Liabilities') or latest_bs.get('TotalLiabilities Net Minority Interest') or latest_bs.get('TotalLiabilities', 1)
            revenue = latest_fin.get('Total Revenue') or latest_fin.get('TotalRevenue', 1)
            
            if total_assets and total_liab and total_assets > 0 and total_liab > 0:
                X1 = working_capital / total_assets
                X2 = retained_earnings / total_assets
                X3 = ebit / total_assets
                X4 = market_cap_z / total_liab
                X5 = revenue / total_assets
                if X4 > 50: X4 = 50 
                z_score = (1.2 * X1) + (1.4 * X2) + (3.3 * X3) + (0.6 * X4) + (0.99 * X5)
                z_str = f"{z_score:.2f}"
            else:
                z_score = 0
                z_str = "N/A"
            
            if info.get('sector') == "Financials": status = "N/A (Bank)"
            elif z_score > 2.99: status = "🟢 Safe"
            elif 1.81 <= z_score <= 2.99: status = "🟡 Grey"
            else: status = "🔴 Trap"
            
            if only_safe and z_score <= 2.99:
                continue
                
            results.append({
                "Ticker": ticker_symbol,
                "Naam": info.get("longName", ticker_symbol),
                "Market Cap": format_big_number(market_cap, valuta),
                "Enterprise Value (EV)": format_big_number(enterprise_value, valuta),
                "Upside": f"{upside:.1f}%" if target else "N/A",
                "EV/EBITDA": f"{ev_ebitda:.1f}" if ev_ebitda else "N/A",
                "Forward EV/EBITDA": f"{fwd_ev_ebitda:.1f}" if fwd_ev_ebitda and isinstance(fwd_ev_ebitda, (int, float)) else "N/A",
                "EV/FCF": f"{ev_fcf:.1f}" if ev_fcf else "N/A",
                "ROE (Huidig)": f"{roe * 100:.1f}%" if roe else "N/A",
                "ROE 5Y Avg": f"{roe_5y_avg * 100:.1f}%" if isinstance(roe_5y_avg, float) else "N/A",
                "ROE 10Y Avg": f"{roe_10y_avg * 100:.1f}%" if isinstance(roe_10y_avg, float) else "N/A",
                "ROIC": f"{roic * 100:.1f}%" if roic else "N/A",
                "Altman Z": z_str,
                "Status": status
            })
        except Exception:
            pass
            
    status_text.text("Scan voltooid!")
    
    if results:
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        st.session_state['scan_results'] = df
    else:
        st.warning("Geen resultaten gevonden voor deze criteria.")

# --- STAP 4: DYNAMISCHE GRAFIEK ONDERAAN ---
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
