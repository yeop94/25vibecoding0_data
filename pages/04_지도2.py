import gspread
from google.oauth2.service_account import Credentials # google-auth의 일부

# Google Sheets 관련 설정
# 실제 운영 시에는 URL이나 이름을 secrets, 환경변수 등으로 관리하는 것이 좋습니다.
GOOGLE_SHEET_NAME_OR_URL = "내 마커 데이터" # 공유한 Google Sheet의 이름 또는 전체 URL
WORKSHEET_NAME = "Sheet1" # 또는 사용하려는 시트의 이름

# gspread 클라이언트 초기화 함수
def init_gspread_client():
    try:
        # Streamlit Secrets 사용
        creds_dict = st.secrets["gcp_service_account"]
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        return gc
    except Exception as e:
        st.error(f"Google Sheets 인증에 실패했습니다: {e}")
        st.error("secrets.toml 파일에 GCP 서비스 계정 정보가 올바르게 설정되었는지 확인하세요.")
        return None

# 워크시트 가져오기 함수
def get_worksheet(gc, sheet_key, worksheet_name_or_index=0):
    try:
        if "docs.google.com/spreadsheets" in sheet_key: # URL인 경우
             spreadsheet = gc.open_by_url(sheet_key)
        else: # 이름인 경우
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
        st.error(f"워크시트 로딩 중 오류: {e}")
        return None

# Google Sheet에서 위치 정보 불러오기
def load_locations_from_sheet(worksheet):
    if worksheet is None:
        return []
    try:
        records = worksheet.get_all_records() # 헤더를 키로 사용하는 딕셔너리 리스트 반환
        locations = []
        for record in records:
            try:
                locations.append({
                    "label": str(record.get("Label", "")), # Label 키가 없을 경우 대비
                    "lat": float(record.get("Latitude", 0.0)),   # Latitude 키가 없을 경우 대비 및 float 변환
                    "lon": float(record.get("Longitude", 0.0)) # Longitude 키가 없을 경우 대비 및 float 변환
                })
            except ValueError:
                st.warning(f"'{record.get('Label')}' 항목의 위도/경도 값을 변환할 수 없습니다. 건너뜁니다.")
                continue # 잘못된 형식의 데이터는 건너뜀
        st.success("Google Sheet에서 데이터를 성공적으로 불러왔습니다.")
        return locations
    except Exception as e:
        st.error(f"Google Sheet에서 데이터를 불러오는 중 오류 발생: {e}")
        return []

# Google Sheet에 위치 정보 추가하기
def add_location_to_sheet(worksheet, location_data):
    if worksheet is None:
        return False
    try:
        # 헤더 순서: Label, Latitude, Longitude
        worksheet.append_row([location_data["label"], location_data["lat"], location_data["lon"]])
        return True
    except Exception as e:
        st.error(f"Google Sheet에 데이터를 추가하는 중 오류 발생: {e}")
        return False

# Google Sheet에서 위치 정보 삭제하기
def delete_location_from_sheet(worksheet, location_to_delete):
    if worksheet is None:
        return False
    try:
        all_records = worksheet.get_all_records() # 데이터만 가져옴 (헤더 제외, 0-indexed list of dicts)
        row_to_delete_on_sheet = -1

        for idx, record in enumerate(all_records):
            # 부동소수점 비교 시 정확도 문제 고려 (작은 오차 허용)
            lat_match = abs(float(record.get("Latitude", 0.0)) - location_to_delete["lat"]) < 0.00001
            lon_match = abs(float(record.get("Longitude", 0.0)) - location_to_delete["lon"]) < 0.00001
            label_match = str(record.get("Label", "")) == location_to_delete["label"]

            if label_match and lat_match and lon_match:
                row_to_delete_on_sheet = idx + 2 # gspread는 1-indexed, 헤더가 1번째 줄이므로 +2
                break
        
        if row_to_delete_on_sheet != -1:
            worksheet.delete_rows(row_to_delete_on_sheet)
            return True
        else:
            st.warning("Google Sheet에서 삭제할 항목을 찾지 못했습니다.")
            return False
    except Exception as e:
        st.error(f"Google Sheet에서 데이터를 삭제하는 중 오류 발생: {e}")
        return False


