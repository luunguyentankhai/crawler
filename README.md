# FUO Crawler

Tải ảnh câu hỏi theo mã môn từ fuoverflow.com, tải comment dưới ảnh, rồi chọn đáp án bằng bình chọn đa số.

## Cài đặt

Cần Python >= 3.11, [uv](https://docs.astral.sh/uv/) và trình duyệt Brave (hoặc Chromium khác).

```sh
uv sync
```

Tạo file `.env` ở thư mục gốc:

```
FUO_BASE_URL=https://fuoverflow.com
BROWSER_PATH=/usr/bin/brave   # tùy chọn, mặc định /usr/bin/brave
HEADLESS=1                    # tùy chọn, 0 = hiện cửa sổ trình duyệt
```

## Cách dùng

1. Đăng nhập Google một lần (mở cửa sổ Brave, đăng nhập xong thì đóng lại):

   ```sh
   uv run main.py login
   uv run main.py check     # kiểm tra phiên còn hiệu lực
   ```

   Phiên lưu ở `auth.json`. Hết hạn thì chạy `login` lại.

2. Chạy toàn bộ (ảnh → comment → đáp án):

   ```sh
   ./crawl.sh CSI106 PRF192        # các môn chỉ định
   ./crawl.sh                      # mọi môn trong subjects.txt (mỗi dòng một mã, # là ghi chú)
   ./crawl.sh CSI106 --limit 2     # tham số thêm chuyển cho `main.py crawl`
   ```

Hoặc chạy từng bước:

| Lệnh | Việc làm |
|---|---|
| `uv run main.py crawl CSI106 [--limit N]` | tải ảnh, tối đa N thread mỗi môn |
| `uv run main.py comments CSI106` | tải comment của ảnh (cần `meta.json` từ bước crawl) |
| `uv run main.py answers CSI106` | offline: chọn đáp án, ghi `answers.json` và `review.md` |
| `uv run main.py renumber [thư mục]` | đổi tên file cũ `<id>-tên` thành `Q1`, `Q2`, ... |

## Kết quả

Trong `images/<MÃ_MÔN>/`:

- `<thread>/Q1.webp, Q2.webp, ...`: ảnh câu hỏi
- `<thread>/comments.json`, `<thread>/answers.json`: comment và đáp án đã chọn (kèm votes, confidence)
- `review.md`: các câu cần kiểm tra tay (hòa phiếu, comment mâu thuẫn, không có đáp án)

Log mỗi lần chạy nằm ở `logs/`.

## Test

```sh
FUO_BASE_URL=https://fuoverflow.com uv run python test_fuo.py
```

Test chạy offline, không cần đăng nhập hay trình duyệt. CI (`.github/workflows/test.yml`) chạy cùng lệnh này cho mỗi push và pull request.
