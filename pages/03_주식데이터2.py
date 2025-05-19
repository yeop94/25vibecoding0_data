import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

# 페이지 설정
st.set_page_config(page_title="글로벌 및 대한민국 Top 30 주식 시각화", layout="wide")
st.title("📈 글로벌 및 대한민국 Top 30 기업 주가 시각화")

# --- 데이터 목록 ---
# 참고: 아래 목록은 예시이며, 실제 순위 및 티커는 변동될 수 있습니다.
# yfinance에서 조회가 용이한 티커를 우선적으로 사용했습니다.

global_top_companies = {
    "Apple (AAPL)": "AAPL",
    "Microsoft (MSFT)": "MSFT",
    "Saudi Aramco (2222.SR)": "2222.SR", # 사우디 아람코 (타다울 증권거래소)
    "Alphabet (GOOGL)": "GOOGL", # 구글 (Class A)
    "Amazon (AMZN)": "AMZN",
    "NVIDIA (NVDA)": "NVDA",
    "Meta Platforms (META)": "META", # 페이스북/인스타그램 모회사
    "Berkshire Hathaway (BRK-A)": "BRK-A", # 워렌 버핏
    "Eli Lilly (LLY)": "LLY",
    "TSMC (TSM)": "TSM", # 대만 반도체 제조 회사
    "Visa (V)": "V",
    "Novo Nordisk (NVO)": "NVO", # 덴마크 제약 회사 (오젬픽 등)
    "JPMorgan Chase (JPM)": "JPM",
    "ExxonMobil (XOM)": "XOM",
    "Johnson & Johnson (JNJ)": "JNJ",
    "LVMH (MC.PA)": "MC.PA", # 루이비통 모에 헤네시 (파리 증권거래소)
    "Walmart (WMT)": "WMT",
    "Mastercard (MA)": "MA",
    "ASML Holding (ASML)": "ASML", # 네덜란드 반도체 장비 회사
    "Procter & Gamble (PG)": "PG",
    "Tesla (TSLA)": "TSLA",
    "UnitedHealth Group (UNH)": "UNH",
    "Home Depot (HD)": "HD",
    "Chevron (CVX)": "CVX",
    "Oracle (ORCL)": "ORCL",
    "Roche Holding (RHHBY)": "RHHBY", # 스위스 제약 회사 (ADR)
    "Merck & Co. (MRK)": "MRK",
    "AbbVie (ABBV)": "ABBV",
    "Coca-Cola (KO)": "KO",
    "Broadcom (AVGO)": "AVGO"
}

korean_top_companies = {
    "삼성전자 (005930.KS)": "005930.KS",
    "SK하이닉스 (000660.KS)": "000660.KS",
    "LG에너지솔루션 (373220.KS)": "373220.KS",
    "삼성바이오로직스 (207940.KS)": "207940.KS",
    "현대자동차 (005380.KS)": "005380.KS",
    "기아 (000270.KS)": "000270.KS",
    "셀트리온 (068270.KS)": "068270.KS",
    "POSCO홀딩스 (005490.KS)": "005490.KS",
    "NAVER (035420.KS)": "035420.KS",
    "LG화학 (051910.KS)": "051910.KS",
    "KB금융 (105560.KS)": "105560.KS",
    "신한지주 (055550.KS)": "055550.KS",
    "삼성물산 (028260.KS)": "028260.KS",
    "현대모비스 (012330.KS)": "012330.KS",
    "카카오 (035720.KS)": "035720.KS",
    "SK이노베이션 (096770.KS)": "096770.KS",
    "하나금융지주 (086790.KS)": "086790.KS",
    "LG전자 (066570.KS)": "066570.KS",
    "삼성생명 (032830.KS)": "032830.KS",
    "SK텔레콤 (017670.KS)": "017670.KS",
    "KT&G (033780.KS)": "033780.KS",
    "한국전력 (015760.KS)": "015760.KS",
    "우리금융지주 (316140.KS)": "316140.KS",
    "HMM (011200.KS)": "011200.KS",
    "고려아연 (010130.KS)": "010130.KS",
    "삼성화재 (000810.KS)": "000810.KS",
    "S-Oil (010950.KS)": "010950.KS",
    "HD현대중공업 (329180.KS)": "329180.KS",
    "기업은행 (024110.KS)": "024110.KS",
    "아모레퍼시픽 (090430.KS)": "090430.KS"
}

# --- UI 섹션 ---
st.sidebar.header("설정")
market_choice = st.sidebar.selectbox(
    "시장 선택",
    ["전 세계 Top 30", "대한민국 Top 30"]
)

if market_choice == "전 세계 Top 30":
    companies_to_display = global_top_companies
    default_company_name = list(global_top_companies.keys())[0]
