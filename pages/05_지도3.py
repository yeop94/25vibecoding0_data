import streamlit as st
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials # google-auth의 일부

# --- Streamlit 페이지 설정 (가장 먼저 실행) ---
st.set_page_config(
    layout="wide",
    page_title="Folium 지도 & 경로 안내",
    page_icon="🗺️"
)

# --- Google Sheets 관련 설정 ---
GOOGLE_SHEET_NAME_OR_URL = "내 마커 데이터" # 실제 시트 이름/URL로 변경 필요
WORKSHEET_NAME = "Sheet1"

# --- Google Sheets Helper Functions (이전과 동일) ---
def init_gspread_client():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        return gc
    except KeyError:
        st.error("Streamlit Secrets에 'gcp_service_account' 정보가 없습니다. .streamlit/secrets.toml 또는 Cloud Secrets 설정을 확인하세요.")
        return None
    except Exception as e:
        st.error(f"Google Sheets 인증에 실패했습니다: {e}")
        return None

def get_worksheet(gc, sheet_key, worksheet_name_or_index=0):
    if gc is None: return None
    try:
        if "docs.google.com/spreadsheets" in sheet_key: spreadsheet = gc.open_by_url(sheet_key)
        else: spreadsheet = gc.open(sheet_key)
        if isinstance(worksheet_name_or_index, str): worksheet = spreadsheet.worksheet(worksheet_name_or_index)
        else: worksheet = spreadsheet.get_worksheet(worksheet_name_or_index)
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound: st.error(f"스프레드시트 '{sheet_key}'를 찾을 수 없습니다."); return None
    except gspread.exceptions.WorksheetNotFound: st.error(f"워크시트 '{worksheet_name_or_index}'를 찾을 수 없습니다."); return None
    except Exception as e: st.error(f"워크시트 '{sheet_key}' 로딩 중 오류: {e}"); return None

def load_locations_from_sheet(worksheet):
    if worksheet is None: return []
    try:
        records = worksheet.get_all_records()
        locations = []
        for i, record in enumerate(records):
            try:
                lat, lon = record.get("Latitude"), record.get("Longitude")
                if lat is None or lon is None: continue
                locations.append({"label": str(record.get("Label", f"무명 마커 {i+1}")), "lat": float(lat), "lon": float(lon)})
            except ValueError: continue
        #if records: st.success("Google Sheet에서 데이터를 성공적으로 불러왔습니다.") # 중복 메시지 최소화
        #else: st.info("Google Sheet에 데이터가 없거나 헤더만 있습니다.")
        return locations
    except Exception as e: st.error(f"Google Sheet 데이터 로딩 중 오류: {e}"); return []

def add_location_to_sheet(worksheet, location_data):
    if worksheet is None: st.error("워크시트 연결 실패로 추가 불가."); return False
    try:
        worksheet.append_row([location_data["label"], location_data["lat"], location_data["lon"]])
        return True
    except Exception as e: st.error(f"Google Sheet 데이터 추가 중 오류: {e}"); return False

def delete_location_from_sheet(worksheet, location_to_delete):
    if worksheet is None: st.error("워크시트 연결 실패로 삭제 불가."); return False
    try:
        all_records_values = worksheet.get_all_values()
        header = all_records_values[0]
        try:
            label_idx, lat_idx, lon_idx = header.index("Label"), header.index("Latitude"), header.index("Longitude")
        except ValueError: st.error("시트 헤더(Label, Latitude, Longitude) 오류로 삭제 불가."); return False
        
        row_to_delete = -1
        for i in range(1, len(all_records_values)):
            row = all_records_values[i]
            try:
                if str(row[label_idx]) == location_to_delete["label"] and \
                   abs(float(row[lat_idx]) - location_to_delete["lat"]) < 0.00001 and \
                   abs(float(row[lon_idx]) - location_to_delete["lon"]) < 0.00001:
                    row_to_delete = i + 1; break
            except (ValueError, IndexError): continue
        if row_to_delete != -1: worksheet.delete_rows(row_to_delete); return True
        else: st.warning(f"Sheet에서 '{location_to_delete['label']}' 삭제 항목 못 찾음."); return False
    except Exception as e: st.error(f"Google Sheet 데이터 삭제 중 오류: {e}"); return False

