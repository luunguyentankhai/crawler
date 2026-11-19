# FUO Crawler

Tải ảnh câu hỏi theo mã môn từ fuoverflow.com, tải comment dưới ảnh, rồi chọn đáp án bằng bình chọn đa số.

## Cài đặt

Cần Python >= 3.11, [uv](https://docs.astral.sh/uv/) và một trình duyệt nền Chromium (Brave, Chrome, Chromium hoặc Edge).
Code tự dò trình duyệt trên Linux, macOS và Windows; không tìm thấy thì đặt `BROWSER_PATH`.

```sh
uv sync
```

Tạo file `.env` ở thư mục gốc:

```sh
cp .env.example .env
```

### Tìm đường dẫn trình duyệt (`BROWSER_PATH`)

Báo không tìm thấy, hoặc chọn trình duyệt khác:

1. Mở trình duyệt, gõ vào thanh địa chỉ `chrome://version` (Brave: `brave://version`, Edge: `edge://version`).
2. Copy dòng **Executable Path** (tiếng Việt: Đường dẫn thực thi).
3. Dán vào `.env`, ví dụ `BROWSER_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe`.

Chỉ dùng được trình duyệt nền Chromium.

## Cách dùng

1. Đăng nhập Google một lần (mở trình duyệt, đăng nhập xong thì đóng lại):

   ```sh
   uv run main.py login
   uv run main.py check     # kiểm tra phiên còn hiệu lực
   ```

   Phiên lưu ở `auth.json`. Hết hạn thì chạy `login` lại.

2. Chạy toàn bộ (ảnh → comment → đáp án):

   ```sh
   uv run main.py all <mã môn 1> <mã môn 2>      # các môn chỉ định
   uv run main.py all                    # mọi môn trong subjects.txt (mỗi dòng một mã, # là ghi chú)
   uv run main.py all <mã môn> --limit 2   # tối đa 2 thread mỗi môn
   ```


