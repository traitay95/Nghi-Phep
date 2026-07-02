import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(
    page_title="Hệ Thống Đăng Ký Nghỉ Phép Tuần",
    page_icon="📅",
    layout="centered"
)

st.title("📅 Đăng Ký Nghỉ Phép Trực Tuyến")
st.markdown("---")

# --- KẾT NỐI GOOGLE SHEETS BẰNG GSPREAD ---
def get_google_sheet():
    # Sử dụng link cấu hình từ mục Secrets để khởi tạo kết nối thông qua gspread công khai
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    
    # Kết nối ẩn danh thông qua client gspread công khai được mở quyền Editor
    gc = gspread.public()
    # Mở file và trỏ thẳng vào Trang tính đầu tiên (Sheet1)
    sh = gc.open_by_url(sheet_url)
    return sh.sheet1

try:
    wks = get_google_sheet()
except Exception as e:
    st.error("⚠️ Không thể kết nối tới Google Sheets. Vui lòng kiểm tra lại quyền Chia sẻ (Editor) hoặc link trong Secrets!")
    st.stop()

# Hàm đọc và đồng bộ dữ liệu + Tự động dọn dẹp vào 0h Thứ 2
def load_and_sync_data():
    # Đọc toàn bộ dữ liệu từ Sheets về
    records = wks.get_all_records()
    df = pd.DataFrame(records)
    
    # Chuẩn hóa nếu bảng trống
    if df.empty or "Ngay_Dang_Ky" not in df.columns:
        df = pd.DataFrame(columns=["STT", "Ho_Ten", "Khoa_Phong", "Ngay_Nghi", "Mat_Khau", "Ngay_Dang_Ky"])
        return df

    # Loại bỏ dòng trống
    df = df.dropna(subset=["Ho_Ten"])
    
    if not df.empty:
        # 🔄 LOGIC TỰ ĐỘNG XOÁ DỮ LIỆU TUẦN CŨ (0h Thứ 2)
        today = datetime.now()
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
                
            # Ghi đè lại dữ liệu sạch lên Sheets bằng cách xóa hết rồi gieo lại dòng tiêu đề + data
            wks.clear()
            wks.update([df_tuan_nay.columns.values.tolist()] + df_tuan_nay.values.tolist())
            return df_tuan_nay

        df = df.drop(columns=['Ngay_Dang_Ky_DT'])
        
    return df

df_list = load_and_sync_data()

# --- GIAO DIỆN CHÍNH ---
tab1, tab2 = st.tabs(["✍️ Đăng Ký Nghỉ Phép", "❌ Hủy Lịch Nghỉ"])

# TAB 1: ĐĂNG KÝ NGHỈ PHÉP
with tab1:
    st.subheader("Điền thông tin đăng ký")
    with st.form(key="form_dang_ky", clear_on_submit=True):
        ho_ten = st.text_input("1. Họ và Tên:").strip()
        khoa_phong = st.text_input("2. Khoa/Phòng / Vị trí làm việc:").strip()
        ngay_nghi = st.date_input("3. Chọn Ngày nghỉ phép:", min_value=datetime.now().date())
        mat_khau = st.text_input("4. Mật khẩu chỉnh sửa (Dùng để hủy nếu đổi ý):", type="password").strip()
        
        submit_button = st.form_submit_button(label="Gửi Đăng Ký")
        
        if submit_button:
            if not ho_ten or not khoa_phong or not mat_khau:
                st.error("⚠️ Vui lòng điền đầy đủ tất cả các mục thông tin!")
            else:
                stt_moi = len(df_list) + 1
                ngay_nghi_str = ngay_nghi.strftime("%d/%m/%Y")
                ngay_tao_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Append dòng mới trực tiếp xuống cuối file Sheets
                wks.append_row([stt_moi, ho_ten, khoa_phong, ngay_nghi_str, mat_khau, ngay_tao_str])
                
                st.success(f"🎉 Chúc mừng {ho_ten} đã đăng ký nghỉ phép thành công!")
                st.rerun()

# TAB 2: HỦY ĐĂNG KÝ
with tab2:
    st.subheader("Xóa lịch đăng ký nghỉ phép")
    if df_list.empty:
        st.info("Hiện chưa có ai đăng ký nghỉ phép trong tuần này.")
    else:
        danh_sach_chon = []
        for idx, row in df_list.iterrows():
            danh_sach_chon.append(f"STT {int(row['STT'])} - {row['Ho_Ten']} ({row['Khoa_Phong']} - Ngày {row['Ngay_Nghi']})")
            
        lua_chon_xoa = st.selectbox("Chọn dòng muốn hủy bỏ:", options=danh_sach_chon)
        mat_khau_nhap = st.text_input("Nhập mật khẩu chỉnh sửa của bạn để xác nhận xóa:", type="password").strip()
        
        btn_xoa = st.button("Xác Nhận Hủy Lịch Nghỉ", type="primary")
        
        if btn_xoa:
            stt_can_xoa = int(lua_chon_xoa.split(" ")[1])
            mat_khau_dung = str(df_list.loc[df_list['STT'] == stt_can_xoa, 'Mat_Khau'].values[0])
            
            if mat_khau_nhap == mat_khau_dung:
                df_list = df_list[df_list['STT'] != stt_can_xoa]
                if not df_list.empty:
                    df_list['STT'] = range(1, len(df_list) + 1)
                
                # Xóa trắng và đồng bộ lại bảng sau khi xóa dòng
                wks.clear()
                wks.update([df_list.columns.values.tolist()] + df_list.values.tolist())
                st.success("✅ Đã hủy lịch nghỉ phép thành công!")
                st.rerun()
            else:
                st.error("❌ Mật khẩu chỉnh sửa không chính xác! Vui lòng kiểm tra lại.")

# --- BẢNG TỔNG HỢP ---
st.markdown("---")
st.subheader("📊 Bảng Tổng Hợp Nghỉ Phép Trong Tuần")

if not df_list.empty:
    df_hien_thi = df_list.copy()
    df_hien_thi = df_hien_thi.rename(columns={"Ho_Ten": "Họ và Tên", "Khoa_Phong": "Khoa/Phòng", "Ngay_Nghi": "Ngày nghỉ phép"})
    st.dataframe(df_hien_thi[["STT", "Họ và Tên", "Khoa/Phòng", "Ngày nghỉ phép"]], use_container_width=True, hide_index=True)
else:
    st.info("Hiện tại chưa có ai đăng ký nghỉ phép trong tuần này.")