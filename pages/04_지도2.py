import streamlit as st
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials # google-auth의 일부

# -----------------------------------------------------------------------------
# 페이지 설정 - 반드시 Streamlit 명령어 중 가장 먼저 실행되어야 합니다!
# -----------------------------------------------------------------------------
st.set_page_config(
    layout="wide",
    page_title="Folium 지도 & Google Sheets (경고 수정)",
    page_icon="🗺️"
)
# -----------------------------------------------------------------------------

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
        st.error("Streamlit Secrets에 'gcp_service_account' 정보가 없습니다. .streamlit/secrets.toml 파일을 확인하세요.")
        return None
    except Exception as e:
        st.error(f"Google Sheets 인증에 실패했습니다: {e}")
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
        st.error(f"스프레드시트 '{sheet_key}'를 찾을 수 없습니다. 이름을 확인하거나 서비스 계정에 공유했는지 확인하세요.")
        return None
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"워크시트 '{worksheet_name_or_index}'를 찾을 수 없습니다.")
        return None
    except Exception as e:
        st.error(f"워크시트 '{sheet_key}' (시트: {worksheet_name_or_index}) 로딩 중 오류: {e}")
        return None

def load_locations_from_sheet(worksheet):
    if worksheet is None:
        st.warning("워크시트가 제공되지 않아 위치 정보를 불러올 수 없습니다.")
        return []
    try:
        records = worksheet.get_all_records()
        locations = []
        for i, record in enumerate(records):
            try:
                lat = record.get("Latitude")
                lon = record.get("Longitude")
                if lat is None or lon is None:
                    st.warning(f"시트의 {i+2}번째 행에 Latitude 또는 Longitude 데이터가 없습니다. 건너뜁니다. (레이블: {record.get('Label', 'N/A')})")
                    continue
                locations.append({
                    "label": str(record.get("Label", f"무명 마커 {i+1}")),
                    "lat": float(lat),
                    "lon": float(lon)
                })
            except ValueError:
                st.warning(f"시트의 {i+2}번째 행 (레이블: '{record.get('Label')}')의 위도/경도 값을 숫자로 변환할 수 없습니다. 건너뜁니다.")
                continue
        if records:
            st.success("Google Sheet에서 데이터를 성공적으로 불러왔습니다.")
        else:
            st.info("Google Sheet에 데이터가 없거나 헤더만 있습니다.")
        return locations
    except Exception as e:
        st.error(f"Google Sheet에서 데이터를 불러오는 중 오류 발생: {e}")
        return []

def add_location_to_sheet(worksheet, location_data):
    if worksheet is None:
        st.error("워크시트가 제공되지 않아 위치 정보를 추가할 수 없습니다.")
        return False
    try:
        worksheet.append_row([location_data["label"], location_data["lat"], location_data["lon"]])
        return True
    except Exception as e:
        st.error(f"Google Sheet에 데이터를 추가하는 중 오류 발생: {e}")
        return False

def delete_location_from_sheet(worksheet, location_to_delete):
    if worksheet is None:
        st.error("워크시트가 제공되지 않아 위치 정보를 삭제할 수 없습니다.")
        return False
    try:
        all_records_values = worksheet.get_all_values()
        header = all_records_values[0]
        try:
            label_col_idx = header.index("Label")
            lat_col_idx = header.index("Latitude")
            lon_col_idx = header.index("Longitude")
        except ValueError:
            st.error("시트 헤더에 'Label', 'Latitude', 'Longitude' 중 하나 이상이 없습니다. 삭제 기능을 사용할 수 없습니다.")
            return False
        row_to_delete_on_sheet = -1
        for i in range(1, len(all_records_values)):
            row_values = all_records_values[i]
            try:
                sheet_label = row_values[label_col_idx]
                sheet_lat = float(row_values[lat_col_idx])
                sheet_lon = float(row_values[lon_col_idx])
                lat_match = abs(sheet_lat - location_to_delete["lat"]) < 0.00001
                lon_match = abs(sheet_lon - location_to_delete["lon"]) < 0.00001
                label_match = sheet_label == location_to_delete["label"]
                if label_match and lat_match and lon_match:
                    row_to_delete_on_sheet = i + 1
                    break
            except (ValueError, IndexError):
                st.warning(f"시트의 {i+1}번째 행 데이터 형식 오류로 삭제 비교 중 건너뜁니다.")
                continue
        if row_to_delete_on_sheet != -1:
            worksheet.delete_rows(row_to_delete_on_sheet)
            return True
        else: # 경고 메시지는 그대로 두되, 이 함수는 성공/실패만 반환
            pass # st.warning(f"Google Sheet에서 '{location_to_delete['label']}' 항목을 찾지 못해 삭제하지 못했습니다.")
            return False # 찾지 못했으므로 False 반환
    except Exception as e:
        st.error(f"Google Sheet에서 데이터를 삭제하는 중 오류 발생: {e}")
        return False

