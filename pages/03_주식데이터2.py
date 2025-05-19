import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

# 페이지 설정
st.set_page_config(page_title="Top 30 주식 시각화", layout="wide")
st.title("📈 전 세계 시가총액 Top 30 기업 주가 시각화")

# 전 세계 시가총액 Top 30 기업 목록 (일부만 포함, 필요 시 추가)
top30_companies = {
    "Apple (AAPL)": "AAPL",
    "Microsoft (MSFT)": "MSFT",
    "Samsung Electronics (005930.KS)": "005930.KS",
    "Tencent (0700.HK)": "0700.HK",
    "Toyota (7203.T)": "7203.T",
    "Amazon (AMZN)": "AMZN",
    "NVIDIA (NVDA)": "NVDA",
    "Alphabet (GOOGL)": "GOOGL",
    "Meta Platforms (META)": "META",
    "TSMC (TSM)": "TSM",
    "Visa (V)": "V",
    "ExxonMobil (XOM)": "XOM"
}

# 기업 선택
company_name = st.selectbox("기업 선택", list(top30_companies.keys()))
ticker = top30_companies[company_name]

# 날짜 선택
today = date.today()
default_start = today - timedelta(days=365)
start_date, end_date = st.date_input(
    "조회 기간 선택 (기본: 최근 1년)",
    value=(default_start, today),
    max_value=today
    # format="YYYY-MM-DD" # <- 이 부분을 삭제 또는 주석 처리합니다.
)

# 날짜 유효성 확인 및 yfinance end 날짜 보정
if start_date >= end_date:
    st.error("❗ 시작일은 종료일보다 앞서야 합니다.")
else:
    yf_end_date = end_date + timedelta(days=1)  # yfinance는 end를 포함하지 않음

    with st.spinner("📡 주가 데이터를 불러오는 중..."):
        data = yf.download(ticker, start=start_date, end=yf_end_date)

    if data.empty or len(data) < 2:
        st.warning("📉 선택한 기간에 유효한 주가 데이터가 부족합니다. 기간을 늘려보세요.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines+markers", name="종가"))
        fig.update_layout(
            title=f"{company_name} 주가 추이 ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})", # 제목에 날짜 포맷 적용
            xaxis_title="날짜",
            yaxis_title="종가 (현지 통화)",
            template="plotly_white",
            height=600
        )
        st.plotly_chart(fig, use_container_width=True)
