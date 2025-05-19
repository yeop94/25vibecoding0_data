import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import koreanize_matplotlib

st.title("내가 좋아하는 주식 차트")

ticker = st.text_input("종목 코드 입력 (예: 삼성전자 = 005930.KS)", value="005930.KS")

if st.button("주가 불러오기"):
    data = yf.download(ticker, period="3mo")
    
    if not data.empty:
        st.write(f"최근 데이터: {data.index[-1].date()}")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(data['Close'], label="종가")
        ax.set_title("3개월 주가 추이")
        ax.set_xlabel("날짜")
        ax.set_ylabel("종가 (원)")
        ax.legend()
        st.pyplot(fig)
    else:
        st.error("데이터를 불러올 수 없습니다. 종목 코드를 확인해주세요.")
