import streamlit as st
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
import requests
import polyline
import urllib.parse
import os
from datetime import datetime

# --- Streamlit 페이지 설정 (가장 먼저 실행) ---
st.set_page_config(
    layout="wide",
    page_title="Folium 지도 & 경로 안내",
    page_icon="🗺️"
)

# --- Google API 설정 ---
GOOGLE_MAPS_API_KEY = st.secrets.get("google_maps_api_key", "")

# --- Google Sheets 관련 설정 ---
GOOGLE_SHEET_NAME_OR_URL = "내 마커 데이터"  # 실제 시트 이름/URL로 변경 필요
WORKSHEET_NAME = "Sheet1"

# --- Google Sheets Helper Functions ---
def init_gspread_client():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        return gc
    except KeyError:
        st.error("Streamlit Secrets에 'gcp_service_account' 정보가 없습니다. 설정을 확인하세요.")
        return None
    except Exception as e:
        st.error(f"Google Sheets 인증 실패: {e}")
        return None

def get_worksheet(gc, sheet_key, worksheet_name_or_index=0):
    if gc is None: 
        return None
    
    try:
        if "docs.google.com/spreadsheets" in sheet_key:
            spreadsheet = gc.open_by_url(sheet_key)
        else:
            spreadsheet = gc.open(sheet_key)
        
        if isinstance(worksheet_name_or_index, str):
            worksheet = spreadsheet.worksheet(worksheet_name_or_index)
        else:
            worksheet = spreadsheet.get_worksheet(worksheet_name_or_index)
        
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"스프레드시트 '{sheet_key}'를 찾을 수 없습니다.")
        return None
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"워크시트 '{worksheet_name_or_index}'를 찾을 수 없습니다.")
        return None
    except Exception as e:
        st.error(f"워크시트 '{sheet_key}' 로딩 중 오류: {e}")
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
                    "label": str(record.get("Label", f"무명 마커 {i+1}")),
                    "lat": float(lat),
                    "lon": float(lon)
                })
            except ValueError:
                continue
                
        return locations
    except Exception as e:
        st.error(f"Google Sheet 데이터 로딩 중 오류: {e}")
        return []

def add_location_to_sheet(worksheet, location_data):
    if worksheet is None:
        st.error("워크시트 연결 실패로 추가 불가.")
        return False
    
    try:
        worksheet.append_row([location_data["label"], location_data["lat"], location_data["lon"]])
        return True
    except Exception as e:
        st.error(f"Google Sheet 데이터 추가 중 오류: {e}")
        return False

def delete_location_from_sheet(worksheet, location_to_delete):
    if worksheet is None:
        st.error("워크시트 연결 실패로 삭제 불가.")
        return False
    
    try:
        all_records_values = worksheet.get_all_values()
        header = all_records_values[0]
        
        try:
            label_idx = header.index("Label")
            lat_idx = header.index("Latitude")
            lon_idx = header.index("Longitude")
        except ValueError:
            st.error("시트 헤더(Label, Latitude, Longitude) 오류로 삭제 불가.")
            return False
        
        row_to_delete = -1
        for i in range(1, len(all_records_values)):
            row = all_records_values[i]
            try:
                if (str(row[label_idx]) == location_to_delete["label"] and
                    abs(float(row[lat_idx]) - location_to_delete["lat"]) < 0.00001 and
                    abs(float(row[lon_idx]) - location_to_delete["lon"]) < 0.00001):
                    row_to_delete = i + 1
                    break
            except (ValueError, IndexError):
                continue
                
        if row_to_delete != -1:
            worksheet.delete_rows(row_to_delete)
            return True
        else:
            st.warning(f"Sheet에서 '{location_to_delete['label']}' 삭제 항목을 찾지 못했습니다.")
            return False
    except Exception as e:
        st.error(f"Google Sheet 데이터 삭제 중 오류: {e}")
        return False

