import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import plotly.express as px
import requests

# 1. Page Config
st.set_page_config(
    page_title="🍌 Banana Screener 🍌", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

st.title("🍌 Banana Screener 🍌")

# 2. Sidebar Parameters
st.sidebar.header("Filter Criteria")
ticker_input = st.sidebar.text_input("Watchlist (Comma Separated)", "GME")

st.sidebar.subheader("Contract Parameters")
min_dte = st.sidebar.slider("Minimum Days to Expiration (DTE)", 30, 730, 60)
max_extrinsic = st.sidebar.slider("Max Extrinsic Premium (%)", 1.0, 50.0, 10.0)
max_spread = st.sidebar.slider("Max Bid/Ask Spread (%)", 1.0, 50.0, 5.0, help="Filters out illiquid contracts where you lose money to the spread.")
min_volume = st.sidebar.number_input("Minimum Volume", min_value=0, value=250)
min_oi = st.sidebar.number_input("Minimum Open Interest (OI)", min_value=0, value=1000)

strategy = st.sidebar.radio(
    "Target Strategy",
    [
        "All LEAPS (Raw Data)", 
        "Deep ITM (Stock Replacement)", 
        "High Leverage / Low IV",
        "Max Upside (+20% Stock Rally)"
    ]
)

tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

# 3. Live Data Fetcher
@st.cache_data(ttl=900)
def fetch_leaps_data(ticker_list, min_days):
    results, errors = [], []
    today = datetime.now()

    for ticker in ticker_list:
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            if not expirations:
                errors.append(f"{ticker}: No expiration dates.")
                continue

            try:
                spot_price = stock.fast_info['lastPrice']
            except:
                hist = stock.history(period="1d")
                spot_price = hist['Close'].iloc[-1] if not hist.empty else 0.0

            for exp in expirations:
                exp_date = datetime.strptime(exp, "%Y-%m-%d")
                dte = (exp_date - today).days

                if dte >= min_days:
                    chain = stock.option_chain(exp)
                    for _, call in chain.calls.iterrows():
                        strike, price = call['strike'], call['lastPrice']
                        if price == 0: continue
                            
                        bid, ask = call.get('bid', 0.0), call.get('ask', 0.0)
                        vol, oi = call.get('volume', 0), call.get('openInterest', 0)
                        iv = (call.get('impliedVolatility', 0.0)) * 100
                        
                        # Base Metrics
                        intrinsic = max(0.0, spot_price - strike)
                        
                        # --- SANITY CHECK ---
                        # If option is priced below intrinsic value, data is delayed/bugged. Skip it.
                        if price < (intrinsic * 0.98):  # 2% buffer for bid/ask delays
                            continue
                        # --------------------
                        
                        extrinsic = max(0.0, price - intrinsic)
                        extrinsic_pct = (extrinsic / spot_price) * 100 if spot_price > 0 else 0
                        break_even = strike + price
                        be_dist_pct = ((break_even - spot_price) / spot_price) * 100 if spot_price > 0 else 0
                        
                        # Advanced Metrics
                        moneyness = spot_price / strike if strike > 0 else 0
                        est_delta = min(0.99, max(0.01, round(0.50 + (moneyness - 1.0) * 1.5, 2)))
                        eff_leverage = (spot_price / price) * est_delta if price > 0 else 0
                        
                        spread_pct = ((ask - bid) / price) * 100 if price > 0 and ask > bid else 0
                        cost_per_day = extrinsic / dte if dte > 0 else 0
                        prob_itm = est_delta * 100
                        
                        # Profitability Stress Test (+20% Rally Scenario)
                        stock_up_20 = spot_price * 1.20
                        value_at_expiry = max(0.0, stock_up_20 - strike)
                        roi_20pct = ((value_at_expiry - price) / price) * 100 if price > 0 else -100.0

                        results.append({
                            "Ticker": ticker, "Expiration": exp, "DTE": dte, "Strike": strike,
                            "Spot": round(spot_price, 2), "Price": round(price, 2),
                            "Spread %": round(spread_pct, 1),
                            "Vol": int(vol) if not pd.isna(vol) else 0,
                            "OI": int(oi) if not pd.isna(oi) else 0,
                            "Extrinsic %": round(extrinsic_pct, 2), 
                            "Cost/Day": round(cost_per_day, 3),
                            "IV %": round(iv, 1),
                            "Break-Even %": round(be_dist_pct, 1),
                            "Prob ITM %": round(prob_itm, 1), 
                            "Eff Leverage": round(eff_leverage, 2),
                            "+20% Rally ROI %": round(roi_20pct, 1)
                        })
        except Exception as e:
            errors.append(f"{ticker}: {str(e)}")
    return pd.DataFrame(results), errors

# 4. Data Processing & UI
with st.spinner("Fetching live options chain data..."):
    df, fetch_errors = fetch_leaps_data(tickers, min_dte)

if fetch_errors:
    for err in fetch_errors: 
        st.sidebar.warning(err)

if not df.empty:
    # Base Global Filters
    df = df[(df["Extrinsic %"] <= max_extrinsic) & 
            (df["Vol"] >= min_volume) & 
            (df["OI"] >= min_oi) &
            (df["Spread %"] <= max_spread)]
            
    # Strategy Filters
    if strategy == "Deep ITM (Stock Replacement)":
        filtered_df = df[(df["Strike"] <= df["Spot"] * 0.90) & (df["Extrinsic %"] <= 12.0)].sort_values("Extrinsic %")
    elif strategy == "High Leverage / Low IV":
        filtered_df = df[(df["Eff Leverage"] >= 2.0) & (df["IV %"] <= 90.0)].sort_values("Eff Leverage", ascending=False)
    elif strategy == "Max Upside (+20% Stock Rally)":
        filtered_df = df.sort_values("+20% Rally ROI %", ascending=False)
    else:
        filtered_df = df.sort_values(["Ticker", "DTE", "Strike"])

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Scanned", len(df))
    c2.metric("Filtered Opportunities", len(filtered_df))
    c3.metric("Current Mode", strategy)
    if not filtered_df.empty: 
        c4.metric("Best Upside (+20% Rally)", f"{round(filtered_df['+20% Rally ROI %'].max(), 1)}%")

    tab1, tab2, tab3 = st.tabs(["📊 Profitability Matrix", "📈 Visualizations", "🤖 Llama 3 AI Check"])

    with tab1:
        # Dynamic Strategy Banner
        strategy_rules = {
            "All LEAPS (Raw Data)": "🎯 **Raw Scan Rule:** Filter for **Spread % < 8%** to guarantee liquid orders, and prioritize **DTE > 365** days for time safety.",
            "Deep ITM (Stock Replacement)": "🎯 **Stock Replacement Rule:** Look for **Extrinsic % < 8%** and **Prob ITM % > 80%**. You get ~100 shares of exposure with virtually zero time drag.",
            "High Leverage / Low IV": "🎯 **Volatility Expansion Rule:** Target **IV % < 40%** and **Eff Leverage > 2.5x**. Buying when IV is low ensures you don't pay a volatility markup.",
            "Max Upside (+20% Stock Rally)": "🎯 **Asymmetric Upside Rule:** Seek **+20% Rally ROI % > 40%** with a low **Cost/Day**. High returns mean option upside far outpaces time decay."
        }
        
        col_banner, col_popover = st.columns([5, 1])
        with col_banner:
            st.info(strategy_rules.get(strategy, ""))
        with col_popover:
            with st.popover("💡 Selection Rules"):
                st.markdown("""
                ### Quick Rules of Thumb
- **Extrinsic %:** < 8% is ideal. > 20% is expensive time drag.
- **Spread %:** < 5% is liquid. Always use **Limit Orders**.
- **Prob ITM %:** > 70% for safe stock replacement.
- **Eff Leverage:** 2.0x - 3.5x gives max efficiency without wild risk.
- **IV %:** Lower is cheaper. Buy when IV is historically low.
                """)

        if not filtered_df.empty:
            def style_dataframe(row):
                styles = [''] * len(row)
                idx_roi = filtered_df.columns.get_loc("+20% Rally ROI %")
                if row["+20% Rally ROI %"] >= 50.0:
                    styles[idx_roi] = 'background-color: rgba(30, 80, 30, 0.5); color: #a3e635; font-weight: bold;'
                elif row["+20% Rally ROI %"] < 0:
                    styles[idx_roi] = 'background-color: rgba(80, 30, 30, 0.5); color: #f87171;'
                
                idx_spread = filtered_df.columns.get_loc("Spread %")
                if row["Spread %"] > 10.0:
                    styles[idx_spread] = 'color: #facc15;'
                    
                return styles

            # Native Column Tooltips with Rules of Thumb
            column_rules = {
                "Ticker": st.column_config.TextColumn("Ticker", help="Stock ticker symbol."),
                "DTE": st.column_config.NumberColumn("DTE", help="💡 RULE OF THUMB: Aim for 365+ DTE for LEAPS to minimize daily time decay."),
                "Spread %": st.column_config.NumberColumn("Spread %", help="💡 RULE OF THUMB: Target < 5%. Over 10% is illiquid—never use Market Orders, always use Limit Orders!", format="%.1f%%"),
                "OI": st.column_config.NumberColumn("OI", help="💡 RULE OF THUMB: High Open Interest indicates an active market, meaning better liquidity and easier entries/exits."),
                "Extrinsic %": st.column_config.NumberColumn("Extrinsic %", help="💡 RULE OF THUMB: Keep < 10% for stock replacement. Above 20% means high time-decay drag.", format="%.2f%%"),
                "Cost/Day": st.column_config.NumberColumn("Cost/Day", help="💡 RULE OF THUMB: Dollar cost per day (Theta decay). Lower means holding the contract longer is cheaper.", format="$%.3f"),
                "IV %": st.column_config.NumberColumn("IV %", help="💡 RULE OF THUMB: Lower IV means options are 'on sale'. High IV means you pay a volatility premium.", format="%.1f%%"),
                "Break-Even %": st.column_config.NumberColumn("Break-Even %", help="💡 RULE OF THUMB: Stock % gain needed by expiration to break even. Lower is safer.", format="%.1f%%"),
                "Prob ITM %": st.column_config.NumberColumn("Prob ITM %", help="💡 RULE OF THUMB: Aim for 70%-80%+ for safe, high-probability stock replacements.", format="%.1f%%"),
                "Eff Leverage": st.column_config.NumberColumn("Eff Leverage", help="💡 RULE OF THUMB: 2.0x to 3.5x is the sweet spot for capital efficiency without extreme volatility.", format="%.2fx"),
                "+20% Rally ROI %": st.column_config.NumberColumn("+20% Rally ROI %", help="💡 RULE OF THUMB: Look for > 30%. Negative values mean time decay destroys gains even if the stock rises 20%.", format="%.1f%%")
            }

            st.dataframe(
                filtered_df.style.apply(style_dataframe, axis=1), 
                column_config=column_rules,
                use_container_width=True, 
                hide_index=True
            )
            
            st.download_button(
                "📥 Export Screened LEAPS to CSV", 
                data=filtered_df.to_csv(index=False).encode('utf-8'), 
                file_name=f"leaps_screen_{datetime.now().strftime('%Y%m%d')}.csv", 
                mime="text/csv"
            )
        else:
            st.warning("No contracts matched your filter criteria.")

    with tab2:
        if not filtered_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(px.scatter(filtered_df, x="Prob ITM %", y="+20% Rally ROI %", color="Ticker", size="OI", hover_data=["Strike", "Price"], title="Probability vs. Potential Return (Sized by OI)"), use_container_width=True)
            with col2:
                st.plotly_chart(px.scatter(filtered_df, x="Extrinsic %", y="IV %", color="Ticker", size="DTE", hover_data=["Strike", "Price", "Spread %"], title="Cheapness Map (Lower Left is Cheaper)"), use_container_width=True)

    with tab3:
        st.subheader("Fundamental Catalyst Check")
        selected_ticker = st.selectbox("Select Ticker", tickers)

        if st.button("Run Llama 3 Risk Check"):
            prompt = f"Provide a brief 3-bullet point fundamental risk and catalyst assessment for buying 1-year long-dated call options (LEAPS) on {selected_ticker}."
            with st.spinner("Connecting to local Ollama instance..."):
                try:
                    res = requests.post("http://localhost:11434/api/generate", json={"model": "llama3:8b", "prompt": prompt, "stream": False}, timeout=15)
                    res.raise_for_status()
                    st.success("AI Analysis Complete:")
                    st.write(res.json()["response"])
                except Exception as e:
                    st.error("🚨 Connection Failed. Ensure `ollama serve` is running in a separate terminal.")
else:
    st.error("No options data received.")