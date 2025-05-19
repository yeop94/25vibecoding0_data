import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# 한글 폰트 설정 - 시스템에 koreanize-matplotlib이 설치되어 있다면 임포트
try:
    import koreanize_matplotlib
except ImportError:
    st.warning("koreanize_matplotlib이 설치되어 있지 않습니다. 한글이 깨질 수 있습니다.")

st.set_page_config(layout="wide", page_title="투자 포트폴리오 시뮬레이터")
st.title('📈 투자 포트폴리오 시뮬레이터')
st.markdown('실시간 야후 파이낸스 데이터를 활용한 투자 포트폴리오 시뮬레이션 도구')

# 한국 주요 기업 심볼 (코스피)
kr_symbols = {
    '삼성전자': '005930.KS',
    'SK하이닉스': '000660.KS',
    '네이버': '035420.KS',
    '카카오': '035720.KS',
    '현대차': '005380.KS',
    'LG화학': '051910.KS',
    '셀트리온': '068270.KS',
    '삼성바이오로직스': '207940.KS',
    'POSCO홀딩스': '005490.KS',
    '기아': '000270.KS'
}

# 미국 주요 기업 심볼
us_symbols = {
    'Apple': 'AAPL',
    'Microsoft': 'MSFT',
    'Amazon': 'AMZN',
    'Google': 'GOOGL',
    'Facebook': 'META',
    'Tesla': 'TSLA',
    'NVIDIA': 'NVDA',
    'Netflix': 'NFLX',
    'JPMorgan Chase': 'JPM',
    'Berkshire Hathaway': 'BRK-B'
}

# 사이드바 - 포트폴리오 설정
st.sidebar.header('포트폴리오 설정')

# 투자 기간 설정
start_date = st.sidebar.date_input(
    "투자 시작일",
    datetime.now() - timedelta(days=365)
)

end_date = st.sidebar.date_input(
    "투자 종료일",
    datetime.now()
)

# 날짜 유효성 검사
if start_date >= end_date:
    st.sidebar.error("종료일은 시작일보다 이후여야 합니다.")
    st.stop()

# 최소 데이터 기간 확인 (최소 30일)
if (end_date - start_date).days < 30:
    st.sidebar.warning("정확한 분석을 위해 최소 30일 이상의 기간을 선택하세요.")
    min_date = end_date - timedelta(days=30)
    st.sidebar.info(f"권장 시작일: {min_date.strftime('%Y-%m-%d')} 이전")

# 주식 선택
st.sidebar.subheader('주식 선택')
market = st.sidebar.radio('시장 선택', ['한국 주식', '미국 주식', '혼합'])

selected_stocks = []
weights = []

