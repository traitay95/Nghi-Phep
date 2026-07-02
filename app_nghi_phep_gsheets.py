import streamlit as st
import pandas as pd
import requests
import json
import base64
from datetime import datetime, timedelta

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(
    page_title="Hệ Thống Đăng Ký Nghỉ Phép Tuần",
    page_icon="📅",
    layout="centered"
)

st.title("📅 Đăng Ký Nghỉ Phép Trực Tuyến")
st.markdown("---")

# --- THÔNG TIN CẤU HÌNH GITHUB API ---
GITHUB_TOKEN = st.secrets["github"]["token"]
REPO_NAME = st.secrets["github"]["repo"]
FILE_PATH = "data_nghi_phep.json"
API_URL = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# --- CÁC HÀM XỬ LÝ DATABASE GITHUB ---
def get_github_data():
    """Đọc dữ liệu file JSON từ GitHub về ứng dụng"""
    response = requests.get(API_URL, headers=HEADERS)
    if response.status_code == 200:
        file_data = response.json()
        content = base64.b64decode(file_data["content"]).decode("utf-8")
        sha = file_data["sha"]
        return json.loads(content), sha
    else:
        return [], None

def save_github_data(data, sha, commit_message="Update data"):
    """Ghi đè/Đẩy dữ liệu mới lên lại GitHub"""
    content_str = json.dumps(data, indent=4, ensure_ascii=False)
    content_encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": commit_message,
        "content": content_encoded,
    }
    if sha:
        payload["sha"] = sha
        
    response = requests.put(API_URL, headers=HEADERS, json=payload)
    return response.status_code in [200, 201]

# --- ĐỒNG BỘ VÀ TỰ ĐỘNG CLEAR DỮ LIỆU THỨ 2 ---
def load_and_sync_data():
    raw_data, sha = get_github_data()
    df = pd.DataFrame(raw_data)
    
    if df.empty or "Ngay_Dang_Ky" not in df.columns:
        df = pd.DataFrame(columns=["STT", "Ho_Ten", "Khoa_Phong", "Ngay_Nghi", "Mat_Khau", "Ngay_Dang_Ky"])
        return df, sha

    # Lấy thời gian chuẩn theo múi giờ Việt Nam (UTC+7)
    today = datetime.utcnow() + timedelta(hours=7)
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    df['Ngay_Dang_Ky_DT'] = pd.to_datetime(df['Ngay_Dang_Ky'], errors='coerce', format='%Y-%m-%d %H:%M:%S')
    dong_tuan_cu = df[df['Ngay_Dang_Ky_DT'] < start_of_week]
    
    if not dong_tuan_cu.empty:
        df_tuan_nay = df[df['Ngay_Dang_Ky_DT'] >= start_of_week].copy()
        df_tuan_nay = df_tuan_nay.drop(columns=['Ngay_Dang_Ky_DT'])
        
        if not df_tuan_nay.empty:
            df_tuan_nay['STT'] = range(1, len(df_tuan_nay) + 1)
        else:
            df_tuan_nay = pd.DataFrame(columns=["STT", "Ho_Ten", "Khoa_Phong", "Ngay_Nghi", "Mat_Khau", "Ngay_Dang_Ky"])
            
        list_to_save = df_tuan_nay.to_dict(orient="records")
        save_github_data(list_to_save, sha, "Auto clear tuần cũ")
        _, new_sha = get_github_data()
        return df_tuan_nay, new_sha

    df = df.drop(columns=['Ngay_Dang_Ky_DT'])
    return df, sha

# Tải dữ liệu về biến toàn cục của App
df_list, current_sha = load_and_sync_data()

# --- KIỂM TRA THỨ TRONG TUẦN (MÚI GIỜ VN) ---
now_vn = datetime.utcnow() + timedelta(hours=7)
thu_trong_tuan = now_vn.weekday()  # 0: Thứ 2, 4: Thứ 6, 5: Thứ 7, 6: Chủ Nhật
la_ngay_khoa = thu_trong_tuan in [4, 5, 6]  # True nếu là Thứ 6, 7, CN

# --- GIAO DIỆN ỨNG DỤNG ---
tab1, tab2 = st.tabs(["✍️ Đăng Ký Nghỉ Phép", "❌ Hủy Lịch Nghỉ"])