# --- Streamlit App Title ---
st.title("🗺️ 마커 저장 및 경로 안내 (Google Sheets 연동)")

# --- 세션 상태 초기화 ---
default_map_center = [37.5665, 126.9780]
default_zoom_start = 6

if "locations" not in st.session_state: st.session_state.locations = []
if "map_center" not in st.session_state: st.session_state.map_center = list(default_map_center)
if "zoom_start" not in st.session_state: st.session_state.zoom_start = default_zoom_start
if "last_clicked_coord" not in st.session_state: st.session_state.last_clicked_coord = None
if "gs_client" not in st.session_state: st.session_state.gs_client = init_gspread_client()
if "worksheet" not in st.session_state: st.session_state.worksheet = None
if "data_loaded_from_sheet" not in st.session_state: st.session_state.data_loaded_from_sheet = False

# 경로 기능 관련 세션 상태
if "route_origin_label" not in st.session_state: st.session_state.route_origin_label = None
if "route_destination_label" not in st.session_state: st.session_state.route_destination_label = None
if "route_results" not in st.session_state: st.session_state.route_results = None
if "calculating_route" not in st.session_state: st.session_state.calculating_route = False


# --- Google Sheets 연결 및 초기 데이터 로드 ---
if st.session_state.gs_client and st.session_state.worksheet is None:
    st.session_state.worksheet = get_worksheet(st.session_state.gs_client, GOOGLE_SHEET_NAME_OR_URL, WORKSHEET_NAME)

if st.session_state.worksheet and not st.session_state.data_loaded_from_sheet:
    with st.spinner("Google Sheets에서 데이터를 불러오는 중..."):
        st.session_state.locations = load_locations_from_sheet(st.session_state.worksheet)
        st.session_state.data_loaded_from_sheet = True
        if st.session_state.locations:
            last_loc = st.session_state.locations[-1]
            st.session_state.map_center = [last_loc['lat'], last_loc['lon']]
            st.session_state.zoom_start = 10
        else:
            st.session_state.map_center = list(default_map_center)
            st.session_state.zoom_start = default_zoom_start

# --- 레이아웃 설정 ---
col1, col2 = st.columns([3, 1.2]) # 사이드바 너비 조정

with col1: # 지도 표시 영역
    st.subheader("🌍 지도")
    
    # map_center 유효성 검사
    current_map_center = st.session_state.get("map_center", list(default_map_center))
    current_zoom_start = st.session_state.get("zoom_start", default_zoom_start)
    if not (isinstance(current_map_center, (list, tuple)) and len(current_map_center) == 2 and all(isinstance(c, (int, float)) for c in current_map_center)):
        current_map_center = list(default_map_center)
        st.session_state.map_center = list(default_map_center) # 세션 상태도 복원

    m = folium.Map(location=current_map_center, zoom_start=current_zoom_start)

    # 마커 표시 (출발지/도착지 강조)
    for loc_data in st.session_state.locations:
        icon_color, icon_symbol, popup_text = 'blue', 'info-sign', loc_data["label"]
        if st.session_state.route_origin_label == loc_data["label"]:
            icon_color, icon_symbol, popup_text = 'green', 'play', f"출발: {loc_data['label']}"
        elif st.session_state.route_destination_label == loc_data["label"]:
            icon_color, icon_symbol, popup_text = 'red', 'stop', f"도착: {loc_data['label']}"
        
        folium.Marker(
            [loc_data["lat"], loc_data["lon"]], 
            tooltip=loc_data["label"],
            popup=folium.Popup(popup_text, max_width=200),
            icon=folium.Icon(color=icon_color, icon=icon_symbol)
        ).add_to(m)

    if st.session_state.last_clicked_coord: # 임시 클릭 마커
        folium.Marker(
            [st.session_state.last_clicked_coord["lat"], st.session_state.last_clicked_coord["lng"]],
            tooltip="선택된 위치 (저장 전)", icon=folium.Icon(color='green', icon='plus')
        ).add_to(m)

    map_interaction_data = st_folium(m, width="100%", height=600, key="map_with_routes")

    # 지도 상호작용 결과 처리
    if map_interaction_data:
        new_center = map_interaction_data.get("center")
        if new_center and isinstance(new_center, (list, tuple)) and len(new_center) == 2:
            st.session_state.map_center = list(new_center)
        elif new_center and isinstance(new_center, dict) and "lat" in new_center and "lng" in new_center:
             st.session_state.map_center = [new_center["lat"], new_center["lng"]]


        if map_interaction_data.get("zoom") is not None: st.session_state.zoom_start = map_interaction_data["zoom"]
        
        clicked = map_interaction_data.get("last_clicked")
        if clicked and st.session_state.last_clicked_coord != clicked:
            st.session_state.last_clicked_coord = clicked
            st.rerun()