import streamlit as st
import folium
from streamlit_folium import st_folium
# gspread 와 Credentials 는 위 헬퍼 함수 섹션에서 import

# --- Google Sheets Helper Functions (위에 정의된 함수들) ---
# init_gspread_client, get_worksheet, load_locations_from_sheet,
# add_location_to_sheet, delete_location_from_sheet
# 이 함수들을 여기에 붙여넣거나, 별도 파일로 분리 후 import 합니다.
# ---------------------------------------------------------

st.set_page_config(layout="wide")
st.title("🗺️ 클릭하고 마커 찍기 (Google Sheets 연동)")

# Google Sheets 클라이언트 및 워크시트 초기화
# 앱 로드 시 한 번만 실행되도록 st.session_state 활용
if 'gs_client' not in st.session_state:
    st.session_state.gs_client = init_gspread_client()
if 'worksheet' not in st.session_state and st.session_state.gs_client:
    st.session_state.worksheet = get_worksheet(st.session_state.gs_client, GOOGLE_SHEET_NAME_OR_URL, WORKSHEET_NAME)
else:
    st.session_state.worksheet = None


# 세션 상태 초기화 (데이터 로딩은 아래에서)
if "locations" not in st.session_state:
    st.session_state.locations = [] # 초기에는 비어있고, 시트에서 로드
if "map_center" not in st.session_state:
    st.session_state.map_center = [37.5665, 126.9780]
if "zoom_start" not in st.session_state:
    st.session_state.zoom_start = 6
if "last_clicked_coord" not in st.session_state:
    st.session_state.last_clicked_coord = None
if "data_loaded_from_sheet" not in st.session_state:
    st.session_state.data_loaded_from_sheet = False

# Google Sheet에서 데이터 로드 (앱 시작 시 또는 새로고침 시)
if st.session_state.worksheet and not st.session_state.data_loaded_from_sheet:
    with st.spinner("Google Sheets에서 데이터를 불러오는 중..."):
        st.session_state.locations = load_locations_from_sheet(st.session_state.worksheet)
        st.session_state.data_loaded_from_sheet = True # 한 번 로드되면 다시 로드하지 않도록 플래그 설정
        if st.session_state.locations: # 로드된 데이터가 있다면 지도를 해당 위치로 조정
             last_loc = st.session_state.locations[-1]
             st.session_state.map_center = [last_loc['lat'], last_loc['lon']]
             st.session_state.zoom_start = 10


# 레이아웃 설정
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("🌍 지도")
    if st.button("🔄 Google Sheets에서 데이터 새로고침"):
        with st.spinner("Google Sheets에서 데이터를 다시 불러오는 중..."):
            st.session_state.locations = load_locations_from_sheet(st.session_state.worksheet)
            if st.session_state.locations:
                 last_loc = st.session_state.locations[-1]
                 st.session_state.map_center = [last_loc['lat'], last_loc['lon']]
                 st.session_state.zoom_start = 10
            else: # 데이터가 없는 경우 초기 중심으로
                st.session_state.map_center = [37.5665, 126.9780]
                st.session_state.zoom_start = 6
            st.experimental_rerun()
    if not isinstance(st.session_state.get("map_center"), (list, tuple)) or \
       len(st.session_state.get("map_center", [])) != 2 or \
       not all(isinstance(coord, (int, float)) for coord in st.session_state.get("map_center", [])):
    
        st.warning(f"유효하지 않은 map_center 값({st.session_state.get('map_center')})이 감지되어 기본값으로 재설정합니다.")
        st.session_state.map_center = [37.5665, 126.9780]  # 서울 기본 위치
        st.session_state.zoom_start = 6                   # 기본 줌 레벨

    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.zoom_start)

    for loc in st.session_state.locations:
        folium.Marker([loc["lat"], loc["lon"]], tooltip=loc["label"], icon=folium.Icon(color='blue')).add_to(m)

    if st.session_state.last_clicked_coord:
        folium.Marker(
            [st.session_state.last_clicked_coord["lat"], st.session_state.last_clicked_coord["lng"]],
            tooltip="선택된 위치 (저장 전)",
            icon=folium.Icon(color='green', icon='plus')
        ).add_to(m)

    map_data = st_folium(
        m,
        width="100%",
        height=600,
        returned_objects=["last_clicked", "center", "zoom"],
        key="folium_map_gs" # 이전과 다른 키 사용 가능
    )

    # 수정된 코드:
    if map_data:
        new_center_from_map = map_data.get("center")
        if new_center_from_map is not None: # None이 아닐 때만 업데이트
            st.session_state.map_center = new_center_from_map
        # else: new_center_from_map이 None이면 st.session_state.map_center는 이전 값을 유지
    
        # zoom 값도 유사하게 처리할 수 있습니다 (선택적)
        new_zoom_from_map = map_data.get("zoom")
        if new_zoom_from_map is not None:
            st.session_state.zoom_start = new_zoom_from_map
    
        if map_data.get("last_clicked"):
            st.session_state.last_clicked_coord = map_data["last_clicked"]
            st.experimental_rerun()