if market in ['한국 주식', '혼합']:
    kr_selected = st.sidebar.multiselect(
        '한국 주식 선택',
        list(kr_symbols.keys()),
        default=['삼성전자', 'SK하이닉스'] if market == '한국 주식' else ['삼성전자']
    )
    selected_stocks.extend([kr_symbols[stock] for stock in kr_selected])
    
    # 각 주식 가중치 설정
    if kr_selected:
        st.sidebar.subheader('한국 주식 가중치 (%)')
        kr_weights = []
        for stock in kr_selected:
            weight = st.sidebar.slider(f'{stock} 비중', 0, 100, 100 // len(kr_selected) if kr_selected else 0)
            kr_weights.append(weight)
        weights.extend(kr_weights)

if market in ['미국 주식', '혼합']:
    us_selected = st.sidebar.multiselect(
        '미국 주식 선택',
        list(us_symbols.keys()),
        default=['Apple', 'Microsoft'] if market == '미국 주식' else ['Apple']
    )
    selected_stocks.extend([us_symbols[stock] for stock in us_selected])
    
    # 각 주식 가중치 설정
    if us_selected:
        st.sidebar.subheader('미국 주식 가중치 (%)')
        us_weights = []
        for stock in us_selected:
            weight = st.sidebar.slider(f'{stock} 비중', 0, 100, 100 // len(us_selected) if us_selected else 0)
            us_weights.append(weight)
        weights.extend(us_weights)

# 초기 투자금 설정
investment_amount = st.sidebar.number_input('초기 투자금 (원)', value=10000000, step=1000000, min_value=1000000)

# 리밸런싱 옵션
rebalance = st.sidebar.checkbox('정기 리밸런싱', value=False)
if rebalance:
    rebalance_freq = st.sidebar.selectbox('리밸런싱 주기', ['월별', '분기별', '반기별', '연간'], index=1)

# 데이터 로드 및 분석
if selected_stocks and sum(weights) == 100:
    # 진행 상태 표시
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 주식 데이터 로드
    status_text.text('주식 데이터를 불러오는 중...')
    
    all_data = {}
    valid_data_count = 0
    
    for i, symbol in enumerate(selected_stocks):
        try:
            progress_bar.progress((i+1)/len(selected_stocks))
            stock_data = yf.download(symbol, start=start_date, end=end_date)
            
            # 데이터가 비어있는지 확인
            if not stock_data.empty and len(stock_data) > 5:  # 최소 5일치 데이터 필요
                all_data[symbol] = stock_data
                valid_data_count += 1
                status_text.text(f'{symbol} 데이터 로드 완료 ({i+1}/{len(selected_stocks)})')
            else:
                st.warning(f"{symbol}에 대한 충분한 데이터가 없습니다. 다른 기간이나 주식을 선택해보세요.")
        except Exception as e:
            st.error(f"{symbol} 데이터 로드 중 오류 발생: {e}")
    
    status_text.text('데이터 로드 완료!')
    progress_bar.empty()
    
    # 유효한 데이터가 있는지 확인
    if valid_data_count == 0:
        st.error("유효한 주식 데이터를 찾을 수 없습니다. 다른 주식이나 기간을 선택해보세요.")
        st.stop()
    
    # 실제 로드된 주식만 가중치 계산에 사용
    valid_symbols = list(all_data.keys())
    valid_weights = []
    valid_names = []
    
    # 로드된 주식에 대한 가중치 재계산
    total_weight = 0
    for i, symbol in enumerate(selected_stocks):
        if symbol in valid_symbols:
            valid_weights.append(weights[i])
            total_weight += weights[i]
            
            # 심볼에 해당하는 회사명 찾기
            company_name = None
            for k, v in kr_symbols.items():
                if v == symbol:
                    company_name = k + ' (KR)'
                    break
            if not company_name:
                for k, v in us_symbols.items():
                    if v == symbol:
                        company_name = k + ' (US)'
                        break
            if not company_name:
                company_name = symbol
            
            valid_names.append(company_name)
    
    # 가중치 정규화 (합이 100%가 되도록)
    if total_weight > 0:
        valid_weights = [w * 100 / total_weight for w in valid_weights]
    else:
        st.error("유효한 주식의 가중치 합이 0입니다.")
        st.stop()
    
    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 가격 추이", "📉 수익률 분석", "🔄 포트폴리오 시뮬레이션", "📊 위험 분석"])
    
    with tab1:
        st.subheader('주식 가격 추이')
        
        # 주식별 종가 그래프
        fig = go.Figure()
        
        # 각 주식 데이터 시각화
        for symbol in all_data:
            # 심볼에 해당하는 회사명 찾기
            company_name = None
            for k, v in kr_symbols.items():
                if v == symbol:
                    company_name = k + ' (KR)'
                    break
            if not company_name:
                for k, v in us_symbols.items():
                    if v == symbol:
                        company_name = k + ' (US)'
                        break
            if not company_name:
                company_name = symbol
            
            # 정규화된 가격(시작일 대비 백분율)
            normalized_price = all_data[symbol]['Close'] / all_data[symbol]['Close'].iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=all_data[symbol].index,
                y=normalized_price,
                mode='lines',
                name=company_name
            ))
        
        fig.update_layout(
            title='투자 기간 동안의 정규화된 주가 추이 (시작일 = 100%)',
            xaxis_title='날짜',
            yaxis_title='정규화된 가격 (%)',
            height=600
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 실제 종가 데이터
        st.subheader('실제 종가 데이터')
        
        # 각 주식별 최신 데이터 표시
        stock_summary = []
        for symbol in all_data:
            company_name = None
            for k, v in {**kr_symbols, **us_symbols}.items():
                if v == symbol:
                    company_name = k
                    break
            if not company_name:
                company_name = symbol
            
            latest_data = all_data[symbol].iloc[-1]
            first_data = all_data[symbol].iloc[0]
            price_change = (latest_data['Close'] - first_data['Close']) / first_data['Close'] * 100
            
            stock_summary.append({
                '종목': company_name,
                '심볼': symbol,
                '현재가': latest_data['Close'],
                '시작가': first_data['Close'],
                '변동률(%)': price_change,
                '거래량': latest_data['Volume']
            })
        
        summary_df = pd.DataFrame(stock_summary)
        st.dataframe(summary_df, width=1000)
    
    with tab2:
        st.subheader('수익률 분석')
        
        # 일별 수익률 계산
        returns_data = {}
        for symbol in all_data:
            if len(all_data[symbol]) > 1:  # 최소 2개 이상의 데이터 포인트 필요
                returns_data[symbol] = all_data[symbol]['Close'].pct_change().dropna()
        
        # 데이터 프레임 생성 전 확인
        if not returns_data:
            st.error("수익률을 계산할 수 있는 데이터가 없습니다.")
            st.stop()
        
        # 반환 데이터로 데이터프레임 생성
        try:
            returns_df = pd.DataFrame(returns_data)
            
            # 데이터프레임이 비어있는지 확인
            if returns_df.empty:
                st.error("수익률 데이터프레임이 비어있습니다.")
                st.stop()
        except ValueError as e:
            st.error(f"데이터프레임 생성 중 오류 발생: {e}")
            st.error("충분한 데이터가 없습니다. 다른 주식이나 더 긴 기간을 선택해보세요.")
            st.stop()
        
        # 누적 수익률 계산
        try:
            cumulative_returns = (1 + returns_df).cumprod() - 1
            
            # 누적 수익률 시각화
            fig = go.Figure()
            for column in cumulative_returns.columns:
                company_name = None
                for k, v in {**kr_symbols, **us_symbols}.items():
                    if v == column:
                        company_name = k
                        break
                if not company_name:
                    company_name = column
                
                fig.add_trace(go.Scatter(
                    x=cumulative_returns.index,
                    y=cumulative_returns[column] * 100,
                    mode='lines',
                    name=company_name
                ))
            
            fig.update_layout(
                title='누적 수익률 (%)',
                xaxis_title='날짜',
                yaxis_title='누적 수익률 (%)',
                height=600
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"누적 수익률 계산 중 오류 발생: {e}")
            st.stop()
        
        # 수익률 통계
        st.subheader('수익률 통계')
        
        try:
            # 연간 수익률
            annual_returns = returns_df.mean() * 252 * 100
            annual_volatility = returns_df.std() * np.sqrt(252) * 100
            
            # Sharpe Ratio 계산 (분모가 0이 되지 않도록 확인)
            sharpe_ratio = pd.Series(index=annual_returns.index)
            for idx in annual_returns.index:
                if annual_volatility[idx] > 0:
                    sharpe_ratio[idx] = annual_returns[idx] / annual_volatility[idx]
                else:
                    sharpe_ratio[idx] = np.nan
            
            stats_df = pd.DataFrame({
                '연간 수익률(%)': annual_returns,
                '연간 변동성(%)': annual_volatility,
                'Sharpe Ratio': sharpe_ratio
            })
            
            # 인덱스를 회사명으로 변경
            stats_df.index = [next((k for k, v in {**kr_symbols, **us_symbols}.items() if v == idx), idx) for idx in stats_df.index]
            
            st.dataframe(stats_df, width=1000)
        except Exception as e:
            st.error(f"수익률 통계 계산 중 오류 발생: {e}")
        
        # 상관관계 히트맵
        try:
            if len(returns_df.columns) > 1:  # 2개 이상의 주식이 있을 때만 상관관계 표시
                st.subheader('수익률 상관관계')
                corr_matrix = returns_df.corr()
                
                # 인덱스와 컬럼을 회사명으로 변경
                company_names = [next((k for k, v in {**kr_symbols, **us_symbols}.items() if v == idx), idx) for idx in corr_matrix.index]
                corr_matrix.index = company_names
                corr_matrix.columns = company_names
                
                fig_corr = px.imshow(
                    corr_matrix,
                    color_continuous_scale='RdBu_r',
                    labels=dict(x="종목", y="종목", color="상관계수"),
                    x=company_names,
                    y=company_names
                )
                fig_corr.update_layout(height=600)
                st.plotly_chart(fig_corr, use_container_width=True)
        except Exception as e:
            st.error(f"상관관계 계산 중 오류 발생: {e}")
    
    with tab3:
        st.subheader('포트폴리오 시뮬레이션')
        
        try:
            # 포트폴리오 가중치 정규화
            weights_array = np.array(valid_weights) / 100
            
            # 포트폴리오 수익률 계산
            port_returns = pd.DataFrame()
            
            for i, symbol in enumerate(valid_symbols):
                company_name = None
                for k, v in {**kr_symbols, **us_symbols}.items():
                    if v == symbol:
                        company_name = k
                        break
                if not company_name:
                    company_name = symbol
                
                if symbol in all_data and len(all_data[symbol]) > 1:
                    port_returns[company_name] = all_data[symbol]['Close'].pct_change().dropna() * weights_array[i]
            
            # 충분한 데이터가 있는지 확인
            if port_returns.empty:
                st.error("포트폴리오 수익률을 계산할 수 있는 충분한 데이터가 없습니다.")
                st.stop()
            
            # 포트폴리오 전체 수익률 계산
            port_returns['Portfolio'] = port_returns.sum(axis=1)
            
            # 누적 수익률
            cumulative_port_returns = (1 + port_returns).cumprod() - 1
            
            # 누적 투자금액 계산
            portfolio_value = (1 + cumulative_port_returns['Portfolio']) * investment_amount
            
            # 포트폴리오 시각화
            fig_port = go.Figure()
            
            fig_port.add_trace(go.Scatter(
                x=portfolio_value.index,
                y=portfolio_value,
                mode='lines',
                name='포트폴리오 가치',
                fill='tozeroy'
            ))
            
            fig_port.update_layout(
                title=f'포트폴리오 가치 시뮬레이션 (초기 투자: {investment_amount:,}원)',
                xaxis_title='날짜',
                yaxis_title='포트폴리오 가치 (원)',
                height=600
            )
            
            st.plotly_chart(fig_port, use_container_width=True)
            
            # 포트폴리오 성과 요약
            if len(portfolio_value) > 0:
                final_value = portfolio_value.iloc[-1]
                total_return = (final_value - investment_amount) / investment_amount * 100
                
                # 투자 기간이 충분한 경우에만 연율화 수익률 계산
                if len(portfolio_value) > 5:  # 최소 5일 이상의 데이터 필요
                    days = (portfolio_value.index[-1] - portfolio_value.index[0]).days
                    if days > 0:
                        annualized_return = (final_value / investment_amount) ** (365 / days) - 1
                        annualized_return *= 100
                    else:
                        annualized_return = 0
                else:
                    annualized_return = 0
                
                # 3열 지표 표시
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("최종 포트폴리오 가치", f"{final_value:,.0f}원")
                with col2:
                    st.metric("총 수익률", f"{total_return:.2f}%")
                with col3:
                    st.metric("연율화 수익률", f"{annualized_return:.2f}%")
            else:
                st.warning("포트폴리오 가치를 계산할 수 있는 충분한 데이터가 없습니다.")
            
            # 포트폴리오 구성 파이 차트
            st.subheader('포트폴리오 구성')
            
            fig_pie = px.pie(
                names=valid_names,
                values=valid_weights,
                title='포트폴리오 자산 배분'
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # 월별 수익률 표시
            if not port_returns.empty and len(port_returns) > 20:  # 최소 20일 이상의 데이터 필요
                st.subheader('월별 포트폴리오 수익률')
                
                try:
                    # 월별 수익률 계산
                    monthly_returns = port_returns['Portfolio'].resample('M').apply(lambda x: (1 + x).prod() - 1)
                    
                    if len(monthly_returns) > 0:
                        fig_monthly = px.bar(
                            x=monthly_returns.index,
                            y=monthly_returns * 100,
                            labels={'x': '월', 'y': '수익률 (%)'},
                            title='월별 포트폴리오 수익률 (%)'
                        )
                        
                        fig_monthly.update_layout(height=500)
                        st.plotly_chart(fig_monthly, use_container_width=True)
                    else:
                        st.info("월별 수익률을 계산할 수 있는 충분한 데이터가 없습니다.")
                except Exception as e:
                    st.error(f"월별 수익률 계산 중 오류 발생: {e}")
        except Exception as e:
            st.error(f"포트폴리오 시뮬레이션 중 오류 발생: {e}")
    
    with tab4:
        st.subheader('위험 분석')
        
        try:
            if 'Portfolio' in port_returns.columns and len(port_returns) > 5:
                # 일별 VaR (Value at Risk) 계산
                port_std = port_returns['Portfolio'].std()
                var_95 = port_returns['Portfolio'].quantile(0.05)
                var_99 = port_returns['Portfolio'].quantile(0.01)
                
                cvar_95 = port_returns['Portfolio'][port_returns['Portfolio'] <= var_95].mean()
                cvar_99 = port_returns['Portfolio'][port_returns['Portfolio'] <= var_99].mean()
                
                # 일별 수익률 분포
                fig_hist = px.histogram(
                    port_returns['Portfolio'],
                    nbins=50,
                    labels={'value': '일별 수익률', 'count': '빈도'},
                    title='포트폴리오 일별 수익률 분포'
                )
                
                # VaR 라인 추가
                fig_hist.add_vline(x=var_95, line_dash="dash", line_color="red", 
                                  annotation_text="95% VaR", annotation_position="top right")
                fig_hist.add_vline(x=var_99, line_dash="dash", line_color="darkred", 
                                  annotation_text="99% VaR", annotation_position="top right")
                
                fig_hist.update_layout(height=500)
                st.plotly_chart(fig_hist, use_container_width=True)
                
                # VaR 및 CVaR 요약
                st.subheader('Value at Risk (VaR) 분석')
                st.write('VaR은 정상적인 시장 조건에서 특정 기간 동안 발생할 수 있는 최대 손실을 나타냅니다.')
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("일별 95% VaR", f"{var_95*100:.2f}%")
                    st.write(f"95% 확률로 하루에 {var_95*investment_amount:,.0f}원 이상 손실이 발생하지 않을 것으로 예상됩니다.")
                with col2:
                    st.metric("일별 99% VaR", f"{var_99*100:.2f}%")
                    st.write(f"99% 확률로 하루에 {var_99*investment_amount:,.0f}원 이상 손실이 발생하지 않을 것으로 예상됩니다.")
                
                # 스트레스 테스트
                st.subheader('스트레스 테스트')
                st.write('과거 데이터를 기반으로 극단적인 시장 상황에서 포트폴리오가 어떻게 반응할지 시뮬레이션합니다.')
                
                # 최악의 날들 보여주기
                if len(port_returns['Portfolio']) >= 5:
                    worst_days = port_returns['Portfolio'].sort_values().head(min(5, len(port_returns['Portfolio'])))
                    best_days = port_returns['Portfolio'].sort_values(ascending=False).head(min(5, len(port_returns['Portfolio'])))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"#### 최악의 {len(worst_days)}일")
                        worst_days_df = pd.DataFrame({
                            '날짜': worst_days.index,
                            '손실 (%)': worst_days * 100
                        })
                        st.dataframe(worst_days_df, width=400)
                        
                    with col2:
                        st.write(f"#### 최고의 {len(best_days)}일")
                        best_days_df = pd.DataFrame({
                            '날짜': best_days.index,
                            '수익 (%)': best_days * 100
                        })
                        st.dataframe(best_days_df, width=400)
                    
                    # 최악의 시나리오 시뮬레이션
                    st.write("#### 최악의 시나리오 시뮬레이션")
                    days_to_simulate = min(5, len(worst_days))
                    st.write(f"만약 {days_to_simulate}일 연속으로 최악의 날이 발생한다면:")
                    
                    worst_scenario = (1 + worst_days.mean()) ** days_to_simulate - 1
                    worst_value = investment_amount * (1 + worst_scenario)
                    
                    st.metric(f"{days_to_simulate}일 후 예상 포트폴리오 가치", f"{worst_value:,.0f}원", f"{worst_scenario*100:.2f}%")
                else:
                    st.info("스트레스 테스트를 위한 충분한 데이터가 없습니다.")
                
                # 드롭다운 분석
                if len(portfolio_value) > 1:
                    max_drawdown = (portfolio_value / portfolio_value.cummax() - 1).min()
                    
                    st.metric("최대 낙폭 (Maximum Drawdown)", f"{max_drawdown*100:.2f}%")
                    
                    # 드롭다운 시각화
                    drawdown = (portfolio_value / portfolio_value.cummax() - 1) * 100
                    
                    fig_dd = px.line(
                        x=drawdown.index,
                        y=drawdown,
                        labels={'x': '날짜', 'y': '낙폭 (%)'},
                        title='포트폴리오 낙폭 (%)'
                    )
                    
                    fig_dd.update_layout(height=500)
                    st.plotly_chart(fig_dd, use_container_width=True)
                else:
                    st.info("최대 낙폭 분석을 위한 충분한 데이터가 없습니다.")
            else:
                st.info("위험 분석을 위한 충분한 포트폴리오 데이터가 없습니다.")
        except Exception as e:
            st.error(f"위험 분석 중 오류 발생: {e}")

elif selected_stocks and sum(weights) != 100:
    st.warning('포트폴리오 가중치의 합이 100%가 되어야 합니다. 현재: {}%'.format(sum(weights)))
else:
    st.info('포트폴리오를 구성하려면 왼쪽 사이드바에서 주식을 선택하고 가중치를 설정해주세요.')

# 앱 정보
st.sidebar.markdown('---')
st.sidebar.info('이 앱은 야후 파이낸스 API를 사용하여 실시간 주식 데이터를 가져옵니다. 교육 목적으로만 사용하세요.')