# --- Google Maps Directions API 함수 ---
def get_directions(origin_lat, origin_lng, dest_lat, dest_lng, mode="driving"):
    """Google Maps Directions API를 통해 경로 정보를 가져옵니다."""
    if not GOOGLE_MAPS_API_KEY:
        return {"error_message": "Google Maps API 키가 설정되지 않았습니다."}
    
    base_url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{origin_lat},{origin_lng}",
        "destination": f"{dest_lat},{dest_lng}",
        "mode": mode,
        "key": GOOGLE_MAPS_API_KEY,
        "language": "ko",  # 한국어 결과
        "region": "kr"     # 한국 지역 기준
    }
    
    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data["status"] == "OK" and data["routes"]:
            route = data["routes"][0]
            leg = route["legs"][0]
            
            # 폴리라인 경로 데이터 추출
            route_polyline = route["overview_polyline"]["points"]
            decoded_polyline = polyline.decode(route_polyline)
            
            # 구글 맵스 웹 URL 생성
            map_url = f"https://www.google.com/maps/dir/?api=1&origin={origin_lat},{origin_lng}&destination={dest_lat},{dest_lng}&travelmode={mode}"
            
            return {
                "duration": leg["duration"]["text"],
                "distance": leg["distance"]["text"],
                "start_address": leg["start_address"],
                "end_address": leg["end_address"],
                "steps": leg["steps"],
                "polyline": decoded_polyline,
                "url": map_url
            }
        else:
            error_msg = data.get("status", "알 수 없는 오류")
            if data.get("error_message"):
                error_msg = data["error_message"]
            return {"error_message": f"{error_msg}"}
    except Exception as e:
        return {"error_message": f"API 호출 오류: {str(e)}"}

def get_place_details(place_id):
    """Google Maps Place Details API를 통해 장소 상세 정보를 가져옵니다."""
    if not GOOGLE_MAPS_API_KEY:
        return {"error_message": "Google Maps API 키가 설정되지 않았습니다."}
    
    base_url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "key": GOOGLE_MAPS_API_KEY,
        "language": "ko",
        "fields": "name,formatted_address,geometry,rating,formatted_phone_number,opening_hours,website,photos"
    }
    
    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data["status"] == "OK" and "result" in data:
            return data["result"]
        else:
            error_msg = data.get("status", "알 수 없는 오류")
            if data.get("error_message"):
                error_msg = data["error_message"]
            return {"error_message": f"{error_msg}"}
    except Exception as e:
        return {"error_message": f"API 호출 오류: {str(e)}"}

def get_place_photo_url(photo_reference, max_width=400):
    """Google Maps Place Photo API를 통해 장소 사진 URL을 생성합니다."""
    if not GOOGLE_MAPS_API_KEY or not photo_reference:
        return None
    
    return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={max_width}&photoreference={photo_reference}&key={GOOGLE_MAPS_API_KEY}"

def geocode_address(address):
    """Google Maps Geocoding API를 통해 주소를 좌표로 변환합니다."""
    if not GOOGLE_MAPS_API_KEY:
        return {"error_message": "Google Maps API 키가 설정되지 않았습니다."}
    
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": GOOGLE_MAPS_API_KEY,
        "language": "ko",
        "region": "kr"
    }
    
    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data["status"] == "OK" and data["results"]:
            result = data["results"][0]
            location = result["geometry"]["location"]
            
            return {
                "lat": location["lat"],
                "lng": location["lng"],
                "formatted_address": result["formatted_address"],
                "place_id": result.get("place_id")
            }
        else:
            error_msg = data.get("status", "알 수 없는 오류")
            if data.get("error_message"):
                error_msg = data["error_message"]
            return {"error_message": f"{error_msg}"}
    except Exception as e:
        return {"error_message": f"API 호출 오류: {str(e)}"}

# --- Streamlit App Title ---
st.title("🗺️ 마커 저장 및 경로 안내 (Google Maps API 연동)")

# --- 세션 상태 초기화 ---
default_map_center = [37.5665, 126.9780]  # 서울 중심 좌표
default_zoom_start = 12

# 초기화 함수 - 앱 시작 시 한 번만 실행
def initialize_session_state():
    if "locations" not in st.session_state:
        st.session_state.locations = []
    if "map_center" not in st.session_state:
        st.session_state.map_center = list(default_map_center)
    if "zoom_start" not in st.session_state:
        st.session_state.zoom_start = default_zoom_start
    if "last_clicked_coord" not in st.session_state:
        st.session_state.last_clicked_coord = None
    if "gs_client" not in st.session_state:
        st.session_state.gs_client = init_gspread_client()
    if "worksheet" not in st.session_state:
        st.session_state.worksheet = None
    if "data_loaded_from_sheet" not in st.session_state:
        st.session_state.data_loaded_from_sheet = False
    if "route_origin_label" not in st.session_state:
        st.session_state.route_origin_label = None
    if "route_destination_label" not in st.session_state:
        st.session_state.route_destination_label = None
    if "route_results" not in st.session_state:
        st.session_state.route_results = None
    if "calculating_route" not in st.session_state:
        st.session_state.calculating_route = False
    if "search_address" not in st.session_state:
        st.session_state.search_address = ""
    if "search_results" not in st.session_state:
        st.session_state.search_results = None
    if "show_traffic" not in st.session_state:
        st.session_state.show_traffic = False
    if "selected_place_details" not in st.session_state:
        st.session_state.selected_place_details = None
    if "map_type" not in st.session_state:
        st.session_state.map_type = "OpenStreetMap"
    if "last_operation" not in st.session_state:
        st.session_state.last_operation = None
    if "operation_time" not in st.session_state:
        st.session_state.operation_time = datetime.now()

