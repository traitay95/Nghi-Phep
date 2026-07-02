import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(
    page_title="Hệ Thống Đăng Ký Nghỉ Phép Tuần",
    page_icon="📅",
    layout="centered"
)

st.title("📅 Đăng Ký Nghỉ Phép Trực Tuyến")
st.markdown("---")

# --- KẾT NỐI GOOGLE SHEETS VIA STREAMLIT CONNECTION ---
# Sử dụng cơ chế st.connection chính thức không cần file JSON bảo mật
conn = st.connection("gsheets", type=GSheetsConnection)

# Hàm đọc và đồng bộ dữ liệu + Tự động dọn dẹp vào 0h Thứ 2
def load_and_sync_data():
    # Đọc dữ liệu từ Sheet1, đặt ttl=0 để luôn lấy dữ liệu mới nhất, tránh lưu cache cũ
    df = conn.read(worksheet="Sheet1", ttl=0)
    
    # Chuẩn hóa dữ liệu nếu sheet hoàn toàn trống (chỉ có tiêu đề) hoặc bị lỗi
    if df.empty or "Ngay_Dang_Ky" not in df.columns:
        df = pd.DataFrame(columns=["STT", "Ho_Ten", "Khoa_Phong", "Ngay_Nghi", "Mat_Khau", "Ngay_Dang_Ky"])
        return df

    # Loại bỏ các dòng trống vô định nếu có
    df = df.dropna(subset=["Ho_Ten"])
    
    if not df.empty:
        # 🔄 LOGIC TỰ ĐỘNG XOÁ DỮ LIỆU TUẦN CŨ (0h Thứ 2 hàng tuần)
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Chuyển cột ngày hệ thống sang datetime để so sánh mốc thời gian
        df['Ngay_Dang_Ky_DT'] = pd.to_datetime(df['Ngay_Dang_Ky'], errors='coerce', format='%Y-%m-%d %H:%M:%S')
        
        # Kiểm tra xem có dòng nào thuộc tuần cũ hay không
        dong_tuan_cu = df[df['Ngay_Dang_Ky_DT'] < start_of_week]
        
        if not dong_tuan_cu.empty:
            # Chỉ giữ lại các dòng đăng ký từ 0h Thứ 2 tuần này trở đi
            df_tuan_nay = df[df['Ngay_Dang_Ky_DT'] >= start_of_week].copy()
            df_tuan_nay = df_tuan_nay.drop(columns=['Ngay_Dang_Ky_DT'])
            
            # Đánh lại số STT tuần mới bắt đầu từ mốc 1
            if not df_tuan_nay.empty:
                df_tuan_nay['STT'] = range(1, len(df_tuan_nay) + 1)
            else:
                df_tuan_nay = pd.DataFrame(columns=["STT", "Ho_Ten", "Khoa_Phong", "Ngay_Nghi", "Mat_Khau", "Ngay_Dang_Ky"])
                
            # Đẩy ngược bảng sạch lên Google Sheets xóa hết dữ liệu tuần cũ
            conn.update(worksheet="Sheet1", data=df_tuan_nay)
            return df_tuan_nay

        df = df.drop(columns=['Ngay_Dang_Ky_DT'])
        
    return df

# Tải dữ liệu từ Google Sheets về ứng dụng
df_list = load_and_sync_data()

# --- GIAO DIỆN CHÍNH ---
tab1, tab2 = st.tabs(["✍️ Đăng Ký Nghỉ Phép", "❌ Hủy Lịch Nghỉ"])

# ==============================================================================
# TAB 1: ĐĂNG KÝ NGHỈ PHÉP
# ==============================================================================
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
                # Tạo định dạng chuỗi dữ liệu mới
                stt_moi = len(df_list) + 1
                ngay_nghi_str = ngay_nghi.strftime("%d/%m/%Y")
                ngay_tao_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                new_row = pd.DataFrame([{
                    "STT": stt_moi,
                    "Ho_Ten": ho_ten,
                    "Khoa_Phong": khoa_phong,
                    "Ngay_Nghi": ngay_nghi_str,
                    "Mat_Khau": mat_khau,
                    "Ngay_Dang_Ky": ngay_tao_str
                }])
                
                # Gom dữ liệu cũ và mới rồi update thẳng lên Google Sheets
                df_updated = pd.concat([df_list, new_row], ignore_index=True)
                conn.update(worksheet="Sheet1", data=df_updated)
                
                st.success(f"🎉 Chúc mừng {ho_ten} đã đăng ký nghỉ phép thành công!")
                st.rerun()