else: # 대한민국 Top 30
    companies_to_display = korean_top_companies
    default_company_name = list(korean_top_companies.keys())[0]

# 기업 선택
selected_company_name = st.sidebar.selectbox(
    "기업 선택",
    list(companies_to_display.keys()),
    index=list(companies_to_display.keys()).index(default_company_name) # 기본 선택
)
ticker = companies_to_display[selected_company_name]

# 날짜 선택
today = date.today()
default_start = today - timedelta(days=365)

# 사이드바로 날짜 선택 UI 이동
start_date, end_date = st.sidebar.date_input(
    "조회 기간 선택 (기본: 최근 1년)",
    value=(default_start, today),
    max_value=today
)

# --- 데이터 처리 및 시각화 ---
if start_date >= end_date:
    st.error("❗ 시작일은 종료일보다 앞서야 합니다.")
else:
    yf_end_date = end_date + timedelta(days=1)  # yfinance는 end를 포함하지 않음

    # 메인 영역에 로딩 스피너와 차트 표시
    st.subheader(f"{selected_company_name} 주가 정보")
    with st.spinner(f"📡 {selected_company_name} 주가 데이터를 불러오는 중..."):
        try:
            data = yf.download(ticker, start=start_date, end=yf_end_date, progress=False)
        except Exception as e:
            st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
            data = None # 오류 발생 시 data를 None으로 설정

    if data is not None and not data.empty and len(data) >= 1: # 데이터가 최소 1개 이상 있을 때
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines+markers", name="종가"))

        # 이동평균선 추가 (20일)
        if len(data) >= 20:
            data['MA20'] = data['Close'].rolling(window=20).mean()
            fig.add_trace(go.Scatter(x=data.index, y=data['MA20'], mode='lines', name='20일 이동평균', line=dict(color='orange', dash='dash')))

        fig.update_layout(
            title=f"{selected_company_name} 주가 추이 ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})",
            xaxis_title="날짜",
            yaxis_title=f"종가 ({yf.Ticker(ticker).info.get('currency', '현지 통화')})", # 통화 정보 가져오기 시도
            template="plotly_white",
            height=600,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        # 최근 데이터 테이블 표시
        st.subheader("최근 데이터")
        st.dataframe(data.tail().sort_index(ascending=False))

        # 주요 정보 표시 (yfinance Ticker 객체 활용)
        try:
            ticker_info = yf.Ticker(ticker).info
            info_cols = st.columns(2)
            with info_cols[0]:
                st.markdown("#### 기업 정보")
                st.write(f"**기업명:** {ticker_info.get('longName', selected_company_name)}")
                st.write(f"**섹터:** {ticker_info.get('sector', 'N/A')}")
                st.write(f"**산업:** {ticker_info.get('industry', 'N/A')}")
                st.write(f"**웹사이트:** {ticker_info.get('website', 'N/A')}")

            with info_cols[1]:
                st.markdown("#### 주요 주가 지표")
                st.write(f"**현재가:** {ticker_info.get('currentPrice', 'N/A')} {ticker_info.get('currency', '')}")
                st.write(f"**시가총액:** {ticker_info.get('marketCap', 'N/A'):,} {ticker_info.get('currency', '')}")
                st.write(f"**52주 최고가:** {ticker_info.get('fiftyTwoWeekHigh', 'N/A')}")
                st.write(f"**52주 최저가:** {ticker_info.get('fiftyTwoWeekLow', 'N/A')}")
                st.write(f"**거래량:** {ticker_info.get('volume', 'N/A'):,}")

        except Exception as e:
            st.warning(f"기업 상세 정보를 불러오는 데 실패했습니다: {e}")

    elif data is not None and data.empty: # 데이터는 있으나 비어있는 경우 (예: 해당 기간 거래 없음)
        st.warning(f"📉 선택한 기간 '{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}'에 대한 {selected_company_name}의 주가 데이터가 없습니다. 다른 기간을 선택해 보세요.")
    elif data is None: # 데이터 로드 실패 시
        pass # 오류 메시지는 이미 위에서 표시됨
    else: # len(data) < 1 인 경우는 사실상 empty와 유사
         st.warning(f"📉 선택한 기간에 유효한 주가 데이터가 부족합니다. 기간을 늘려보세요. (데이터 포인트 수: {len(data)})")

# 앱 설명 추가 (선택적)
st.sidebar.markdown("---")
st.sidebar.info(
    "이 앱은 전 세계 및 대한민국의 시가총액 상위 기업들의 주가를 시각화합니다. "
    "데이터는 Yahoo Finance에서 제공받으며, 실제 투자 결정은 신중하게 이루어져야 합니다."
)