# 세션 상태 초기화
initialize_session_state()

# --- Google Sheets 연결 및 초기 데이터 로드 ---
if st.session_state.gs_client and st.session_state.worksheet is None:
    st.session_state.worksheet = get_worksheet(st.session_state.gs_client, GOOGLE_SHEET_NAME_OR_URL, WORKSHEET_NAME)

if st.session_state.worksheet and not st.session_state.data_loaded_from_sheet:
    with st.spinner("Google Sheets에서 데이터를 불러오는 중..."):
        st.session_state.locations = load_locations_from_sheet(st.session_state.worksheet)
        st.session_state.data_loaded_from_sheet = True
        
        if st.session_state.locations:
            st.success("Google Sheet에서 데이터를 성공적으로 불러왔습니다.")
            last_loc = st.session_state.locations[-1]
            st.session_state.map_center = [last_loc['lat'], last_loc['lon']]
            st.session_state.zoom_start = 13
        else:
            st.info("Google Sheet에 저장된 데이터가 없습니다.")
            st.session_state.map_center = list(default_map_center)
            st.session_state.zoom_start = default_zoom_start

# --- 탭 기반 인터페이스 ---
tab1, tab2, tab3 = st.tabs(["🗺️ 지도 및 마커", "🚗 경로 찾기", "ℹ️ API 설정 도움말"])

