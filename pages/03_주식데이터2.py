import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

# 시가총액 Top 30 기업 딕셔너리
top30_companies = {
    "Apple (AAPL)": "AAPL",
    "Microsoft (MSFT)": "MSFT",
    "Saudi Aramco (2222.SR)": "2222.SR",
    "Alphabet (GOOGL)": "GOOGL",
    "Amazon (AMZN)": "AMZN",
    "NVIDIA (NVDA)": "NVDA",
    "Berkshire Hathaway (BRK-B)": "BRK-B",
    "Meta Platforms (META)": "META",
    "TSMC (TSM)": "TSM",
    "Eli Lilly (LLY)": "LLY",
    "Tesla (TSLA)": "TSLA",
    "Visa (V)": "V",
    "Johnson & Johnson (JNJ)": "JNJ",
    "ExxonMobil (XOM)": "XOM",
    "JPMorgan Chase (JPM)": "JPM",
    "Samsung Electronics (005930.KS)": "005930.KS",
    "Walmart (WMT)": "WMT",
    "Nestlé (NESN.SW)": "NESN.SW",
    "Procter & Gamble (PG)": "PG",
    "UnitedHealth Group (UNH)": "UNH",
    "Roche (ROG.SW)": "ROG.SW",
    "Novartis (NOVN.SW)": "NOVN.SW",
    "Chevron (CVX)": "CVX",
    "LVMH (MC.PA)": "MC.PA",
    "Mastercard (MA)": "MA",
    "Kweichow Moutai (600519.SS)": "600519.SS",
    "ICBC (1398.HK)": "1398.HK",
    "Tencent (0700.HK)": "0700.HK",
    "Shell (SHEL)": "SHEL",
    "Toyota (7203.T)": "7203.T"
}

st.set_page_config(page_title="Top 30 주식 시각화", layout="wide")
st.title("📈 전 세계 시가총액 Top 30 기업 주가 시각화")

# 사용자 입력
company_name = st.selectbox("기업 선택", list(top30_companies.keys()))
ticker = top30_companies[company_name]
period = st.selectbox("기간 선택", ["1mo", "3mo", "6mo", "1y"])

# 데이터 불러오기
data = yf.download(ticker, period=period)

# 차트 시각화
if data.empty:
    st.error("📉 주가 데이터를 불러올 수 없습니다.")
else:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines+markers", name="종가"))
    fig.update_layout(
        title=f"{company_name} 주가 추이 ({period})",
        xaxis_title="날짜",
        yaxis_title="종가 (현지 통화)",
        template="plotly_white",
        height=600
    )
    st.plotly_chart(fig, use_container_width=True)