# --- Streamlit App Title ---
st.title("🗺️ 클릭하고 마커 찍기 (Google Sheets 연동)")

# --- 세션 상태 초기화 ---
default_map_center = [37.5665, 126.9780]
default_zoom_start = 6

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

# --- Google Sheets 연결 및 초기 데이터 로드 ---
if st.session_state.gs_client and st.session_state.worksheet is None:
    st.session_state.worksheet = get_worksheet(st.session_state.gs_client, GOOGLE_SHEET_NAME_OR_URL, WORKSHEET_NAME)

if st.session_state.worksheet and not st.session_state.data_loaded_from_sheet:
    with st.spinner("Google Sheets에서 데이터를 불러오는 중..."):
        st.session_state.locations = load_locations_from_sheet(st.session_state.worksheet)
        st.session_state.data_loaded_from_sheet = True
        if st.session_state.locations:
            last_loc = st.session_state.locations[-1]
            st.session_state.map_center = [last_loc['lat'], last_loc['lon']] # 리스트 형식으로 저장
            st.session_state.zoom_start = 10
        else:
            st.session_state.map_center = list(default_map_center) # 리스트 형식으로 저장
            st.session_state.zoom_start = default_zoom_start

# --- 레이아웃 설정 ---
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("🌍 지도")
    if st.button("🔄 Google Sheets에서 데이터 새로고침"):
        if st.session_state.worksheet:
            with st.spinner("Google Sheets에서 데이터를 다시 불러오는 중..."):
                st.session_state.locations = load_locations_from_sheet(st.session_state.worksheet)
                if st.session_state.locations:
                    last_loc = st.session_state.locations[-1]
                    st.session_state.map_center = [last_loc['lat'], last_loc['lon']] # 리스트 형식
                    st.session_state.zoom_start = 10
                else:
                    st.session_state.map_center = list(default_map_center) # 리스트 형식
                    st.session_state.zoom_start = default_zoom_start
                st.rerun()
        else:
            st.warning("Google Sheets에 연결되지 않아 새로고침할 수 없습니다. 설정을 확인하세요.")

    # --- folium.Map 호출 전 map_center 유효성 검사 및 복구 (최후의 방어선) ---
    # 이 코드가 실행되지 않도록 하는 것이 목표입니다.
    current_map_center = st.session_state.get("map_center", list(default_map_center))
    current_zoom_start = st.session_state.get("zoom_start", default_zoom_start)

    if not isinstance(current_map_center, (list, tuple)) or \
       len(current_map_center) != 2 or \
       not all(isinstance(coord, (int, float)) for coord in current_map_center):
        # 이 경고 메시지가 나오지 않도록 하는 것이 이번 수정의 주 목적입니다.
        st.warning(f"유효하지 않은 map_center 값({current_map_center})이 감지되어 기본값으로 재설정합니다. (이 메시지는 정상적으로는 나타나지 않아야 합니다.)")
        current_map_center = list(default_map_center)
        current_zoom_start = default_zoom_start
        st.session_state.map_center = list(default_map_center)
        st.session_state.zoom_start = default_zoom_start


    m = folium.Map(location=current_map_center, zoom_start=current_zoom_start)

    for loc_data in st.session_state.locations:
        folium.Marker([loc_data["lat"], loc_data["lon"]], tooltip=loc_data["label"], icon=folium.Icon(color='blue')).add_to(m)

    if st.session_state.last_clicked_coord:
        folium.Marker(
            [st.session_state.last_clicked_coord["lat"], st.session_state.last_clicked_coord["lng"]],
            tooltip="선택된 위치 (저장 전)",
            icon=folium.Icon(color='green', icon='plus')
        ).add_to(m)

    map_interaction_data = st_folium(
        m,
        width="100%",
        height=600,
        returned_objects=["last_clicked", "center", "zoom"],
        key="folium_map_final_check"
    )

    # 지도 상호작용 결과 처리 - map_center가 항상 [lat, lng] 리스트 형식을 갖도록 수정
    if map_interaction_data:
        new_center_from_map = map_interaction_data.get("center")
        if new_center_from_map is not None:
            # st_folium의 'center'가 어떤 형식이든 [lat, lng] 리스트로 변환/보장
            if isinstance(new_center_from_map, dict) and "lat" in new_center_from_map and "lng" in new_center_from_map:
                st.session_state.map_center = [new_center_from_map["lat"], new_center_from_map["lng"]]
            elif isinstance(new_center_from_map, (list, tuple)) and len(new_center_from_map) == 2 and \
                 all(isinstance(c, (int, float)) for c in new_center_from_map):
                st.session_state.map_center = list(new_center_from_map) # 튜플일 경우 리스트로 변환
            # else: 예상치 못한 형식이면 업데이트하지 않아 기존 map_center 유지 (경고는 이미 위에서 처리)

        new_zoom_from_map = map_interaction_data.get("zoom")
        if new_zoom_from_map is not None:
            st.session_state.zoom_start = new_zoom_from_map

        last_clicked_update = map_interaction_data.get("last_clicked") # {'lat': ..., 'lng': ...} 형태
        if last_clicked_update:
            if st.session_state.last_clicked_coord != last_clicked_update:
                st.session_state.last_clicked_coord = last_clicked_update # 딕셔너리 형태로 저장
                st.rerun()