with tab1:
    # --- 레이아웃 설정 ---
    col1, col2 = st.columns([3, 1.2]) 
    
    with col1: 
        st.subheader("🌍 지도")
        
        # 지도 타입 선택
        map_types = ["OpenStreetMap", "Stamen Terrain", "Stamen Toner", "CartoDB positron"]
        selected_map_type = st.selectbox("지도 타입 선택:", map_types, index=map_types.index(st.session_state.map_type))
        st.session_state.map_type = selected_map_type
        
        # 트래픽 정보 표시 설정 (Google Maps API 키가 있을 때만)
        if GOOGLE_MAPS_API_KEY:
            st.session_state.show_traffic = st.checkbox("교통 정보 표시", value=st.session_state.show_traffic)
        
        # 주소 검색 기능
        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            search_input = st.text_input("주소 검색:", value=st.session_state.search_address)
        with search_col2:
            search_button = st.button("🔍 검색", use_container_width=True)
        
        if search_button and search_input:
            st.session_state.search_address = search_input
            search_result = geocode_address(search_input)
            
            if "error_message" not in search_result:
                st.session_state.search_results = search_result
                st.session_state.map_center = [search_result["lat"], search_result["lng"]]
                st.session_state.zoom_start = 15
                st.session_state.last_clicked_coord = {"lat": search_result["lat"], "lng": search_result["lng"]}
                st.success(f"검색 결과: {search_result['formatted_address']}")
            else:
                st.error(f"검색 오류: {search_result['error_message']}")
                st.session_state.search_results = None
        
        # 지도 생성
        current_map_center = st.session_state.map_center
        current_zoom_start = st.session_state.zoom_start
        
        if not (isinstance(current_map_center, (list, tuple)) and len(current_map_center) == 2 and 
                all(isinstance(c, (int, float)) for c in current_map_center)):
            current_map_center = list(default_map_center)
            st.session_state.map_center = list(default_map_center)
        
        m = folium.Map(location=current_map_center, zoom_start=current_zoom_start, tiles=st.session_state.map_type)
        
        # 트래픽 정보 레이어 추가 (Google Maps API 키가 있고, 옵션이 켜져있을 때)
        if GOOGLE_MAPS_API_KEY and st.session_state.show_traffic:
            traffic_url = f"https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_API_KEY}&libraries=visualization"
            folium.TileLayer(
                tiles=f"https://mt0.google.com/vt/lyrs=m@221097413,traffic&hl=ko&x={{x}}&y={{y}}&z={{z}}&style=3&apiKey={GOOGLE_MAPS_API_KEY}",
                attr="Google Maps Traffic",
                name="Traffic",
                overlay=True,
                control=True
            ).add_to(m)
        
        # 경로 폴리라인 추가
        if st.session_state.route_results:
            # 도보 경로
            walking_info = st.session_state.route_results.get("walking", {})
            if walking_info and "polyline" in walking_info and walking_info["polyline"]:
                folium.PolyLine(
                    locations=walking_info["polyline"],
                    weight=4,
                    color='blue',
                    opacity=0.7,
                    tooltip="도보 경로"
                ).add_to(m)
            
            # 자동차 경로
            driving_info = st.session_state.route_results.get("driving", {})
            if driving_info and "polyline" in driving_info and driving_info["polyline"]:
                folium.PolyLine(
                    locations=driving_info["polyline"],
                    weight=5,
                    color='red',
                    opacity=0.7,
                    tooltip="자동차 경로"
                ).add_to(m)
        
        # 마커 추가
        for loc_data in st.session_state.locations:
            icon_color, icon_symbol, popup_text = 'blue', 'info-sign', loc_data["label"]
            
            if st.session_state.route_origin_label == loc_data["label"]:
                icon_color, icon_symbol, popup_text = 'green', 'play', f"출발: {loc_data['label']}"
            elif st.session_state.route_destination_label == loc_data["label"]:
                icon_color, icon_symbol, popup_text = 'red', 'flag', f"도착: {loc_data['label']}"
            
            folium.Marker(
                [loc_data["lat"], loc_data["lon"]], 
                tooltip=loc_data["label"], 
                popup=folium.Popup(popup_text, max_width=200),
                icon=folium.Icon(color=icon_color, icon=icon_symbol)
            ).add_to(m)
        
        # 마지막으로 클릭한 위치 마커 추가
        if st.session_state.last_clicked_coord:
            folium.Marker(
                [st.session_state.last_clicked_coord["lat"], st.session_state.last_clicked_coord["lng"]],
                tooltip="선택된 위치 (저장 전)", 
                icon=folium.Icon(color='purple', icon='plus')
            ).add_to(m)
        
        # 검색 결과 위치 마커 추가
        if st.session_state.search_results and "error_message" not in st.session_state.search_results:
            folium.Marker(
                [st.session_state.search_results["lat"], st.session_state.search_results["lng"]],
                tooltip=f"검색 결과: {st.session_state.search_results['formatted_address']}",
                popup=folium.Popup(st.session_state.search_results['formatted_address'], max_width=300),
                icon=folium.Icon(color='orange', icon='search')
            ).add_to(m)
        
        # 위치 컨트롤 추가
        folium.LatLngPopup().add_to(m)
        folium.LayerControl().add_to(m)
        
        # 지도 렌더링
        map_interaction_data = st_folium(m, width="100%", height=600, key="map_corrected_routes")
        
        # 지도 상호작용 처리
        if map_interaction_data:
            new_center = map_interaction_data.get("center")
            if new_center:
                if isinstance(new_center, dict) and "lat" in new_center and "lng" in new_center:
                    st.session_state.map_center = [new_center["lat"], new_center["lng"]]
                elif isinstance(new_center, (list, tuple)) and len(new_center) == 2:
                    st.session_state.map_center = list(new_center)
            
            if map_interaction_data.get("zoom") is not None:
                st.session_state.zoom_start = map_interaction_data["zoom"]
            
            clicked = map_interaction_data.get("last_clicked")
            if clicked and st.session_state.last_clicked_coord != clicked:
                st.session_state.last_clicked_coord = clicked
                st.session_state.last_operation = "map_click"
                st.session_state.operation_time = datetime.now()
                # 매 클릭마다 rerun하지 않고, 상태만 업데이트

    with col2: 
        st.subheader("📍 마커 추가")
        
        if not st.session_state.worksheet:
            st.error("Google Sheets에 연결되지 않았습니다. 설정을 확인하세요.")
        
        # 마커 추가 폼
        if st.session_state.last_clicked_coord:
            lat, lng = st.session_state.last_clicked_coord["lat"], st.session_state.last_clicked_coord["lng"]
            st.info(f"선택 위치: {lat:.5f}, {lng:.5f}")
            
            with st.form("label_form_corrected_routes", clear_on_submit=True):
                label = st.text_input("장소 이름", value=f"마커 {len(st.session_state.locations) + 1}")
                
                col1, col2 = st.columns(2)
                with col1:
                    submit_btn = st.form_submit_button("✅ 마커 저장", use_container_width=True)
                with col2:
                    cancel_btn = st.form_submit_button("❌ 취소", use_container_width=True)
                
                if submit_btn:
                    if st.session_state.worksheet:
                        new_loc = {"label": label, "lat": lat, "lon": lng}
                        if add_location_to_sheet(st.session_state.worksheet, new_loc):
                            st.session_state.locations.append(new_loc)
                            st.toast(f"'{label}' 저장 완료!", icon="📄")
                            st.session_state.map_center = [lat, lng]
                            st.session_state.zoom_start = 15
                            st.session_state.last_clicked_coord = None
                            st.session_state.last_operation = "marker_added"
                            st.session_state.operation_time = datetime.now()
                            st.rerun()
                
                if cancel_btn:
                    st.session_state.last_clicked_coord = None
                    st.rerun()
        else:
            st.info("마커를 추가하려면 지도를 클릭하세요.")
        
        # 현재 위치 자동 감지 버튼
        if st.button("📍 내 현재 위치로 이동", use_container_width=True):
            st.markdown("""
            <script>
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const lat = position.coords.latitude;
                        const lng = position.coords.longitude;
                        window.parent.postMessage({
                            type: "streamlit:setComponentValue",
                            value: {lat, lng},
                        }, "*");
                    },
                    (error) => {
                        console.error("위치 정보를 가져올 수 없습니다:", error);
                    }
                );
            } else {
                console.error("브라우저가 위치 서비스를 지원하지 않습니다.");
            }
            </script>
            """, unsafe_allow_html=True)
            st.info("브라우저에서 위치 정보 접근을 허용해주세요.")
        
        st.markdown("---")
        st.subheader("📋 저장된 위치 목록")
        
        # 검색 필터
        filter_query = st.text_input("마커 필터링:", placeholder="이름으로 필터링...")
        
        # 저장된 위치 목록 표시
        if st.session_state.locations:
            filtered_locations = st.session_state.locations
            if filter_query:
                filtered_locations = [loc for loc in st.session_state.locations 
                                     if filter_query.lower() in loc['label'].lower()]
            
            if not filtered_locations:
                st.info(f"'{filter_query}'에 해당하는 마커가 없습니다.")
            
            for i, loc in enumerate(filtered_locations):
                col1, col2, col3, col4 = st.columns([0.5, 0.15, 0.15, 0.2])
                
                with col1:
                    st.markdown(f"**{loc['label']}**")
                    st.caption(f"({loc['lat']:.4f}, {loc['lon']:.4f})")
                
                with col2:
                    if st.button("🔍", key=f"view_{i}_{loc['label']}"):
                        st.session_state.map_center = [loc['lat'], loc['lon']]
                        st.session_state.zoom_start = 16
                        st.session_state.last_operation = "view_marker"
                        st.session_state.operation_time = datetime.now()
                        st.rerun()
                
                with col3:
                    if st.button("🚩", key=f"route_{i}_{loc['label']}"):
                        st.session_state.route_destination_label = loc["label"]
                        st.session_state.last_operation = "set_destination"
                        st.session_state.operation_time = datetime.now()
                        st.rerun()
                
                with col4:
                    if st.button("🗑️", key=f"del_{i}_{loc['label']}"):
                        if st.session_state.worksheet and delete_location_from_sheet(st.session_state.worksheet, loc):
                            # 위치 정보 저장
                            deleted_label = loc["label"]
                            # 경로 시작/종료 지점 재설정
                            if st.session_state.route_origin_label == deleted_label:
                                st.session_state.route_origin_label = None
                            if st.session_state.route_destination_label == deleted_label:
                                st.session_state.route_destination_label = None
                            # 위치 목록에서 제거
                            st.session_state.locations.remove(loc)
                            st.toast(f"'{deleted_label}' 삭제 완료!", icon="🚮")
                            st.session_state.last_operation = "marker_deleted"
                            st.session_state.operation_time = datetime.now()
                            st.rerun()
                
                # 마커 간 구분선
                st.markdown("---")
        else:
            st.info("저장된 위치가 없습니다.")
            
        # 모든 마커 삭제 버튼
        if st.session_state.locations and st.button("🗑️ 모든 마커 삭제", use_container_width=True):
            if st.session_state.worksheet:
                confirm = st.checkbox("정말로 모든 마커를 삭제하시겠습니까?")
                if confirm:
                    try:
                        # 헤더 줄 유지하고 데이터만 삭제
                        st.session_state.worksheet.delete_rows(2, len(st.session_state.locations) + 1)
                        st.session_state.locations = []
                        st.session_state.route_origin_label = None
                        st.session_state.route_destination_label = None
                        st.session_state.route_results = None
                        st.success("모든 마커가 삭제되었습니다.")
                        st.session_state.last_operation = "all_markers_deleted"
                        st.session_state.operation_time = datetime.now()
                        st.rerun()
                    except Exception as e:
                        st.error(f"마커 삭제 중 오류 발생: {e}")