# ==============================================================================
# TAB 2: HỦY ĐĂNG KÝ (ĐỔI Ý KHÔNG NGHỈ NỮA)
# ==============================================================================
with tab2:
    st.subheader("Xóa lịch đăng ký nghỉ phép")
    
    if df_list.empty:
        st.info("Hiện chưa có ai đăng ký nghỉ phép trong tuần này.")
    else:
        # Tạo danh sách text trực quan cho người dùng lựa chọn đúng tên mình
        danh_sach_chon = []
        for idx, row in df_list.iterrows():
            danh_sach_chon.append(f"STT {int(row['STT'])} - {row['Ho_Ten']} ({row['Khoa_Phong']} - Ngày {row['Ngay_Nghi']})")
            
        lua_chon_xoa = st.selectbox("Chọn dòng muốn hủy bỏ:", options=danh_sach_chon)
        mat_khau_nhap = st.text_input("Nhập mật khẩu chỉnh sửa của bạn để xác nhận xóa:", type="password").strip()
        
        btn_xoa = st.button("Xác Nhận Hủy Lịch Nghỉ", type="primary")
        
        if btn_xoa:
            # Tách chuỗi để lấy số STT chính xác
            stt_can_xoa = int(lua_chon_xoa.split(" ")[1])
            
            # Lấy mật khẩu đúng của dòng đó ra so khớp
            mat_khau_dung = str(df_list.loc[df_list['STT'] == stt_can_xoa, 'Mat_Khau'].values[0])
            
            if mat_khau_nhap == mat_khau_dung:
                # Loại bỏ dòng dữ liệu đó ra khỏi Dataframe
                df_list = df_list[df_list['STT'] != stt_can_xoa]
                
                # Đánh lại số thứ tự STT từ 1
                if not df_list.empty:
                    df_list['STT'] = range(1, len(df_list) + 1)
                
                # Đẩy đè file dữ liệu đã lọc sạch lên Google Sheets để xóa dòng
                conn.update(worksheet="Sheet1", data=df_list)
                st.success("✅ Đã hủy lịch nghỉ phép thành công!")
                st.rerun()
            else:
                st.error("❌ Mật khẩu chỉnh sửa không chính xác! Vui lòng kiểm tra lại.")

# --- KHU VỰC HIỂN THỊ BẢNG TỔNG HỢP NỘI BỘ ---
st.markdown("---")
st.subheader("📊 Bảng Tổng Hợp Nghỉ Phép Trong Tuần")
st.caption("ℹ️ Bảng hiển thị công khai nội bộ (Đã ẩn mật khẩu bảo mật). Tự động dọn dẹp vào 00:00 Thứ 2 hàng tuần.")

if not df_list.empty:
    # Đổi tên cột sang tiếng Việt có dấu khi hiển thị lên giao diện cho đẹp
    df_hien_thi = df_list.copy()
    df_hien_thi = df_hien_thi.rename(columns={
        "Ho_Ten": "Họ và Tên",
        "Khoa_Phong": "Khoa/Phòng",
        "Ngay_Nghi": "Ngày nghỉ phép"
    })
    
    # Chỉ trích xuất hiển thị các cột thông tin cần thiết, giấu cột mật khẩu đi
    st.dataframe(
        df_hien_thi[["STT", "Họ và Tên", "Khoa/Phòng", "Ngày nghỉ phép"]], 
        use_container_width=True, 
        hide_index=True
    )
else:
    st.info("Hiện tại chưa có ai đăng ký nghỉ phép trong tuần này.")