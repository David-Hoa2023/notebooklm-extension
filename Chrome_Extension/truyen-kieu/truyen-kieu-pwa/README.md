# Bội Kiều PWA

Progressive Web App (PWA) version của ứng dụng Bội Kiều - xem câu thơ Truyện Kiều ngẫu nhiên trên điện thoại Android.

## 📱 Tính năng PWA

- **Cài đặt như ứng dụng native**: Có thể cài đặt trực tiếp từ trình duyệt
- **Hoạt động offline**: Sử dụng câu thơ mặc định khi không có mạng
- **Thông báo push**: Nhận câu thơ định kỳ qua thông báo
- **Thiết kế responsive**: Tối ưu cho màn hình điện thoại
- **Hiệu ứng rung**: Hỗ trợ vibration API trên mobile

## 🚀 Cách cài đặt trên Android

### Phương pháp 1: Trực tiếp từ web
1. Mở Chrome trên điện thoại Android
2. Truy cập vào địa chỉ web hosting PWA này
3. Nhấn vào banner "Cài đặt ứng dụng Bội Kiều" xuất hiện ở đầu trang
4. Chọn "Cài đặt" để thêm vào màn hình chính

### Phương pháp 2: Từ menu Chrome
1. Mở PWA trong Chrome
2. Nhấn vào menu 3 chấm (⋮) góc trên phải
3. Chọn "Thêm vào Màn hình chính" hoặc "Cài đặt ứng dụng"
4. Xác nhận cài đặt

## 🌐 Hosting PWA

Để PWA hoạt động, bạn cần host các file trên một web server hỗ trợ HTTPS. Một số tùy chọn miễn phí:

### GitHub Pages
1. Upload folder `truyen-kieu-pwa` lên GitHub repository
2. Bật GitHub Pages trong Settings
3. Truy cập qua URL: `https://username.github.io/repo-name/truyen-kieu-pwa/`

### Netlify
1. Kéo thả folder `truyen-kieu-pwa` vào netlify.com
2. Nhận URL miễn phí ngay lập tức

### Vercel
1. Import project từ GitHub hoặc upload trực tiếp
2. Tự động deploy với URL miễn phí

## 📁 Cấu trúc PWA

```
truyen-kieu-pwa/
├── index.html          # Giao diện chính responsive
├── app.js              # Logic ứng dụng PWA
├── service-worker.js   # Service worker cho offline & notifications
├── manifest.json       # PWA manifest configuration
├── create_icons.py     # Script tạo icon
├── icons/              # App icons các kích cỡ
│   ├── icon-72.png
│   ├── icon-96.png
│   ├── icon-128.png
│   ├── icon-144.png
│   ├── icon-152.png
│   ├── icon-192.png
│   ├── icon-384.png
│   └── icon-512.png
└── README.md
```

## 🎯 Sử dụng

1. **Nhập nguồn thơ**: Dán URL Google Doc đã chia sẻ
2. **Xem bói**: Nhấn "Bói Kiều" để xem câu thơ ngẫu nhiên
3. **Sao chép**: Nhấn "Sao chép" để copy câu thơ
4. **Thông báo**: Bật toggle để nhận thông báo định kỳ
5. **Cài đặt**: Chọn tần suất thông báo (15, 30, 60 phút hoặc 2 giờ)

## 🔧 Tính năng kỹ thuật

- **Service Worker**: Cache offline, background sync
- **Push Notifications**: Thông báo định kỳ với câu thơ
- **Web App Manifest**: Cấu hình PWA chuẩn
- **Responsive Design**: Tối ưu cho mobile
- **Local Storage**: Lưu cài đặt người dùng
- **Vibration API**: Phản hồi xúc giác
- **Clipboard API**: Sao chép câu thơ

## 📱 Yêu cầu hệ thống

- Android 5.0+ với Chrome 67+
- iOS 11.3+ với Safari (hỗ trợ hạn chế)
- Kết nối mạng để tải câu thơ từ Google Docs
- Hoạt động offline với câu thơ mặc định

## 🎨 Thiết kế

- Theme màu tím gradient theo phong cách retro
- Hiệu ứng neon và chrome metallic
- Animation bars giống Winamp
- Font Roboto tối ưu cho mobile
- Touch-friendly button sizing

## 🔄 Cập nhật

PWA tự động kiểm tra và cập nhật khi có phiên bản mới. Service worker sẽ tải xuống và cài đặt bản cập nhật trong background.