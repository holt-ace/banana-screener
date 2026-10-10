# 🍌 Banana Screener 🍌

**[Play with the Live App Here!](https://banana-screener.streamlit.app/)**

Banana Screener is an interactive web dashboard designed to help retail traders screen, analyze, and visualize equity options—with a specific focus on Long-Term Equity Anticipation Securities (LEAPS). Powered by live data, it evaluates options chains to find the best risk-to-reward contracts based on your own custom criteria.

## ✨ Features

* **Dual User Modes:**
  * **🦍 Ape (Beginner):** Translates complex options jargon into plain English. Focuses on maximum risk, win probability, and target stock prices.
  * **🦧 Orangutan (Pro):** Unlocks raw options data, including Bid/Ask Spread %, Extrinsic Premium %, Implied Volatility (IV%), and Effective Leverage.
* **Live Volatility Alerts:** Automatically compares a contract's Implied Volatility against the stock's 1-year Historical Volatility (HV) to warn you of potential "IV Crush" before you buy.
* **Target Strategies:** Quick-filter contracts based on specific goals (Max Upside, Deep ITM, High Leverage, or Raw LEAPS).
* **Interactive P&L Sandbox:** Visualize expiration payoff diagrams for selected contracts and calculate Good-Til-Canceled (GTC) limit sell orders to automate your exits.
* **Advanced Visualizations (Pro Mode):** Interactive scatter plots mapping Volatility Skew (IV vs. Strike) and Contract Cheapness (Extrinsic % vs. IV).

## 🚀 How to Use

No installation required! Just head over to **[banana-screener.streamlit.app](https://banana-screener.streamlit.app/)** and use the left sidebar to tailor the screening process to your specific risk tolerance:

1. **Watchlist:** Input a comma-separated list of ticker symbols (defaults to `GME`).
2. **Contract Parameters:** Adjust your minimum days to expiration, max extrinsic premium (hype value), max spread, and minimum volume.
3. **Analyze:** Toggle between the Trade Matrix, the P&L Sandbox, and the Pro Visuals to find your entry and exit strategies.

## ⚠️ Disclaimer

**This tool is for educational and informational purposes only.** It does not constitute financial advice, investment recommendations, or an endorsement to buy or sell any securities. Options trading carries significant risk and is not suitable for all investors. Always perform your own due diligence and consult with a licensed financial advisor before making any investment decisions. Live data may be delayed or subject to inaccuracies.