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

# --- Google Sheets Helper Functions (이전과 동일, 일부 메시지 수정) ---
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
        else: st.warning(f"Sheet에서 '{location_to_delete['label']}' 삭제 항목을 찾지 못했습니다."); return False
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
        st.session_state.data_loaded_from_sheet = True # 데이터 로드 완료 플래그
        if st.session_state.locations: # 첫 로드 시 메시지 한 번만 표시
            st.success("Google Sheet에서 데이터를 성공적으로 불러왔습니다.")
            last_loc = st.session_state.locations[-1]
            st.session_state.map_center = [last_loc['lat'], last_loc['lon']]
            st.session_state.zoom_start = 10
        else:
            st.info("Google Sheet에 저장된 데이터가 없습니다.")
            st.session_state.map_center = list(default_map_center)
            st.session_state.zoom_start = default_zoom_start


# --- 레이아웃 설정 ---
col1, col2 = st.columns([3, 1.2]) 

with col1: 
    st.subheader("🌍 지도")
    
    current_map_center = st.session_state.get("map_center", list(default_map_center))
    current_zoom_start = st.session_state.get("zoom_start", default_zoom_start)
    if not (isinstance(current_map_center, (list, tuple)) and len(current_map_center) == 2 and all(isinstance(c, (int, float)) for c in current_map_center)):
        current_map_center = list(default_map_center)
        st.session_state.map_center = list(default_map_center)

    m = folium.Map(location=current_map_center, zoom_start=current_zoom_start)

    for loc_data in st.session_state.locations:
        icon_color, icon_symbol, popup_text = 'blue', 'info-sign', loc_data["label"]
        if st.session_state.route_origin_label == loc_data["label"]:
            icon_color, icon_symbol, popup_text = 'green', 'play', f"출발: {loc_data['label']}"
        elif st.session_state.route_destination_label == loc_data["label"]:
            icon_color, icon_symbol, popup_text = 'red', 'stop', f"도착: {loc_data['label']}"
        
        folium.Marker(
            [loc_data["lat"], loc_data["lon"]], 
            tooltip=loc_data["label"], popup=folium.Popup(popup_text, max_width=200),
            icon=folium.Icon(color=icon_color, icon=icon_symbol)
        ).add_to(m)

    if st.session_state.last_clicked_coord:
        folium.Marker(
            [st.session_state.last_clicked_coord["lat"], st.session_state.last_clicked_coord["lng"]],
            tooltip="선택된 위치 (저장 전)", icon=folium.Icon(color='green', icon='plus')
        ).add_to(m)

    map_interaction_data = st_folium(m, width="100%", height=600, key="map_corrected_routes")

    if map_interaction_data:
        new_center = map_interaction_data.get("center")
        if new_center:
            if isinstance(new_center, dict) and "lat" in new_center and "lng" in new_center:
                 st.session_state.map_center = [new_center["lat"], new_center["lng"]]
            elif isinstance(new_center, (list,tuple)) and len(new_center)==2:
                 st.session_state.map_center = list(new_center)

        if map_interaction_data.get("zoom") is not None: st.session_state.zoom_start = map_interaction_data["zoom"]
        
        clicked = map_interaction_data.get("last_clicked")
        if clicked and st.session_state.last_clicked_coord != clicked:
            st.session_state.last_clicked_coord = clicked
            st.rerun()

