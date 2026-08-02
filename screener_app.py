import yfinance as yf
import pandas as pd
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Global Value Screener & Portfolio Simulator", layout="wide")

# --- SUPABASE DATABASE VERBINDING ---
@st.cache_resource
def init_supabase() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("⚠️ Kan geen verbinding maken met Supabase Secrets. Controleer je Streamlit Secrets!")
        st.stop()

supabase = init_supabase()
USER_ID = "default_user"

def load_user_data_from_supabase():
    try:
        response = supabase.table("user_portfolio").select("*").eq("id", USER_ID).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return {
                "portfolio_cash": float(row.get("portfolio_cash", 20000.0)),
                "portfolio_shares": row.get("portfolio_shares", {}),
                "watchlist": row.get("watchlist", [])
            }
    except Exception:
        pass
    return {"portfolio_cash": 20000.0, "portfolio_shares": {}, "watchlist": []}

def save_user_data_to_supabase():
    try:
        supabase.table("user_portfolio").upsert({
            "id": USER_ID,
            "portfolio_cash": st.session_state['portfolio_cash'],
            "portfolio_shares": st.session_state['portfolio_shares'],
            "watchlist": st.session_state['watchlist']
        }).execute()
    except Exception as e:
        st.error(f"Fout bij opslaan in Supabase: {e}")

# Initialiseer session state
if 'initialized' not in st.session_state:
    db_data = load_user_data_from_supabase()
    st.session_state['portfolio_cash'] = db_data['portfolio_cash']
    st.session_state['portfolio_shares'] = db_data['portfolio_shares']
    st.session_state['watchlist'] = db_data['watchlist']
    st.session_state['initialized'] = True

st.title("🌐 Live Market Screener & Portfolio (€20.000)")

tab1, tab2, tab3 = st.tabs(["🚀 Markt Scanner (Database)", "⭐ Watchlist", "💼 Fictieve Portefeuille (€20k)"])

# ==========================================
# TAB 1: MARKT SCANNER
# ==========================================
with tab1:
    st.header("⚡ Instant Markt Scanner")
    st.write("De resultaten hieronder worden op de achtergrond ververst via Supabase.")
    
    try:
        response = supabase.table("scanned_stocks").select("*").execute()
        scanned_data = response.data
    except Exception as e:
        scanned_data = []
        st.error(f"Kon gegevens niet ophalen uit Supabase: {e}")

    if scanned_data:
        df = pd.DataFrame(scanned_data)
        
        c1, c2 = st.columns(2)
        with c1:
            advies_filter = st.multiselect("Filter op Advies:", options=df['advies'].unique(), default=df['advies'].unique())
        with c2:
            search_ticker = st.text_input("Zoek specifiek aandeel / ticker:", "")

        filtered_df = df[df['advies'].isin(advies_filter)]
        if search_ticker:
            filtered_df = filtered_df[filtered_df['ticker'].str.contains(search_ticker.upper())]

        display_df = filtered_df.copy()
        display_df['huidige_koers'] = display_df['huidige_koers'].apply(lambda x: f"€{x:.2f}" if pd.notnull(x) else "N/A")
        display_df['upside'] = display_df['upside'].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "N/A")
        display_df['roe'] = display_df['roe'].apply(lambda x: f"{x*100:.1f}%" if pd.notnull(x) else "N/A")
        
        st.dataframe(
            display_df[['ticker', 'naam', 'advies', 'huidige_koers', 'upside', 'ev_ebitda', 'roe']], 
            use_container_width=True
        )

        st.markdown("---")
        st.subheader("🛒 Virtueel Aandeel Kopen")
        
        selected_buy_ticker = st.selectbox("Kies een aandeel uit de tabel om te kopen:", filtered_df['ticker'].tolist())
        buy_amount = st.number_input("Hoeveel euro wil je beleggen?", min_value=100.0, max_value=20000.0, value=2000.0, step=500.0)
        
        if st.button("💰 Koop Aandeel"):
            if buy_amount > st.session_state['portfolio_cash']:
                st.error("Niet genoeg cash geld beschikbaar!")
            else:
                row = df[df['ticker'] == selected_buy_ticker].iloc[0]
                price = float(row['huidige_koers'])
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
                save_user_data_to_supabase()
                st.success(f"Gefeliciteerd! Je hebt {shares_bought:.2f} aandelen {selected_buy_ticker} gekocht!")
                st.rerun()
    else:
        st.info("De database wordt momenteel gevuld op de achtergrond. Start de eerste scan via GitHub Actions!")

# ==========================================
# TAB 2: WATCHLIST
# ==========================================
with tab2:
    st.header("⭐ Watchlist")
    st.write("Jouw bewaarde aandelen in de cloud:")
    st.write(st.session_state['watchlist'])

