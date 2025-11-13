# 🌸 Bội Kiều PWA - Truyện Kiều Progressive Web App

[![Vietnamese Literature](https://img.shields.io/badge/Literature-Vietnamese-red.svg)](https://vi.wikipedia.org/wiki/Truy%E1%BB%87n_Ki%E1%BB%81u)
[![PWA](https://img.shields.io/badge/PWA-Progressive%20Web%20App-blue.svg)](https://web.dev/progressive-web-apps/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Bội Kiều** là ứng dụng web tiến bộ (PWA) hiển thị các câu thơ ngẫu nhiên từ tác phẩm "Truyện Kiều" của Nguyễn Du, với tính năng thông báo định kỳ và giao diện retro tuyệt đẹp.

## ✨ Tính năng

- 🔮 **Bói Kiều**: Xem câu thơ ngẫu nhiên với hiệu ứng mystical
- 📱 **PWA**: Cài đặt như ứng dụng native trên điện thoại
- 🔔 **Thông báo định kỳ**: Nhận câu thơ theo khoảng thời gian tùy chọn
- 📚 **Tùy chỉnh nguồn**: Kết nối Google Docs cho bộ sưu tập thơ riêng
- 🎵 **Giao diện Retro**: Thiết kế winamp-inspired với hiệu ứng neon
- 📴 **Hoạt động offline**: Sử dụng được khi không có mạng
- 📋 **Sao chép dễ dàng**: Copy câu thơ yêu thích
- 💫 **Hiệu ứng animat**: Visualizer bars và chrome shine effects

## 🚀 Demo

Truy cập: [https://david-hoa2023.github.io/boi-Kieu-PWA/](https://david-hoa2023.github.io/boi-Kieu-PWA/)

## 📱 Cài đặt

### Trên điện thoại (Android/iOS)
1. Mở trình duyệt và truy cập link demo
2. Chọn "Thêm vào màn hình chính" hoặc banner cài đặt
3. Ứng dụng sẽ hoạt động như app native

### Trên máy tính
1. Mở Chrome/Edge và truy cập link demo
2. Nhấp vào biểu tượng cài đặt trong thanh địa chỉ
3. Chọn "Cài đặt"

## 🛠️ Chạy cục bộ

### Yêu cầu
- Python 3.x (để chạy server test)
- Trình duyệt hiện đại hỗ trợ PWA

### Cách chạy
```bash
# Clone repository
git clone https://github.com/David-Hoa2023/boi-Kieu-PWA.git
cd boi-Kieu-PWA

# Chạy server test
python serve.py

# Truy cập http://localhost:8443
```

### Test trên điện thoại (cùng mạng WiFi)
```bash
# Tìm địa chỉ IP máy tính
ipconfig  # Windows
ifconfig  # macOS/Linux

# Truy cập từ điện thoại: http://[IP]:8443
```

## 📂 Cấu trúc dự án

```
boi-kieu-pwa/
├── index.html          # Giao diện chính
├── app.js             # Logic ứng dụng
├── service-worker.js   # Service worker cho PWA
├── manifest.json      # PWA manifest
├── serve.py          # Server test cục bộ
├── icons/            # Icons cho PWA
│   ├── icon-72.png
│   ├── icon-96.png
│   ├── icon-128.png
│   ├── icon-144.png
│   ├── icon-152.png
│   ├── icon-192.png
│   ├── icon-384.png
│   └── icon-512.png
└── README.md         # Tài liệu này
```

## 🎨 Tính năng kỹ thuật

### PWA Features
- ✅ Service Worker cho caching và offline
- ✅ Web App Manifest
- ✅ Responsive design
- ✅ Add to homescreen
- ✅ Push notifications
- ✅ Background sync

### UI/UX Features
- 🎵 Animated visualizer bars
- 💎 Chrome-style panel với shine effects
- 🌈 Neon text effects
- 📱 Mobile-first responsive design
- 🔮 Mystical reveal animations
- ⚡ Vibration feedback (mobile)

## 🔧 Tùy chỉnh

### Thêm Google Docs riêng
1. Tạo Google Docs mới với các câu thơ (mỗi dòng một câu)
2. Chia sẻ công khai: "Anyone with the link can view"
3. Copy link và paste vào ứng dụng
4. Nhấn "Lưu nguồn thơ"

### Định dạng Google Docs
```
Trăm năm trong cõi người ta, Chữ tài chữ mệnh khéo là ghét nhau.
Trời xanh quen thói má hồng, Đánh phong cho bạc má hồng cho phai.
Cỏ non xanh tận chân trời, Cành lê trắng điểm một vài bông hoa.
...
```

## 📚 Về Truyện Kiều

"**Đoạn Trường Tân Thanh**" (thường gọi là Truyện Kiều) là tác phẩm văn học kinh điển của đại thi hào Nguyễn Du (1765-1820). Đây được coi là đỉnh cao của văn học Việt Nam và là báu vật văn hóa dân tộc.

### Giá trị văn học
- 📖 3.254 câu thơ lục bát
- 🎭 Phản ánh xã hội phfeudal Việt Nam
- 💝 Thể hiện lý tưởng nhân văn sâu sắc
- 🌟 Tác phẩm được UNESCO ghi nhận

## 🤝 Đóng góp

Mọi đóng góp đều được chào đón! Để đóng góp:

1. Fork repository
2. Tạo feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Mở Pull Request

## 📄 License

Dự án này được phân phối dưới giấy phép MIT. Xem file [LICENSE](LICENSE) để biết thêm chi tiết.

## 🙏 Lời cảm ơn

- **Nguyễn Du** - Tác giả "Truyện Kiều"
- **Google Fonts** - Font Roboto
- **PWA Community** - Inspiration cho Progressive Web Apps

## 📧 Liên hệ

- **Author**: David Hoa
- **GitHub**: [@David-Hoa2023](https://github.com/David-Hoa2023)
- **Repository**: [boi-Kieu-PWA](https://github.com/David-Hoa2023/boi-Kieu-PWA)

---

*"Trăm năm trong cõi người ta, Chữ tài chữ mệnh khéo là ghét nhau."* - Nguyễn Du