with col2:
    st.subheader("📍 마커 정보")

    if not st.session_state.gs_client or not st.session_state.worksheet:
        st.warning("Google Sheets에 연결되지 않았습니다. 설정을 확인해주세요.")
    
    if st.session_state.last_clicked_coord:
        lat = st.session_state.last_clicked_coord["lat"]
        lon = st.session_state.last_clicked_coord["lng"]
        st.info(f"선택된 위치: 위도 {lat:.5f}, 경도 {lon:.5f}")

        with st.form("label_form_gs", clear_on_submit=True):
            default_label = f"마커 {len(st.session_state.locations) + 1}"
            label = st.text_input("지명 또는 장소 이름 입력", value=default_label)
            submitted = st.form_submit_button("✅ 마커 저장 (및 Sheet에 추가)")

            if submitted:
                if not st.session_state.worksheet:
                    st.error("워크시트에 연결되지 않아 저장할 수 없습니다.")
                else:
                    new_location = {
                        "label": label,
                        "lat": lat,
                        "lon": lon
                    }
                    with st.spinner("Google Sheet에 저장 중..."):
                        if add_location_to_sheet(st.session_state.worksheet, new_location):
                            st.session_state.locations.append(new_location) # 로컬 상태에도 반영
                            st.toast(f"📍 '{label}' 위치가 Google Sheet에 저장되었습니다.", icon="📄")
                            st.session_state.map_center = [lat, lon]
                            st.session_state.zoom_start = 12
                            st.session_state.last_clicked_coord = None
                            st.experimental_rerun()
                        else:
                            st.error("Google Sheet에 저장 실패했습니다.")
    else:
        st.info("지도를 클릭하여 마커를 추가할 위치를 선택하세요.")

    st.divider()
    
    st.subheader("📋 저장된 위치 목록 (Sheet 동기화)")
    if st.session_state.locations:
        for i, loc in reversed(list(enumerate(st.session_state.locations))):
            item_col, delete_col = st.columns([4,1])
            with item_col:
                st.markdown(f"**{loc['label']}** ({loc['lat']:.5f}, {loc['lon']:.5f})")
            with delete_col:
                if st.button(f"삭제", key=f"delete_gs_{i}"):
                    if not st.session_state.worksheet:
                        st.error("워크시트에 연결되지 않아 삭제할 수 없습니다.")
                    else:
                        location_to_delete = st.session_state.locations[i] # 삭제 전 정보 저장
                        with st.spinner("Google Sheet에서 삭제 중..."):
                            if delete_location_from_sheet(st.session_state.worksheet, location_to_delete):
                                st.session_state.locations.pop(i) # 로컬 상태에서도 삭제
                                st.toast(f"🗑️ '{location_to_delete['label']}' 위치가 Google Sheet에서 삭제되었습니다.", icon=" অল্প")
                                # 지도 중심 조정 로직 (선택적)
                                if not st.session_state.locations:
                                    st.session_state.map_center = [37.5665, 126.9780]
                                    st.session_state.zoom_start = 6
                                elif st.session_state.locations:
                                    last_loc = st.session_state.locations[-1]
                                    st.session_state.map_center = [last_loc['lat'], last_loc['lon']]
                                st.experimental_rerun()
                            else:
                                st.error(f"Google Sheet에서 '{location_to_delete['label']}' 삭제 실패했습니다.")
    else:
        st.info("아직 저장된 위치가 없거나 Google Sheet에서 불러오지 못했습니다.")