with tab2:
    st.subheader("🚗🚶 경로 찾기")
    
    # Google Maps API 키 확인
    if not GOOGLE_MAPS_API_KEY:
        st.warning("경로 찾기 기능을 사용하려면 Google Maps API 키가 필요합니다. 'API 설정 도움말' 탭을 참조하세요.")
    
    # 마커가 없는 경우
    if not st.session_state.locations:
        st.info("경로를 찾으려면 먼저 지도에 마커를 1개 이상 저장해주세요.")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 출발지와 도착지 선택")
            
            placeholder_option = "--- 선택 ---"
            marker_labels = [placeholder_option] + [loc["label"] for loc in st.session_state.locations]
            
            # 선택된 값 유지 또는 기본값(플레이스홀더)으로 설정
            origin_current_val = st.session_state.route_origin_label if st.session_state.route_origin_label in marker_labels else placeholder_option
            dest_current_val = st.session_state.route_destination_label if st.session_state.route_destination_label in marker_labels else placeholder_option
            
            # 만약 이전에 선택한 마커가 삭제되어 더 이상 목록에 없다면 플레이스홀더로 초기화
            if origin_current_val not in marker_labels:
                origin_current_val = placeholder_option
            if dest_current_val not in marker_labels:
                dest_current_val = placeholder_option
            
            selected_origin = st.selectbox("출발지 마커 선택:", options=marker_labels, 
                                          index=marker_labels.index(origin_current_val), 
                                          key="route_origin_sb")
            
            selected_destination = st.selectbox("도착지 마커 선택:", options=marker_labels, 
                                                index=marker_labels.index(dest_current_val), 
                                                key="route_dest_sb")
            
            # 세션 상태 업데이트 (선택 시 즉시 반영되도록)
            st.session_state.route_origin_label = selected_origin if selected_origin != placeholder_option else None
            st.session_state.route_destination_label = selected_destination if selected_destination != placeholder_option else None
            
            col_route_btn1, col_route_btn2 = st.columns(2)
            with col_route_btn1:
                if st.button("🔍 경로 계산", use_container_width=True, key="calc_route_btn_sb"):
                    if not st.session_state.route_origin_label or not st.session_state.route_destination_label:
                        st.warning("출발지와 도착지를 모두 선택해주세요.")
                    elif st.session_state.route_origin_label == st.session_state.route_destination_label:
                        st.warning("출발지와 도착지가 동일합니다. 다른 지점을 선택해주세요.")
                    else:
                        st.session_state.calculating_route = True
                        st.session_state.route_results = None 
                        st.session_state.last_operation = "route_calculation_start"
                        st.session_state.operation_time = datetime.now()
                        st.rerun()
            
            with col_route_btn2:
                if st.button("🗑️ 경로 해제", key="clear_route_sb", use_container_width=True):
                    st.session_state.route_origin_label = None
                    st.session_state.route_destination_label = None
                    st.session_state.route_results = None
                    st.session_state.last_operation = "route_cleared"
                    st.session_state.operation_time = datetime.now()
                    st.rerun()
        
        with col2:
            st.markdown("#### 경로 옵션")
            
            travel_mode = st.radio(
                "이동 수단 선택:",
                options=["자동차 + 도보", "자동차만", "도보만"],
                index=0,
                horizontal=True
            )
            
            alternatives = st.checkbox("대체 경로 검색", value=True)
            
            traffic_model = st.selectbox(
                "교통 예측 모델:",
                options=["최적 예측", "낙관적 예측", "비관적 예측"],
                index=0
            )
            
            avoid_options = st.multiselect(
                "회피 옵션:",
                options=["고속도로", "통행료", "페리"]
            )
            
            # 출발 시간 설정
            departure_time = st.radio(
                "출발 시간:",
                options=["현재", "직접 지정"],
                index=0,
                horizontal=True
            )
            
            if departure_time == "직접 지정":
                departure_date = st.date_input("출발 날짜", datetime.now())
                departure_time_input = st.time_input("출발 시간", datetime.now().time())
        
        # API 호출 결과 처리 로직
        if st.session_state.calculating_route:
            with st.spinner("경로를 계산하는 중입니다..."):
                # 출발지, 도착지 좌표 찾기
                origin_loc = next((loc for loc in st.session_state.locations if loc["label"] == st.session_state.route_origin_label), None)
                dest_loc = next((loc for loc in st.session_state.locations if loc["label"] == st.session_state.route_destination_label), None)
                
                if origin_loc and dest_loc:
                    results = {}
                    
                    # 이동 수단에 따라 API 호출
                    if travel_mode in ["자동차 + 도보", "도보만"]:
                        # 도보 경로 계산
                        walking_result = get_directions(
                            origin_loc["lat"], origin_loc["lon"],
                            dest_loc["lat"], dest_loc["lon"],
                            mode="walking"
                        )
                        results["walking"] = walking_result
                    
                    if travel_mode in ["자동차 + 도보", "자동차만"]:
                        # 자동차 경로 계산
                        driving_result = get_directions(
                            origin_loc["lat"], origin_loc["lon"],
                            dest_loc["lat"], dest_loc["lon"],
                            mode="driving"
                        )
                        results["driving"] = driving_result
                    
                    # 통합 지도 URL 생성
                    map_url_combined = f"https://www.google.com/maps/dir/?api=1&origin={origin_loc['lat']},{origin_loc['lon']}&destination={dest_loc['lat']},{dest_loc['lon']}"
                    results["map_url_combined"] = map_url_combined
                    
                    st.session_state.route_results = results
                
                st.session_state.calculating_route = False
                st.session_state.last_operation = "route_calculation_complete"
                st.session_state.operation_time = datetime.now()
                st.rerun()
        
        # 경로 결과 표시
        if st.session_state.route_results:
            st.markdown("---")
            st.subheader("🔍 경로 검색 결과")
            
            walking_info = st.session_state.route_results.get("walking")
            driving_info = st.session_state.route_results.get("driving")
            
            # 결과 컬럼 레이아웃
            if walking_info and driving_info:
                col_walking, col_driving = st.columns(2)
            else:
                col_walking = col_driving = st
            
            # 도보 경로 정보 표시
            if walking_info:
                with col_walking:
                    if "error_message" in walking_info:
                        st.warning(f"🚶 도보 경로: {walking_info['error_message']}")
                    elif walking_info.get("duration"):
                        st.markdown(f"### 🚶 도보 경로")
                        st.markdown(f"**예상 시간:** {walking_info.get('duration', '정보 없음')}")
                        st.markdown(f"**거리:** {walking_info.get('distance', '정보 없음')}")
                        
                        if "steps" in walking_info:
                            with st.expander("도보 경로 상세 안내"):
                                for i, step in enumerate(walking_info["steps"]):
                                    st.markdown(f"{i+1}. {step.get('html_instructions', '').replace('<b>', '**').replace('</b>', '**')}")
                                    st.caption(f"{step.get('distance', {}).get('text', '')} ({step.get('duration', {}).get('text', '')})")
                        
                        if walking_info.get('url'):
                            st.markdown(f"[Google Maps에서 도보 경로 보기]({walking_info.get('url')})")
                    else:
                        st.warning("🚶 도보 경로 정보를 가져올 수 없습니다.")
            
            # 자동차 경로 정보 표시
            if driving_info:
                with col_driving:
                    if "error_message" in driving_info:
                        st.warning(f"🚗 자동차 경로: {driving_info['error_message']}")
                    elif driving_info.get("duration"):
                        st.markdown(f"### 🚗 자동차 경로")
                        st.markdown(f"**예상 시간:** {driving_info.get('duration', '정보 없음')}")
                        st.markdown(f"**거리:** {driving_info.get('distance', '정보 없음')}")
                        
                        if "steps" in driving_info:
                            with st.expander("자동차 경로 상세 안내"):
                                for i, step in enumerate(driving_info["steps"]):
                                    st.markdown(f"{i+1}. {step.get('html_instructions', '').replace('<b>', '**').replace('</b>', '**')}")
                                    st.caption(f"{step.get('distance', {}).get('text', '')} ({step.get('duration', {}).get('text', '')})")
                        
                        if driving_info.get('url'):
                            st.markdown(f"[Google Maps에서 자동차 경로 보기]({driving_info.get('url')})")
                    else:
                        st.warning("🚗 자동차 경로 정보를 가져올 수 없습니다.")
            
            # 통합 경로 지도 URL
            combined_map_url = st.session_state.route_results.get("map_url_combined")
            if combined_map_url:
                st.markdown("---")
                st.markdown(f"🗺️ [통합 경로 지도 보기 (Google Maps)]({combined_map_url})")

