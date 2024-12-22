# Snake Game

Một trò chơi rắn săn mồi cổ điển được viết bằng Python và Pygame.

## Tính năng

- Điều khiển rắn bằng các phím mũi tên
- Hiển thị điểm số
- Game over khi đâm vào tường hoặc tự cắn vào thân
- Thức ăn xuất hiện ngẫu nhiên trên màn hình
- Giao diện đơn giản, dễ chơi

## Yêu cầu

- Python 3.x
- Pygame

## Cài đặt

1. Cài đặt Python từ [python.org](https://python.org)
2. Cài đặt Pygame:
```bash
pip install pygame
```

## Cách chơi

1. Chạy game:
```bash
python snake_game.py
```

2. Sử dụng:
- Phím mũi tên ⬆️: Di chuyển lên
- Phím mũi tên ⬇️: Di chuyển xuống  
- Phím mũi tên ⬅️: Di chuyển trái
- Phím mũi tên ➡️: Di chuyển phải

3. Luật chơi:
- Điều khiển rắn ăn thức ăn (ô màu đỏ)
- Tránh đâm vào tường hoặc thân rắn
- Điểm số tăng khi ăn được thức ăn
- Game kết thúc khi rắn đâm vào tường hoặc tự cắn vào thân

## Tùy chỉnh

Bạn có thể điều chỉnh các thông số trong code:
- Thay đổi kích thước cửa sổ: `WINDOW_WIDTH` và `WINDOW_HEIGHT`
- Điều chỉnh tốc độ game: `clock.tick(10)` 
- Thay đổi màu sắc: `WHITE`, `BLACK`, `RED`, `GREEN`

## Đóng góp

Mọi đóng góp đều được hoan nghênh. Hãy tạo pull request để cải thiện game.