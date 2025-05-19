import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

# 페이지 설정
st.set_page_config(page_title="Top 30 주식 시각화", layout="wide")
st.title("📈 전 세계 시가총액 Top 30 기업 주가 시각화") # 이미지와 일치하는 제목

# (기업 목록은 동일하다고 가정)
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

company_name = st.selectbox("기업 선택", list(top30_companies.keys()))
ticker = top30_companies[company_name]

today = date.today()
default_start = today - timedelta(days=365)
start_date, end_date = st.date_input(
    "조회 기간 선택 (기본: 최근 1년)",
    value=(default_start, today), # 실제 선택은 이미지에 따라 2024/05/19 ~ 2025/05/19
    max_value=today
)

if start_date >= end_date:
    st.error("❗ 시작일은 종료일보다 앞서야 합니다.")
else:
    yf_end_date = end_date + timedelta(days=1)

    with st.spinner(f"📡 {company_name} 주가 데이터를 불러오는 중..."):
        # --- 수정된 부분 시작 ---
        data = yf.download(
            ticker,
            start=start_date,
            end=yf_end_date,
            interval="1d"  # <--- 일별 데이터를 명시적으로 요청
        )
        # --- 수정된 부분 끝 ---

    # --- 디버깅 정보 출력 시작 ---
    st.subheader("🛠️ 데이터 확인 (디버깅용)")
    st.write(f"요청 Ticker: {ticker}, 시작일: {start_date}, 종료일(yfinance용): {yf_end_date}")
    if data is not None:
        st.write(f"반환된 데이터 형태 (Shape): {data.shape}")
        st.write("데이터 앞부분 (Head):")
        st.dataframe(data.head())
        st.write("데이터 뒷부분 (Tail):")
        st.dataframe(data.tail())
        st.write("데이터 인덱스 정보 (Index):")
        st.write(data.index)
    else:
        st.write("데이터가 반환되지 않았습니다 (None).")
    st.markdown("---") # 디버깅 정보 구분선
    # --- 디버깅 정보 출력 끝 ---

    if data.empty or len(data) < 2:
        # 이 조건이 True면 경고 메시지가 떠야 하는데, 이미지에서는 차트가 그려졌으므로 False로 판단된 것 같습니다.
        # 하지만 실제 데이터는 1개 점으로 보이므로, len(data)가 1일 가능성이 있습니다.
        # 만약 len(data)가 1이라면, 아래 경고가 표시되어야 정상입니다.
        st.warning(f"📉 선택한 기간에 유효한 주가 데이터가 부족합니다 (데이터 포인트 수: {len(data)}). 기간을 늘려보세요.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines+markers", name="종가"))
        fig.update_layout(
            title=f"{company_name} 주가 추이 ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})",
            xaxis_title="날짜",
            yaxis_title="종가 (현지 통화)",
            template="plotly_white",
            height=600
        )
        st.plotly_chart(fig, use_container_width=True)