with tab3:
    st.subheader("ℹ️ Google Maps API 설정 도움말")
    
    st.markdown("""
    ## 1. Google Maps API 키 발급 방법
    
    Google Maps API 키를 발급받아 이 앱에서 경로 안내 기능을 활용할 수 있습니다. 다음 단계를 따라 API 키를 발급받으세요:
    
    1. [Google Cloud Console](https://console.cloud.google.com/)에 로그인합니다.
    2. 새 프로젝트를 생성하거나 기존 프로젝트를 선택합니다.
    3. 왼쪽 메뉴에서 'API 및 서비스' > '라이브러리'로 이동합니다.
    4. 다음 API들을 검색하고 활성화합니다:
       - Maps JavaScript API
       - Directions API
       - Geocoding API
       - Places API
    5. '사용자 인증 정보'로 이동하여 'API 키 만들기'를 클릭합니다.
    6. 생성된 API 키를 복사합니다.
    7. 보안을 위해 API 키 제한을 설정합니다:
       - HTTP 리퍼러 제한 추가 (앱 배포 URL)
       - API 사용량 제한 설정
    
    ## 2. Streamlit 앱에 API 키 설정하기
    
    API 키를 앱에 설정하는 방법은 다음과 같습니다:
    
    ### 로컬 개발 환경인 경우:
    1. 프로젝트 폴더에 `.streamlit` 폴더를 생성합니다.
    2. 해당 폴더 내에 `secrets.toml` 파일을 생성합니다.
    3. 파일 내용을 다음과 같이 작성합니다:
    ```toml
    google_maps_api_key = "YOUR_API_KEY_HERE"
    
    [gcp_service_account]
    type = "service_account"
    project_id = "your-project-id"
    private_key_id = "your-private-key-id"
    private_key = "your-private-key"
    client_email = "your-service-account-email"
    client_id = "your-client-id"
    auth_uri = "https://accounts.google.com/o/oauth2/auth"
    token_uri = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
    client_x509_cert_url = "your-cert-url"
    ```
    
    ### Streamlit Cloud에 배포하는 경우:
    1. Streamlit Cloud 대시보드에서 앱 설정으로 이동합니다.
    2. '보안 설정'에서 '비밀 정보'를 클릭합니다.
    3. 위와 동일한 형식으로 API 키와 서비스 계정 정보를 추가합니다.
    
    ## 3. Google Sheets API 설정
    
    마커 데이터를 Google Sheets에 저장하려면 추가 설정이 필요합니다:
    
    1. [Google Cloud Console](https://console.cloud.google.com/)에서 'API 및 서비스' > '라이브러리'로 이동합니다.
    2. 'Google Sheets API'를 검색하고 활성화합니다.
    3. '사용자 인증 정보'에서 '서비스 계정'을 생성합니다.
    4. 생성된 서비스 계정의 JSON 키를 다운로드합니다.
    5. 다운로드한 JSON 키의 내용을 `secrets.toml` 파일의 `[gcp_service_account]` 섹션에 복사합니다.
    6. 데이터를 저장할 Google Sheet를 생성하고, 첫 번째 행에 다음 헤더를 추가합니다:
       - Label
       - Latitude
       - Longitude
    7. 생성한 서비스 계정 이메일(client_email)을 해당 시트에 편집자로 공유합니다.
    
    ## 4. API 사용량 및 비용 관리
    
    Google Maps API는 사용량에 따라 비용이 발생할 수 있습니다. 효율적인 관리를 위해:
    
    1. [Google Cloud Console](https://console.cloud.google.com/)에서 결제 알림을 설정합니다.
    2. API 키에 사용량 제한을 설정합니다.
    3. 정기적으로 사용량 보고서를 확인합니다.
    4. 무료 사용량 한도를 파악하고, 그 범위 내에서 사용하도록 계획합니다.
    
    ## 5. 문제 해결
    
    1. **API 키 오류**: API 키가 올바르게 설정되었는지 확인하고, 필요한 API가 모두 활성화되었는지 확인합니다.
    2. **할당량 초과**: 무료 사용량을 초과한 경우 결제를 활성화하거나 사용량을 제한합니다.
    3. **권한 문제**: Google Sheets 권한이 올바르게 설정되었는지 확인합니다.
    4. **제한 오류**: API 키에 설정한 제한이 너무 엄격한지 확인합니다.
    
    더 자세한 정보는 [Google Maps Platform 문서](https://developers.google.com/maps/documentation)를 참조하세요.
    """)

