import streamlit as st
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
import requests
import polyline
from datetime import datetime
import math

# --- Streamlit 페이지 설정 ---
st.set_page_config(layout="wide", page_title="지도 & 경로 안내", page_icon="🗺️")

# --- API 키 및 설정 ---
GOOGLE_MAPS_API_KEY = st.secrets.get("google_maps_api_key", "")
GOOGLE_SHEET_NAME = "내 마커 데이터"
WORKSHEET_NAME = "Sheet1"

# --- Google Sheets 연결 함수 ---
def init_gspread_client():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Google Sheets 인증 실패: {e}")
        return None

def get_worksheet(gc, sheet_name):
    try:
        spreadsheet = gc.open(sheet_name)
        return spreadsheet.worksheet(WORKSHEET_NAME)
    except Exception as e:
        st.error(f"워크시트 접근 오류: {e}")
        return None

def load_locations_from_sheet(worksheet):
    if worksheet is None:
        return []
    try:
        records = worksheet.get_all_records()
        locations = []
        for i, record in enumerate(records):
            try:
                lat, lon = record.get("Latitude"), record.get("Longitude")
                if lat is None or lon is None:
                    continue
                locations.append({
                    "label": str(record.get("Label", f"마커 {i+1}")),
                    "lat": float(lat),
                    "lon": float(lon)
                })
            except ValueError:
                continue
        return locations
    except Exception as e:
        st.error(f"데이터 로딩 오류: {e}")
        return []

def add_location_to_sheet(worksheet, location_data):
    if worksheet is None:
        return False
    try:
        worksheet.append_row([location_data["label"], location_data["lat"], location_data["lon"]])
        return True
    except Exception as e:
        st.error(f"데이터 추가 오류: {e}")
        return False

# --- 경로 계산 함수 ---
def get_directions(origin_lat, origin_lng, dest_lat, dest_lng, mode="driving"):
    if not GOOGLE_MAPS_API_KEY:
        return {"error_message": "Google Maps API 키가 설정되지 않았습니다."}
    
    # 두 지점 간 직선 거리 계산 (km)
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # 지구 반경 (km)
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = math.sin(dLat/2) * math.sin(dLat/2) + math.cos(math.radians(lat1)) \
            * math.cos(math.radians(lat2)) * math.sin(dLon/2) * math.sin(dLon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        d = R * c
        return d
    
    # 직선 거리 계산
    direct_distance = haversine(origin_lat, origin_lng, dest_lat, dest_lng)
    
    # 도보 모드에서 거리 체크 (100km 이상일 경우 경고)
    if mode == "walking" and direct_distance > 100:
        return {
            "error_message": f"도보 경로 거리 제한 초과 (직선거리: {direct_distance:.1f}km)"
        }
    
    base_url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{origin_lat},{origin_lng}",
        "destination": f"{dest_lat},{dest_lng}",
        "mode": mode,
        "key": GOOGLE_MAPS_API_KEY,
        "language": "ko"
    }
    
    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data["status"] == "OK" and data["routes"]:
            route = data["routes"][0]
            leg = route["legs"][0]
            route_polyline = route["overview_polyline"]["points"]
            decoded_polyline = polyline.decode(route_polyline)
            
            return {
                "duration": leg["duration"]["text"],
                "distance": leg["distance"]["text"],
                "polyline": decoded_polyline
            }
        elif data["status"] == "ZERO_RESULTS":
            error_messages = {
                "walking": "도보 경로를 찾을 수 없습니다.",
                "driving": "운전 경로를 찾을 수 없습니다."
            }
            return {"error_message": error_messages.get(mode, "경로를 찾을 수 없습니다.")}
        else:
            return {"error_message": f"{data.get('status', '알 수 없는 오류')}"}
    except Exception as e:
        return {"error_message": f"API 오류: {str(e)}"}

# --- 세션 상태 초기화 ---
if "locations" not in st.session_state:
    st.session_state.locations = []
if "map_center" not in st.session_state:
    st.session_state.map_center = [37.5665, 126.9780]  # 서울 중심
if "zoom_start" not in st.session_state:
    st.session_state.zoom_start = 12
if "last_clicked_coord" not in st.session_state:
    st.session_state.last_clicked_coord = None
if "route_origin_label" not in st.session_state:  # 변수명 수정
    st.session_state.route_origin_label = None
if "route_destination_label" not in st.session_state:  # 변수명 수정
    st.session_state.route_destination_label = None
if "route_results" not in st.session_state:
    st.session_state.route_results = None
if "calculating_route" not in st.session_state:
    st.session_state.calculating_route = False
if "gs_client" not in st.session_state:
    st.session_state.gs_client = None
if "worksheet" not in st.session_state:
    st.session_state.worksheet = None
if "data_loaded_from_sheet" not in st.session_state:
    st.session_state.data_loaded_from_sheet = False

# --- Google Sheets 연결 ---
if not st.session_state.gs_client:
    st.session_state.gs_client = init_gspread_client()

if st.session_state.gs_client and not st.session_state.worksheet:
    st.session_state.worksheet = get_worksheet(st.session_state.gs_client, GOOGLE_SHEET_NAME)

# --- 데이터 로드 ---
if st.session_state.worksheet and not st.session_state.data_loaded_from_sheet:
    with st.spinner("데이터 로드 중..."):
        st.session_state.locations = load_locations_from_sheet(st.session_state.worksheet)
        st.session_state.data_loaded_from_sheet = True

# --- 앱 타이틀 ---
st.title("🗺️ 마커 저장 및 경로 안내")

# --- 레이아웃 설정 ---
col1, col2 = st.columns([3, 1])