# ==========================================
# TAB 3: PORTEFEUILLE MET VERKOOP & ADVIES
# ==========================================
with tab3:
    st.header("💼 Jouw Permanente Virtuele Portefeuille")
    
    current_invested_value = 0.0
    portfolio_rows = []
    
    try:
        db_stocks = {item['ticker']: item for item in supabase.table("scanned_stocks").select("*").execute().data}
    except Exception:
        db_stocks = {}

    for ticker, pos in st.session_state['portfolio_shares'].items():
        stock_db_info = db_stocks.get(ticker, {})
        live_price = stock_db_info.get('huidige_koers')
        if not live_price:
            try:
                live_price = float(yf.Ticker(ticker).info.get("currentPrice", pos['gem_aankoopkoers']))
            except Exception:
                live_price = float(pos['gem_aankoopkoers'])
            
        live_val = pos['aantal'] * live_price
        winst_verlies = live_val - pos['totaal_belegd']
        winst_verlies_pct = (winst_verlies / pos['totaal_belegd']) * 100 if pos['totaal_belegd'] > 0 else 0
        
        current_invested_value += live_val

        # --- SLIM VERKOOPADVIES LOGICA ---
        ev_ebitda = stock_db_info.get('ev_ebitda')
        upside = stock_db_info.get('upside', 10)
        roe = stock_db_info.get('roe', 0.20)

        if (ev_ebitda and ev_ebitda > 28) or (upside is not None and upside <= 0):
            verkoop_advies = "🔴 VERKOPEN (Overgewaardeerd / Doel Bereikt)"
        elif roe and roe < 0.12:
            verkoop_advies = "⚠️ OVERWEGEN (Kwaliteit Afgenomen)"
        else:
            verkoop_advies = "🟢 HOUDEN (Sterke Fundamenten)"

        portfolio_rows.append({
            "Ticker": ticker,
            "Aantal": f"{pos['aantal']:.2f}",
            "Gem. Aankoop": f"€{pos['gem_aankoopkoers']:.2f}",
            "Huidige Koers": f"€{live_price:.2f}",
            "Totale Waarde": f"€{live_val:.2f}",
            "Winst / Verlies": f"€{winst_verlies:.2f} ({winst_verlies_pct:.1f}%)",
            "Verkoop Advies": verkoop_advies,
            "raw_aantal": pos['aantal'],
            "raw_live_price": live_price
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
        df_port = pd.DataFrame(portfolio_rows)
        st.subheader("📊 Investeringen & Verkoop-Signalen")
        st.dataframe(df_port.drop(columns=['raw_aantal', 'raw_live_price']), use_container_width=True)

        st.markdown("---")
        col_sell1, col_sell2 = st.columns(2)
        
        with col_sell1:
            st.subheader("💸 Aandelen Verkopen")
            ticker_to_sell = st.selectbox("Kies het aandeel dat je wil verkopen:", df_port['Ticker'].tolist())
            
            selected_pos = df_port[df_port['Ticker'] == ticker_to_sell].iloc[0]
            max_shares = float(selected_pos['raw_aantal'])
            current_price = float(selected_pos['raw_live_price'])
            
            shares_to_sell = st.number_input(
                f"Aantal aandelen te verkopen (Max: {max_shares:.2f}):", 
                min_value=0.01, 
                max_value=max_shares, 
                value=max_shares,
                step=1.0
            )
            
            opbrengst = shares_to_sell * current_price
            st.info(f"💵 Geschatte opbrengst bij verkoop: **€{opbrengst:,.2f}**")
            
            if st.button("🔴 Bevestig Verkoop"):
                st.session_state['portfolio_cash'] += opbrengst
                
                if shares_to_sell >= max_shares:
                    del st.session_state['portfolio_shares'][ticker_to_sell]
                else:
                    st.session_state['portfolio_shares'][ticker_to_sell]['aantal'] -= shares_to_sell
                    st.session_state['portfolio_shares'][ticker_to_sell]['totaal_belegd'] -= (shares_to_sell * st.session_state['portfolio_shares'][ticker_to_sell]['gem_aankoopkoers'])
                
                save_user_data_to_supabase()
                st.success(f"Je hebt {shares_to_sell:.2f} aandelen {ticker_to_sell} verkocht voor €{opbrengst:,.2f}!")
                st.rerun()

        with col_sell2:
            st.subheader("💡 Wanneer is het beste moment om te verkopen?")
            st.markdown("""
            Volgens waarde-beleggen (Value Investing) verkoop je een aandeel **niet** bij kleine koersschommelingen, maar bij 3 concrete situaties:
            
            1. **🔴 Overwaardering:** De koers is zó hard gestegen dat het aandeel te duur is geworden (bijv. EV/EBITDA > 25).
            2. **⚠️ Bedrijfskwaliteit verslechtert:** De winstgevendheid (ROE) zakt permanent onder de 12%.
            3. **🔄 Beter Alternatief:** Je ziet in de Scanner een aandeel met veel meer potentie en kwaliteit.
            """)
    else:
        st.info("Je hebt momenteel geen aandelen in je portefeuille. Ga naar de Markt Scanner om aandelen te kopen!")

    st.markdown("---")
    if st.button("🔄 Reset Portefeuille (Terug naar €20.000 Cash)"):
        st.session_state['portfolio_cash'] = 20000.0
        st.session_state['portfolio_shares'] = {}
        st.session_state['watchlist'] = []
        save_user_data_to_supabase()
        st.rerun()