with col2:
    st.subheader("📍 마커 정보")

    if not st.session_state.gs_client or not st.session_state.worksheet:
        st.error("Google Sheets에 연결되지 않았습니다. 다음을 확인하세요:\n1. Streamlit Secrets 설정(.streamlit/secrets.toml 또는 Cloud Secrets)\n2. Google Sheet 이름/URL 및 공유 설정\n3. 인터넷 연결")
    
    if st.session_state.last_clicked_coord: # last_clicked_coord는 딕셔너리
        lat = st.session_state.last_clicked_coord["lat"]
        lon = st.session_state.last_clicked_coord["lng"]
        st.info(f"선택된 위치: 위도 {lat:.5f}, 경도 {lon:.5f}")

        with st.form("label_form_final", clear_on_submit=True):
            default_label_text = f"마커 {len(st.session_state.locations) + 1}"
            marker_label = st.text_input("지명 또는 장소 이름 입력", value=default_label_text)
            submit_button = st.form_submit_button("✅ 마커 저장 (Sheet에 추가)")

            if submit_button:
                if not st.session_state.worksheet:
                    st.error("워크시트에 연결되지 않아 저장할 수 없습니다.")
                else:
                    new_location_data = {
                        "label": marker_label,
                        "lat": lat, # 숫자
                        "lon": lon  # 숫자
                    }
                    with st.spinner("Google Sheet에 저장 중..."):
                        if add_location_to_sheet(st.session_state.worksheet, new_location_data):
                            st.session_state.locations.append(new_location_data)
                            st.toast(f"📍 '{marker_label}' 위치가 Google Sheet에 저장되었습니다.", icon="📄")
                            # map_center는 반드시 [lat, lon] 리스트 형태여야 함
                            st.session_state.map_center = [lat, lon]
                            st.session_state.zoom_start = 12
                            st.session_state.last_clicked_coord = None
                            st.rerun()
    else:
        st.info("지도를 클릭하여 마커를 추가할 위치를 선택하세요.")

    st.divider()
    
    st.subheader("📋 저장된 위치 목록 (Sheet 동기화)")
    if st.session_state.locations:
        for i, loc_item in enumerate(st.session_state.locations):
            item_col, delete_col = st.columns([4,1])
            with item_col:
                st.markdown(f"**{loc_item['label']}** ({loc_item['lat']:.5f}, {loc_item['lon']:.5f})")
            with delete_col:
                button_key = f"delete_gs_final_{i}_{loc_item['label']}_{loc_item['lat']}_{loc_item['lon']}"
                if st.button(f"삭제", key=button_key):
                    if not st.session_state.worksheet:
                        st.error("워크시트에 연결되지 않아 삭제할 수 없습니다.")
                    else:
                        location_to_delete_data = loc_item
                        with st.spinner("Google Sheet에서 삭제 중..."):
                            if delete_location_from_sheet(st.session_state.worksheet, location_to_delete_data):
                                st.session_state.locations.pop(i)
                                st.toast(f"🗑️ '{location_to_delete_data['label']}' 위치가 Google Sheet에서 삭제되었습니다.", icon="🚮")
                                if not st.session_state.locations:
                                    st.session_state.map_center = list(default_map_center) # 리스트 형식
                                    st.session_state.zoom_start = default_zoom_start
                                elif st.session_state.locations:
                                    last_loc_data = st.session_state.locations[-1]
                                    # map_center는 반드시 [lat, lon] 리스트 형태여야 함
                                    st.session_state.map_center = [last_loc_data['lat'], last_loc_data['lon']]
                                st.rerun()
                                break 
    else:
        st.info("아직 저장된 위치가 없거나 Google Sheet에서 불러오지 못했습니다.")