with col1:
    # --- 지도 생성 ---
    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.zoom_start)
    
    # --- 경로 폴리라인 추가 ---
    if st.session_state.route_results:
        walking_info = st.session_state.route_results.get("walking", {})
        if walking_info and "polyline" in walking_info and "error_message" not in walking_info:
            folium.PolyLine(
                locations=walking_info["polyline"],
                weight=4,
                color='blue',
                opacity=0.7,
                tooltip="도보 경로"
            ).add_to(m)
            
        driving_info = st.session_state.route_results.get("driving", {})
        if driving_info and "polyline" in driving_info and "error_message" not in driving_info:
            folium.PolyLine(
                locations=driving_info["polyline"],
                weight=5,
                color='red',
                opacity=0.7,
                tooltip="자동차 경로"
            ).add_to(m)
    
    # --- 마커 표시 ---
    for loc in st.session_state.locations:
        icon_color, icon_symbol = 'blue', 'info-sign'
        if st.session_state.route_origin_label == loc["label"]:
            icon_color, icon_symbol = 'green', 'play'
        elif st.session_state.route_destination_label == loc["label"]:
            icon_color, icon_symbol = 'red', 'flag'
        
        folium.Marker(
            [loc["lat"], loc["lon"]],
            tooltip=loc["label"],
            popup=loc["label"],
            icon=folium.Icon(color=icon_color, icon=icon_symbol)
        ).add_to(m)
    
    # --- 마지막 클릭 위치 마커 ---
    if st.session_state.last_clicked_coord:
        folium.Marker(
            [st.session_state.last_clicked_coord["lat"], st.session_state.last_clicked_coord["lng"]],
            tooltip="선택된 위치",
            icon=folium.Icon(color='purple', icon='plus')
        ).add_to(m)
    
    # --- 지도 렌더링 ---
    map_data = st_folium(m, width="100%", height=500)
    
    # --- 지도 상호작용 처리 ---
    if map_data:
        if map_data.get("center"):
            st.session_state.map_center = map_data["center"]
        if map_data.get("zoom"):
            st.session_state.zoom_start = map_data["zoom"]
        if map_data.get("last_clicked"):
            st.session_state.last_clicked_coord = map_data["last_clicked"]

with col2:
    # --- 마커 추가 ---
    st.subheader("📍 마커 추가")
    if st.session_state.last_clicked_coord:
        lat, lng = st.session_state.last_clicked_coord["lat"], st.session_state.last_clicked_coord["lng"]
        st.info(f"선택 위치: {lat:.5f}, {lng:.5f}")
        
        label = st.text_input("장소 이름", value=f"마커 {len(st.session_state.locations) + 1}")
        
        if st.button("✅ 마커 저장"):
            if st.session_state.worksheet:
                new_loc = {"label": label, "lat": lat, "lon": lng}
                if add_location_to_sheet(st.session_state.worksheet, new_loc):
                    st.session_state.locations.append(new_loc)
                    st.success(f"'{label}' 저장 완료!")
                    st.session_state.last_clicked_coord = None
                    st.rerun()  # experimental_rerun 대신 rerun 사용
    else:
        st.info("마커를 추가하려면 지도를 클릭하세요.")
    
    # --- 경로 찾기 ---
    st.subheader("🚗 경로 찾기")
    if len(st.session_state.locations) >= 2:
        marker_options = ["선택하세요"] + [loc["label"] for loc in st.session_state.locations]
        origin = st.selectbox("출발지:", marker_options, index=0, key="origin")
        destination = st.selectbox("도착지:", marker_options, index=0, key="destination")
        
        travel_mode = st.radio("이동 수단:", ["자동차", "도보", "모두"], horizontal=True)
        
        if st.button("🔍 경로 계산"):
            if origin != "선택하세요" and destination != "선택하세요" and origin != destination:
                st.session_state.route_origin_label = origin
                st.session_state.route_destination_label = destination
                
                # 출발지/도착지 좌표 찾기
                origin_loc = next((loc for loc in st.session_state.locations if loc["label"] == origin), None)
                dest_loc = next((loc for loc in st.session_state.locations if loc["label"] == destination), None)
                
                if origin_loc and dest_loc:
                    results = {}
                    
                    if travel_mode in ["도보", "모두"]:
                        results["walking"] = get_directions(
                            origin_loc["lat"], origin_loc["lon"],
                            dest_loc["lat"], dest_loc["lon"],
                            mode="walking"
                        )
                    
                    if travel_mode in ["자동차", "모두"]:
                        results["driving"] = get_directions(
                            origin_loc["lat"], origin_loc["lon"],
                            dest_loc["lat"], dest_loc["lon"],
                            mode="driving"
                        )
                    
                    st.session_state.route_results = results
                    st.rerun()  # experimental_rerun 대신 rerun 사용
            else:
                st.warning("출발지와 도착지를 모두 선택하고 서로 다른 지점이어야 합니다.")
    else:
        st.info("경로를 찾으려면 마커를 2개 이상 저장해주세요.")
    
    # --- 경로 결과 표시 ---
    if st.session_state.route_results:
        st.subheader("🔍 경로 검색 결과")
        
        if "walking" in st.session_state.route_results:
            walking = st.session_state.route_results["walking"]
            if "error_message" in walking:
                st.warning(f"🚶 도보: {walking['error_message']}")
            else:
                st.success(f"🚶 도보: {walking['distance']} ({walking['duration']})")
        
        if "driving" in st.session_state.route_results:
            driving = st.session_state.route_results["driving"]
            if "error_message" in driving:
                st.warning(f"🚗 자동차: {driving['error_message']}")
            else:
                st.success(f"🚗 자동차: {driving['distance']} ({driving['duration']})")
