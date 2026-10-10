import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# 1. Page Config
st.set_page_config(
    page_title="🍌 Banana Screener 🍌", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Top UI: Title (Left) and Mode Switcher (Top Right)
header_col1, header_col2 = st.columns([7, 3])
with header_col1:
    st.title("🍌 Banana Screener 🍌")
with header_col2:
    st.markdown("<br>", unsafe_allow_html=True) # Aligns the radio buttons with the title text
    app_mode = st.radio(
        "Mode Selection",
        ["🦍 Ape", "🦧 Orangutan (Pro)"],
        horizontal=True,
        label_visibility="collapsed"
    )

is_ape = "Ape" in app_mode

# 2. Sidebar Parameters 
st.sidebar.header("Filter Criteria")
ticker_input = st.sidebar.text_input("Watchlist (Comma Separated)", "GME")

st.sidebar.subheader("Contract Parameters")

min_dte = st.sidebar.slider(
    "Minimum Days to Expiration (DTE)", 30, 730, 60,
    help="🦍 Ape Translation: More days = safer. Gives the stock more time to move." if is_ape else None
)
max_extrinsic = st.sidebar.slider(
    "Max Extrinsic Premium (%)", 1.0, 50.0, 10.0,
    help="🦍 Ape Translation: How much 'hype' premium you are paying above the stock's actual value. Keep this low." if is_ape else None
)
max_spread = st.sidebar.slider(
    "Max Bid/Ask Spread (%)", 1.0, 50.0, 5.0,
    help="🦍 Ape Translation: High spread means illiquid. Keep this low so you don't get robbed by market makers when you sell." if is_ape else None
)
min_volume = st.sidebar.number_input(
    "Minimum Volume", min_value=0, value=250,
    help="🦍 Ape Translation: How many contracts traded today." if is_ape else None
)
min_oi = st.sidebar.number_input(
    "Minimum Open Interest (OI)", min_value=0, value=1000, 
    help="🦍 Ape Translation: How many other people are holding this contract. High OI = easier to sell." if is_ape else None
)

strategy = st.sidebar.radio(
    "Target Strategy",
    [
        "Max Upside (+20% Stock Rally)",
        "Deep ITM (Stock Replacement)", 
        "High Leverage / Low IV",
        "All LEAPS (Raw Data)"
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
                        
                        intrinsic = max(0.0, spot_price - strike)
                        if price < (intrinsic * 0.98): continue
                        
                        extrinsic = max(0.0, price - intrinsic)
                        extrinsic_pct = (extrinsic / spot_price) * 100 if spot_price > 0 else 0
                        break_even = strike + price
                        be_dist_pct = ((break_even - spot_price) / spot_price) * 100 if spot_price > 0 else 0
                        
                        moneyness = spot_price / strike if strike > 0 else 0
                        est_delta = min(0.99, max(0.01, round(0.50 + (moneyness - 1.0) * 1.5, 2)))
                        eff_leverage = (spot_price / price) * est_delta if price > 0 else 0
                        
                        spread_pct = ((ask - bid) / price) * 100 if price > 0 and ask > bid else 0
                        cost_per_day = extrinsic / dte if dte > 0 else 0
                        prob_itm = est_delta * 100
                        
                        stock_up_20 = spot_price * 1.20
                        value_at_expiry = max(0.0, stock_up_20 - strike)
                        roi_20pct = ((value_at_expiry - price) / price) * 100 if price > 0 else -100.0
                        contract_cost = price * 100

                        results.append({
                            "Ticker": ticker, "Expiration": exp, "DTE": dte, "Strike": strike,
                            "Spot": round(spot_price, 2), "Price": round(price, 2), "Max Risk ($)": contract_cost,
                            "Spread %": round(spread_pct, 1), "Vol": int(vol) if not pd.isna(vol) else 0,
                            "OI": int(oi) if not pd.isna(oi) else 0, "Extrinsic %": round(extrinsic_pct, 2), 
                            "Cost/Day": round(cost_per_day, 3), "IV %": round(iv, 1),
                            "Break-Even": round(break_even, 2), "Break-Even %": round(be_dist_pct, 1),
                            "Prob ITM %": round(prob_itm, 1), "Eff Leverage": round(eff_leverage, 2),
                            "+20% Rally ROI %": round(roi_20pct, 1)
                        })
        except Exception as e:
            errors.append(f"{ticker}: {str(e)}")
    return pd.DataFrame(results), errors

# 4. Data Processing & UI
with st.spinner("Crunching options data..."):
    df, fetch_errors = fetch_leaps_data(tickers, min_dte)

if fetch_errors:
    for err in fetch_errors: 
        st.sidebar.warning(err)

if not df.empty:
    df = df[(df["Extrinsic %"] <= max_extrinsic) & 
            (df["Vol"] >= min_volume) & 
            (df["OI"] >= min_oi) &
            (df["Spread %"] <= max_spread)]
            
    if strategy == "Deep ITM (Stock Replacement)":
        filtered_df = df[(df["Strike"] <= df["Spot"] * 0.90) & (df["Extrinsic %"] <= 12.0)].sort_values("Extrinsic %")
    elif strategy == "High Leverage / Low IV":
        filtered_df = df[(df["Eff Leverage"] >= 2.0) & (df["IV %"] <= 90.0)].sort_values("Eff Leverage", ascending=False)
    elif strategy == "Max Upside (+20% Stock Rally)":
        filtered_df = df.sort_values("+20% Rally ROI %", ascending=False)
    else:
        filtered_df = df.sort_values(["Ticker", "DTE", "Strike"])

    st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 5% 10%; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    div[data-testid="stRadio"] label {
        font-size: 1.5rem !important; 
    }
    </style>
    """, unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Scanned", len(df))
    m2.metric("Filtered Matches", len(filtered_df))
    m3.metric("Active Mode", app_mode.split(" ")[0])
    m4.metric("Best Upside (+20% Move)", f"{round(filtered_df['+20% Rally ROI %'].max(), 1)}%" if not filtered_df.empty else "N/A")

    st.markdown("<br>", unsafe_allow_html=True)
    
    primary_ticker = tickers[0] if tickers else "GME"
    stock_data = yf.Ticker(primary_ticker)
    hist_1y = stock_data.history(period="1y")
    hv_1y = hist_1y['Close'].pct_change().std() * (252 ** 0.5) * 100 if len(hist_1y) > 0 else 50.0 
    avg_iv = filtered_df['IV %'].mean() if not filtered_df.empty else (df['IV %'].mean() if not df.empty else 0)
    iv_diff = avg_iv - hv_1y

    dash_col1, dash_col2 = st.columns([1, 1])
    with dash_col1:
        if is_ape:
            st.subheader(f"⚠️ Ape Alert: Volatility (IV Crush)")
            if avg_iv > hv_1y * 1.2:
                st.error(f"**DANGER:** The hype (Implied Volatility at {avg_iv:.1f}%) is way higher than normal ({hv_1y:.1f}%). Contracts are overpriced. If the hype dies down, you lose money even if the stock goes up. (This is called IV Crush).")
            elif avg_iv > hv_1y:
                st.warning(f"**CAUTION:** The hype ({avg_iv:.1f}%) is slightly above historical averages ({hv_1y:.1f}%). You are paying a small premium.")
            else:
                st.success(f"**SAFE ENTRY:** Hype is low. Options are priced cheaply relative to how much the stock normally moves. Low risk of IV crush.")
        else:
            st.subheader(f"⚠️ Volatility Alert: {primary_ticker}")
            if avg_iv > hv_1y * 1.2:
                st.error(f"**IV CRUSH DANGER:** Implied Volatility ({avg_iv:.1f}%) is far above historical averages ({hv_1y:.1f}%). Options are highly inflated.")
            elif avg_iv > hv_1y:
                st.warning(f"**Elevated Premium:** IV ({avg_iv:.1f}%) is slightly above historical averages ({hv_1y:.1f}%).")
            else:
                st.success(f"**Safe Entry (Low IV):** Options are currently priced cheaply relative to the stock's historical movement. Low risk of IV crush.")

    with dash_col2:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = avg_iv, domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"Average IV vs Historical ({hv_1y:.1f}%)"},
            delta = {'reference': hv_1y, 'increasing': {'color': "#f87171"}, 'decreasing': {'color': "#a3e635"}},
            gauge = {
                'axis': {'range': [0, max(200, avg_iv + 20)], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': "rgba(255,255,255,0.8)", 'thickness': 0.10}, 'bgcolor': "rgba(0,0,0,0)",
                'steps': [
                    {'range': [0, hv_1y * 0.9], 'color': "rgba(30, 80, 30, 0.6)"},       
                    {'range': [hv_1y * 0.9, hv_1y * 1.2], 'color': "rgba(180, 130, 30, 0.6)"}, 
                    {'range': [hv_1y * 1.2, max(200, avg_iv + 20)], 'color': "rgba(180, 30, 30, 0.6)"} 
                ],
                'threshold': {'line': {'color': "white", 'width': 3}, 'thickness': 0.75, 'value': avg_iv}
            }
        ))
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=80, b=10), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
        st.plotly_chart(fig, use_container_width=True)

    # --- TABS ---
    tab1, tab2, tab3 = st.tabs(["📊 Trade Matrix", "🕹️ P&L Sandbox", "📈 Pro Visuals"])

    with tab1:
        if not filtered_df.empty:
            def style_dataframe(row):
                styles = [''] * len(row)
                if "+20% Rally ROI %" in row.index:
                    idx_roi = row.index.get_loc("+20% Rally ROI %")
                    if row["+20% Rally ROI %"] >= 50.0: 
                        styles[idx_roi] = 'background-color: rgba(30, 80, 30, 0.5); color: #a3e635;'
                    elif row["+20% Rally ROI %"] < 0: 
                        styles[idx_roi] = 'background-color: rgba(80, 30, 30, 0.5); color: #f87171;'
                return styles

            if is_ape:
                ape_cols = {
                    "Ticker": st.column_config.TextColumn("Ticker"),
                    "DTE": st.column_config.NumberColumn("Days to Expiry", help="Time you have for the stock to move."),
                    "Price": st.column_config.NumberColumn("Contract Price", format="$%.2f"),
                    "Max Risk ($)": st.column_config.NumberColumn("Total Cost / Max Risk", help="The most money you can lose if the contract expires worthless.", format="$%.2f"),
                    "Cost/Day": st.column_config.NumberColumn("Daily Time Decay", help="How much value the contract loses per day (Theta).", format="$%.3f"),
                    "Prob ITM %": st.column_config.NumberColumn("Win Probability", help="Rough chance of expiring in the money.", format="%.1f%%"),
                    "Break-Even": st.column_config.NumberColumn("Target Stock Price", help="Stock must hit this price at expiration to not lose money.", format="$%.2f"),
                    "+20% Rally ROI %": st.column_config.NumberColumn("Profit if Stock +20%", format="%.1f%%")
                }
                display_df = filtered_df[["Ticker", "DTE", "Strike", "Price", "Max Risk ($)", "Cost/Day", "Prob ITM %", "Break-Even", "+20% Rally ROI %"]]
                st.dataframe(display_df.style.apply(style_dataframe, axis=1), column_config=ape_cols, use_container_width=True, hide_index=True)
            else:
                pro_cols = {
                    "Spread %": st.column_config.NumberColumn("Spread %", format="%.1f%%"),
                    "Extrinsic %": st.column_config.NumberColumn("Extrinsic %", format="%.2f%%"),
                    "IV %": st.column_config.NumberColumn("IV %", format="%.1f%%"),
                    "Eff Leverage": st.column_config.NumberColumn("Eff Leverage", format="%.2fx"),
                }
                st.dataframe(filtered_df.style.apply(style_dataframe, axis=1), column_config=pro_cols, use_container_width=True, hide_index=True)
        else:
            st.warning("No contracts matched your filter criteria.")

    with tab2:
        st.markdown("### 🏒 Expiration Payoff Diagram & Exit Calculator")
        if not filtered_df.empty:
            sandbox_col1, sandbox_col2 = st.columns([1, 3])
            with sandbox_col1:
                st.markdown("#### Select Contract")
                selected_strike = st.selectbox("Strike Price", filtered_df['Strike'].unique())
                contract = filtered_df[filtered_df['Strike'] == selected_strike].iloc[0]
                
                st.markdown("---")
                st.markdown("#### 🎯 GTC Limit Order Calculator")
                st.write("Set a Good-Til-Canceled limit order immediately after buying to automate your exit." if not is_ape else "🦍 Set your sell price right after buying so you don't get greedy and miss the exit.")
                target_profit = st.slider("Target Profit %", 10, 200, 50)
                target_sell_price = contract['Price'] * (1 + (target_profit / 100))
                st.success(f"**Set GTC Sell Order at: ${target_sell_price:.2f}**")

            with sandbox_col2:
                spot = contract['Spot']
                strike = contract['Strike']
                premium = contract['Price']
                
                stock_prices = np.linspace(spot * 0.5, spot * 1.5, 100)
                payoff = np.maximum(0, stock_prices - strike) - premium
                payoff_dollars = payoff * 100
                
                fig2 = px.line(x=stock_prices, y=payoff_dollars, labels={'x': 'Stock Price at Expiration', 'y': 'Total Profit/Loss ($)'})
                fig2.add_vline(x=spot, line_dash="dash", line_color="gray", annotation_text="Current Price")
                fig2.add_vline(x=contract['Break-Even'], line_dash="dash", line_color="#a3e635", annotation_text="Break-Even")
                fig2.add_hline(y=0, line_color="white")
                fig2.update_traces(line_color="#38bdf8", line_width=3)
                fig2.update_layout(title=f"Payoff for {contract['Expiration']} ${strike} Call", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.05)")
                st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        if is_ape:
            st.info("🦍 **Ape Note:** Switch to **🦧 Orangutan (Pro)** mode at the top right of the dashboard to unlock complex Volatility Skew charts, Extrinsic scatter plots, and unfiltered chain data.")
        elif not filtered_df.empty:
            st.markdown("### 🌊 Volatility Skew & Cheapness Map")
            c1, c2 = st.columns(2)
            with c1:
                skew_fig = px.scatter(df, x="Strike", y="IV %", color="DTE", title="Volatility Skew (IV vs Strike)", hover_data=["Price", "Vol"])
                skew_fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.05)")
                st.plotly_chart(skew_fig, use_container_width=True)
            with c2:
                cheap_fig = px.scatter(filtered_df, x="Extrinsic %", y="IV %", color="Ticker", size="DTE", hover_data=["Strike", "Spread %"], title="Cheapness Map (Lower Left = Cheaper)")
                cheap_fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.05)")
                st.plotly_chart(cheap_fig, use_container_width=True)
else:
    st.error("No options data received.")