# 주요 상태 정보 디버그 모드
if st.sidebar.checkbox("디버그 모드", value=False):
    st.sidebar.subheader("세션 상태 정보")
    
    if st.sidebar.checkbox("기본 상태"):
        st.sidebar.json({
            "map_center": st.session_state.map_center,
            "zoom_start": st.session_state.zoom_start,
            "last_operation": st.session_state.last_operation,
            "operation_time": str(st.session_state.operation_time)
        })
    
    if st.sidebar.checkbox("마커 정보"):
        st.sidebar.write(f"마커 수: {len(st.session_state.locations)}")
        if st.session_state.last_clicked_coord:
            st.sidebar.write("마지막 클릭 좌표:", st.session_state.last_clicked_coord)
    
    if st.sidebar.checkbox("경로 정보"):
        st.sidebar.write(f"출발지: {st.session_state.route_origin_label}")
        st.sidebar.write(f"도착지: {st.session_state.route_destination_label}")
        if st.session_state.route_results:
            if "walking" in st.session_state.route_results:
                walk_info = st.session_state.route_results["walking"]
                if "error_message" in walk_info:
                    st.sidebar.write("도보 경로 오류:", walk_info["error_message"])
                else:
                    st.sidebar.write("도보 거리:", walk_info.get("distance"))
            
            if "driving" in st.session_state.route_results:
                drive_info = st.session_state.route_results["driving"]
                if "error_message" in drive_info:
                    st.sidebar.write("자동차 경로 오류:", drive_info["error_message"])
                else:
                    st.sidebar.write("자동차 거리:", drive_info.get("distance"))