with col2: 
    st.subheader("📍 마커 추가")
    if not st.session_state.worksheet:
        st.error("Google Sheets에 연결되지 않았습니다. 설정을 확인하세요.")
    
    if st.session_state.last_clicked_coord:
        lat, lon = st.session_state.last_clicked_coord["lat"], st.session_state.last_clicked_coord["lng"]
        st.info(f"선택 위치: {lat:.5f}, {lon:.5f}")
        with st.form("label_form_corrected_routes", clear_on_submit=True):
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
            if c2.button("삭제", key=f"del_corrected_{i}_{loc['label']}"):
                if st.session_state.worksheet and delete_location_from_sheet(st.session_state.worksheet, loc):
                    deleted_loc_label = st.session_state.locations.pop(i)["label"] # pop 후 바로 사용
                    st.toast(f"'{deleted_loc_label}' 삭제 완료!", icon="🚮")
                    if st.session_state.locations:
                        st.session_state.map_center = [st.session_state.locations[-1]['lat'], st.session_state.locations[-1]['lon']]
                    else:
                        st.session_state.map_center = list(default_map_center)
                    st.rerun()
                    break 
    else: st.info("저장된 위치가 없습니다.")
    
    st.markdown("---")
    st.subheader("🚗🚶 경로 찾기")

    if not st.session_state.locations:
        st.info("경로를 찾으려면 먼저 지도에 마커를 1개 이상 저장해주세요.")
    else:
        placeholder_option = "--- 선택 ---"
        marker_labels = [placeholder_option] + [loc["label"] for loc in st.session_state.locations]

        # 선택된 값 유지 또는 기본값(플레이스홀더)으로 설정
        origin_current_val = st.session_state.route_origin_label if st.session_state.route_origin_label in marker_labels else placeholder_option
        dest_current_val = st.session_state.route_destination_label if st.session_state.route_destination_label in marker_labels else placeholder_option
        
        # 만약 이전에 선택한 마커가 삭제되어 더 이상 목록에 없다면 플레이스홀더로 초기화
        if origin_current_val not in marker_labels : origin_current_val = placeholder_option
        if dest_current_val not in marker_labels : dest_current_val = placeholder_option

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
            if st.button("📍 경로 계산", use_container_width=True, key="calc_route_btn_sb"):
                if not st.session_state.route_origin_label or not st.session_state.route_destination_label:
                    st.warning("출발지와 도착지를 모두 선택해주세요.")
                elif st.session_state.route_origin_label == st.session_state.route_destination_label:
                    st.warning("출발지와 도착지가 동일합니다. 다른 지점을 선택해주세요.")
                else:
                    st.session_state.calculating_route = True # API 호출 준비 플래그
                    st.session_state.route_results = None 
                    st.rerun() 
        with col_route_btn2:
            if st.button("🗑️ 경로 해제", key="clear_route_sb", use_container_width=True):
                st.session_state.route_origin_label = None
                st.session_state.route_destination_label = None
                st.session_state.route_results = None
                st.rerun()

    # --- API 호출 결과 처리 로직 ---
    if st.session_state.get("calculating_route"):
        # 이 블록은 AI 어시스턴트가 다음 턴에 tool_code를 실행하고,
        # 그 결과를 바탕으로 이 부분을 채워넣도록 Python 코드를 제공할 것입니다.
        # 지금은 이전 API 호출("서울역" -> "N서울타워")의 결과를 시뮬레이션하여 표시합니다.
        with st.spinner("경로 결과를 처리 중입니다..."):
            results = {}
            # 이전 API 호출 시뮬레이션 결과 (routes=None, additionalNotes만 있음)
            walking_notes = "도보: Direction search appears to be outside Google Maps current coverage area, fallback to Google Search for this search instead."
            driving_notes = "자동차: Direction search appears to be outside Google Maps current coverage area, fallback to Google Search for this search instead."
            
            results["walking"] = {"error_message": walking_notes}
            results["driving"] = {"error_message": driving_notes}
            # results["map_url_combined"] = None # 이 경우 mapUrl도 None이었음

            st.session_state.route_results = results
            st.session_state.calculating_route = False # 계산 완료
            st.rerun() # 결과 표시를 위해 rerun

    # 경로 결과 표시
    if st.session_state.route_results:
        st.markdown("---")
        st.subheader("🔍 경로 검색 결과")
        
        walking_info = st.session_state.route_results.get("walking")
        driving_info = st.session_state.route_results.get("driving")

        if walking_info:
            if walking_info.get("error_message"):
                st.info(f"🚶 {walking_info['error_message']}")
            elif walking_info.get("duration"):
                st.markdown(f"🚶 **도보 경로:**")
                st.markdown(f"  - 예상 시간: {walking_info.get('duration', '정보 없음')}")
                st.markdown(f"  - 거리: {walking_info.get('distance', '정보 없음')}")
                if walking_info.get('url'): st.markdown(f"  - [Google Maps에서 경로 보기]({walking_info.get('url')})")
            else:
                st.info("🚶 도보 경로 정보를 가져올 수 없습니다.")


        if driving_info:
            if driving_info.get("error_message"):
                st.info(f"🚗 {driving_info['error_message']}")
            elif driving_info.get("duration"):
                st.markdown(f"🚗 **자동차 경로:**")
                st.markdown(f"  - 예상 시간: {driving_info.get('duration', '정보 없음')}")
                st.markdown(f"  - 거리: {driving_info.get('distance', '정보 없음')}")
                if driving_info.get('url'): st.markdown(f"  - [Google Maps에서 경로 보기]({driving_info.get('url')})")
            else:
                st.info("🚗 자동차 경로 정보를 가져올 수 없습니다.")
        
        # combined_map_url = st.session_state.route_results.get("map_url_combined")
        # if combined_map_url:
        # st.markdown(f"🗺️ [통합 경로 지도 보기 (Google Maps)]({combined_map_url})")
