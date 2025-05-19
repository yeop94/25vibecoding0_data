import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🗺️ 클릭해서 지명을 직접 입력하고 마커 찍기")

# 지도 초기 설정
map_center = [37.5665, 126.9780]  # 서울 기준
m = folium.Map(location=map_center, zoom_start=6)

# 클릭 위치 수신
click_result = st_folium(m, width=700, height=500, returned_objects=["last_clicked"], key="input_map")

# 세션 상태에 위치 목록 저장
if "locations" not in st.session_state:
    st.session_state.locations = []

# 클릭하면 위치 입력 필드 표시
if click_result and click_result["last_clicked"]:
    lat = click_result["last_clicked"]["lat"]
    lon = click_result["last_clicked"]["lng"]
    st.success(f"선택된 위치: 위도 {lat:.5f}, 경도 {lon:.5f}")
    
    with st.form("label_form", clear_on_submit=True):
        label = st.text_input("지명 또는 장소 이름 입력", value=f"마커 {len(st.session_state.locations)+1}")
        submitted = st.form_submit_button("마커 저장")
        if submitted:
            st.session_state.locations.append({
                "label": label,
                "lat": lat,
                "lon": lon
            })
            st.toast(f"📍 '{label}' 위치가 저장되었습니다.", icon="📌")

# 저장된 마커들을 지도에 다시 표시
m2 = folium.Map(location=map_center, zoom_start=6)
for loc in st.session_state.locations:
    folium.Marker([loc["lat"], loc["lon"]], tooltip=loc["label"]).add_to(m2)

st.subheader("🗺️ 마커가 표시된 지도")
st_folium(m2, width=700, height=500, key="result_map")  # ❗ 고유 key 추가

# 목록도 텍스트로 출력
if st.session_state.locations:
    st.subheader("📋 저장된 위치 목록")
    for i, loc in enumerate(st.session_state.locations, 1):
        st.markdown(f"{i}. **{loc['label']}** - 위도: `{loc['lat']:.5f}`, 경도: `{loc['lon']:.5f}`")
else:
    st.info("아직 저장된 위치가 없습니다.")