with col2: # 정보 입력 및 경로 찾기 영역
    st.subheader("📍 마커 추가")
    if not st.session_state.worksheet:
        st.error("Google Sheets에 연결되지 않았습니다. 설정을 확인하세요.")
    
    if st.session_state.last_clicked_coord:
        lat, lon = st.session_state.last_clicked_coord["lat"], st.session_state.last_clicked_coord["lng"]
        st.info(f"선택 위치: {lat:.5f}, {lon:.5f}")
        with st.form("label_form_route_page", clear_on_submit=True):
            label = st.text_input("장소 이름", value=f"마커 {len(st.session_state.locations) + 1}")
            if st.form_submit_button("✅ 마커 저장"):
                if st.session_state.worksheet:
                    new_loc = {"label": label, "lat": lat, "lon": lon}
                    if add_location_to_sheet(st.session_state.worksheet, new_loc):
                        st.session_state.locations.append(new_loc)
                        st.toast(f"'{label}' 저장 완료!", icon="📄")
                        st.session_state.map_center, st.session_state.zoom_start = [lat, lon], 12
                        st.session_state.last_clicked_coord = None
                        st.rerun()
    else:
        st.info("마커를 추가하려면 지도를 클릭하세요.")

    st.markdown("---")
    st.subheader("📋 저장된 위치 목록")
    if st.session_state.locations:
        for i, loc in enumerate(st.session_state.locations):
            c1, c2 = st.columns([0.8, 0.2])
            c1.markdown(f"**{loc['label']}** ({loc['lat']:.4f}, {loc['lon']:.4f})")
            if c2.button("삭제", key=f"del_{i}_{loc['label']}"):
                if st.session_state.worksheet and delete_location_from_sheet(st.session_state.worksheet, loc):
                    deleted_loc_label = st.session_state.locations.pop(i)["label"]
                    st.toast(f"'{deleted_loc_label}' 삭제 완료!", icon="🚮")
                    if st.session_state.locations:
                        st.session_state.map_center = [st.session_state.locations[-1]['lat'], st.session_state.locations[-1]['lon']]
                    else:
                        st.session_state.map_center = list(default_map_center)
                    st.rerun()
                    break 
    else: st.info("저장된 위치가 없습니다.")
    
    # --- 경로 찾기 기능 ---
    st.markdown("---")
    st.subheader("🚗🚶 경로 찾기")

    if not st.session_state.locations or len(st.session_state.locations) < 1: # 경로 찾기는 1개만 있어도 출발지/도착지로 쓸 수 있음 (API가 주소/장소명도 받으므로)
        st.info("경로를 찾으려면 지도에 마커를 저장하거나, 경로 검색 API가 장소 이름을 직접 이해할 수 있어야 합니다.")
    
    # 저장된 마커가 있을 경우에만 선택 옵션 제공
    marker_labels = [""] + [loc["label"] for loc in st.session_state.locations] # 빈 옵션 추가

    # 이전에 선택한 값이 유효한지 확인하고 인덱스 설정
    try:
        origin_idx = marker_labels.index(st.session_state.route_origin_label) if st.session_state.route_origin_label in marker_labels else 0
    except ValueError: # 이전 선택값이 더 이상 목록에 없을 경우
        origin_idx = 0
        st.session_state.route_origin_label = marker_labels[0] if marker_labels else None

    try:
        dest_idx = marker_labels.index(st.session_state.route_destination_label) if st.session_state.route_destination_label in marker_labels else (1 if len(marker_labels) > 1 else 0)
    except ValueError:
        dest_idx = (1 if len(marker_labels) > 1 else 0)
        st.session_state.route_destination_label = marker_labels[dest_idx] if len(marker_labels) > dest_idx else None


    # 사용자 입력 필드 추가 (선택 사항)
    origin_input = st.text_input("출발지 (직접 입력 또는 선택)", value=st.session_state.route_origin_label or "")
    destination_input = st.text_input("도착지 (직접 입력 또는 선택)", value=st.session_state.route_destination_label or "")
    
    col_route_btn1, col_route_btn2 = st.columns(2)
    with col_route_btn1:
        if st.button("📍 경로 계산", use_container_width=True):
            if not origin_input or not destination_input:
                st.warning("출발지와 도착지를 모두 입력하거나 선택해주세요.")
            elif origin_input == destination_input:
                st.warning("출발지와 도착지가 동일합니다.")
            else:
                # 선택된 마커의 레이블을 사용하거나, 직접 입력된 텍스트 사용
                st.session_state.route_origin_label = origin_input
                st.session_state.route_destination_label = destination_input
                st.session_state.calculating_route = True
                st.session_state.route_results = None # 이전 결과 초기화
                st.rerun()
    with col_route_btn2:
        if st.button("🗑️ 경로 해제", key="clear_route", use_container_width=True):
            st.session_state.route_origin_label = None
            st.session_state.route_destination_label = None
            st.session_state.route_results = None
            st.rerun()

    # API 호출 및 결과 처리 로직 (st.session_state.calculating_route 플래그 사용)
    # 이 부분은 다음 단계에서 API 호출 코드가 생성된 후 채워집니다.
    # 지금은 이 플래그가 True일 때 API 호출을 준비하는 것으로 가정합니다.

    if st.session_state.calculating_route:
        with st.spinner("경로를 계산 중입니다..."):
            # API 호출 코드가 여기에 위치 (다음 응답에서 생성)
            # st.session_state.route_results = ... (API 결과로 채움)
            # st.session_state.calculating_route = False
            # st.rerun() # API 호출 후 결과를 표시하기 위해 rerun
            # 현재는 API 호출 부분이 없으므로, 이 블록은 다음 단계에서 채워집니다.
            # 이 예제에서는 아직 실제 API 호출 코드가 없으므로, 이 블록은 실제 동작을 하지 않습니다.
            # 사용자가 버튼을 누르면 calculating_route가 True가 되고, 다음 rerun에서 이 블록이 실행됩니다.
            # API 호출 후, 그 결과를 route_results에 저장하고 calculating_route를 False로 바꿔야 합니다.
            pass


    # 경로 결과 표시
    if st.session_state.route_results:
        st.markdown("---")
        st.subheader("🔍 경로 검색 결과")
        
        walking_info = st.session_state.route_results.get("walking")
        driving_info = st.session_state.route_results.get("driving")

        if isinstance(walking_info, str): # 오류 메시지인 경우
            st.error(f"🚶 도보 경로: {walking_info}")
        elif walking_info:
            st.markdown(f"🚶 **도보 경로:**")
            st.markdown(f"  - 예상 시간: {walking_info.get('duration', '정보 없음')}")
            st.markdown(f"  - 거리: {walking_info.get('distance', '정보 없음')}")
            if walking_info.get('url'): st.markdown(f"  - [Google Maps에서 경로 보기]({walking_info.get('url')})")

        if isinstance(driving_info, str): # 오류 메시지인 경우
            st.error(f"🚗 자동차 경로: {driving_info}")
        elif driving_info:
            st.markdown(f"🚗 **자동차 경로:**")
            st.markdown(f"  - 예상 시간: {driving_info.get('duration', '정보 없음')}")
            st.markdown(f"  - 거리: {driving_info.get('distance', '정보 없음')}")
            if driving_info.get('url'): st.markdown(f"  - [Google Maps에서 경로 보기]({driving_info.get('url')})")
        
        # 통합 지도 URL이 있다면 표시 (하나의 API 호출에서 대표 URL을 받을 경우)
        # combined_map_url = st.session_state.route_results.get("map_url_combined")
        # if combined_map_url:
        # st.markdown(f"🗺️ [통합 경로 지도 보기 (Google Maps)]({combined_map_url})")