# ==============================================================================
# TAB 1: ĐĂNG KÝ NGHỈ PHÉP
# ==============================================================================
with tab1:
    st.subheader("Điền thông tin đăng ký")
    
    if la_ngay_khoa:
        st.error("🔒 Hệ thống đã khóa chức năng ĐĂNG KÝ vào Thứ 6, Thứ 7 và Chủ Nhật.")
    
    with st.form(key="form_dang_ky", clear_on_submit=True):
        ho_ten = st.text_input("1. Họ và Tên:", disabled=la_ngay_khoa).strip()
        khoa_phong = st.text_input("2. Khoa/Phòng / Vị trí làm việc:", disabled=la_ngay_khoa).strip()
        ngay_nghi = st.date_input("3. Chọn Ngày nghỉ phép:", min_value=now_vn.date(), disabled=la_ngay_khoa)
        mat_khau = st.text_input("4. Mật khẩu chỉnh sửa (Dùng để hủy nếu đổi ý):", type="password", disabled=la_ngay_khoa).strip()
        
        submit_button = st.form_submit_button(label="Gửi Đăng Ký", disabled=la_ngay_khoa)
        
        if submit_button and not la_ngay_khoa:
            if not ho_ten or not khoa_phong or not mat_khau:
                st.error("⚠️ Vui lòng điền đầy đủ tất cả các mục thông tin!")
            else:
                stt_moi = len(df_list) + 1
                ngay_nghi_str = ngay_nghi.strftime("%d/%m/%Y")
                # Ghi nhận chính xác ngày giờ đăng ký theo giờ VN
                ngay_tao_str = now_vn.strftime("%Y-%m-%d %H:%M:%S")
                
                new_row = pd.DataFrame([{
                    "STT": stt_moi,
                    "Ho_Ten": ho_ten,
                    "Khoa_Phong": khoa_phong,
                    "Ngay_Nghi": ngay_nghi_str,
                    "Mat_Khau": mat_khau,
                    "Ngay_Dang_Ky": ngay_tao_str
                }])
                
                df_updated = pd.concat([df_list, new_row], ignore_index=True)
                list_to_save = df_updated.to_dict(orient="records")
                
                if save_github_data(list_to_save, current_sha, f"User {ho_ten} dang ky"):
                    st.success(f"🎉 Chúc mừng {ho_ten} đã đăng ký nghỉ phép thành công!")
                    st.rerun()
                else:
                    st.error("❌ Lỗi hệ thống khi lưu trữ vào GitHub. Hãy thử lại!")

# ==============================================================================
# TAB 2: HỦY ĐĂNG KÝ
# ==============================================================================
with tab2:
    st.subheader("Xóa lịch đăng ký nghỉ phép")
    
    if la_ngay_khoa:
        st.error("🔒 Hệ thống đã khóa chức năng XÓA/HỦY lịch nghỉ vào Thứ 6, Thứ 7 và Chủ Nhật.")
        
    if df_list.empty:
        st.info("Hiện chưa có ai đăng ký nghỉ phép trong tuần này.")
    else:
        danh_sach_chon = []
        for idx, row in df_list.iterrows():
            danh_sach_chon.append(f"STT {int(row['STT'])} - {row['Ho_Ten']} ({row['Khoa_Phong']} - Ngày {row['Ngay_Nghi']})")
            
        lua_chon_xoa = st.selectbox("Chọn dòng muốn hủy bỏ:", options=danh_sach_chon, disabled=la_ngay_khoa)
        mat_khau_nhap = st.text_input("Nhập mật khẩu chỉnh sửa của bạn để xác nhận xóa:", type="password", disabled=la_ngay_khoa).strip()
        
        btn_xoa = st.button("Xác Nhận Hủy Lịch Nghỉ", type="primary", disabled=la_ngay_khoa)
        
        if btn_xoa and not la_ngay_khoa:
            stt_can_xoa = int(lua_chon_xoa.split(" ")[1])
            mat_khach_dung = str(df_list.loc[df_list['STT'] == stt_can_xoa, 'Mat_Khau'].values[0])
            
            if mat_khau_nhap == mat_khach_dung:
                df_list = df_list[df_list['STT'] != stt_can_xoa]
                if not df_list.empty:
                    df_list['STT'] = range(1, len(df_list) + 1)
                
                list_to_save = df_list.to_dict(orient="records")
                
                if save_github_data(list_to_save, current_sha, f"Huy lich STT {stt_can_xoa}"):
                    st.success("✅ Đã hủy lịch nghỉ phép thành công!")
                    st.rerun()
                else:
                    st.error("❌ Không thể đồng bộ xóa lên GitHub. Thử lại sau!")
            else:
                st.error("❌ Mật khẩu chỉnh sửa không chính xác! Vui lòng kiểm tra lại.")

# --- KHU VỰC HIỂN THỊ BẢNG TỔNG HỢP ---
st.markdown("---")
st.subheader("📊 Bảng Tổng Hợp Nghỉ Phép Trong Tuần")

if not df_list.empty:
    df_hien_thi = df_list.copy()
    df_hien_thi = df_hien_thi.rename(columns={
        "Ho_Ten": "Họ và Tên",
        "Khoa_Phong": "Khoa/Phòng",
        "Ngay_Nghi": "Ngày nghỉ phép",
        "Ngay_Dang_Ky": "Ngày giờ đăng ký"
    })
    # Hiển thị thêm cột Ngày giờ đăng ký ra bảng công khai để mọi người theo dõi
    st.dataframe(
        df_hien_thi[["STT", "Họ và Tên", "Khoa/Phòng", "Ngày nghỉ phép", "Ngày giờ đăng ký"]], 
        use_container_width=True, 
        hide_index=True
    )
else:
    st.info("Hiện tại chưa có ai đăng ký nghỉ phép trong tuần này.")