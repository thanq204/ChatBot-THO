# 📝 Git Commit Convention (Quy tắc Commit Code)

Tài liệu này quy định chuẩn mực viết **Commit Message** và **Đặt tên Branch** cho dự án. Việc tuân thủ quy tắc giúp lịch sử Git sạch sẽ, dễ tra cứu lỗi, tự động tạo Changelog và phối hợp nhóm hiệu quả. Dự án áp dụng chuẩn **[Conventional Commits 1.0.0](https://www.conventionalcommits.org/)**.

---

## 📌 1. Cấu trúc chuẩn của một Commit Message

Một Commit Message chuẩn gồm có 3 phần:

```text
<type>(<scope>): <summary ngắn gọn>

[Nội dung chi tiết - Optional Body]

[Thông tin thêm / Breaking Changes - Optional Footer]
```

- **Header**: Bắt buộc. Không quá **50 - 72 ký tự**.
- **Body**: Tùy chọn. Giải thích chi tiết **TẠI SAO** làm thay đổi này (nếu header chưa đủ rõ).
- **Footer**: Tùy chọn. Dùng cho **BREAKING CHANGE** hoặc gắn mã Issue / PR (ví dụ: `Closes #12`).

---

## 🏷️ 2. Các Loại Commit (`<type>`)

| Type | Ý nghĩa | Khi nào sử dụng? | Ví dụ |
| :--- | :--- | :--- | :--- |
| `feat` | Tính năng mới (Feature) | Thêm một chức năng / module mới cho ứng dụng | `feat(backend): add streaming support for chat endpoint` |
| `fix` | Sửa lỗi (Bug Fix) | Sửa một lỗi / bug trong code | `fix(frontend): resolve missing user avatar on reload` |
| `docs` | Tài liệu (Documentation) | Cập nhật file README, tài liệu API, comment | `docs(readme): update quickstart installation guide` |
| `style` | Định dạng code | Format code, sửa khoảng trắng, thiếu dấu chấm phẩy (không ảnh hưởng logic) | `style(agent): format python code using ruff` |
| `refactor` | Tái cấu trúc code | Sửa đổi code cấu trúc lại tốt hơn mà KHÔNG thêm feature hay fix bug | `refactor(eval): simplify metric evaluation pipeline` |
| `perf` | Tăng hiệu năng | Cải thiện tốc độ, tối ưu truy vấn DB, bộ nhớ | `perf(backend): cache embedding responses` |
| `test` | Kiểm thử | Thêm mới hoặc sửa đổi unit test, integration test | `test(agent): add test cases for fallback routing` |
| `chore` | Công việc phụ | Cập nhật file config, dependencies, script hỗ trợ build | `chore(deps): update langchain package to 0.2.0` |
| `ci` | CI/CD Pipeline | Cập nhật GitHub Actions, Docker script, deployment config | `ci(docker): update multi-stage docker build` |
| `revert` | Revert commit | Revert lại một commit hỏng trước đó | `revert: feat(api): add v2 streaming API` |

---

## 🎯 3. Phạm vi ảnh hưởng (`<scope>`)

Scope giúp xác định vị trí/module mà commit đó tác động đến. Một số scope gợi ý cho dự án:

- `backend` / `api`
- `frontend` / `ui`
- `agent` / `graph`
- `eval`
- `docker` / `config`
- `deps`

*Ví dụ:* `feat(agent): implement multi-turn conversation memory`

---

## ✍️ 4. Quy tắc viết tiêu đề (`<summary>`)

1. **Sử dụng thì hiện tại / mệnh lệnh (Imperative mood)**:
   - ✅ `add user auth` (Thêm xác thực người dùng)
   - ❌ `added user auth` hoặc `adding user auth`
2. **Chữ cái đầu viết thường** (hoặc đồng nhất trong team).
3. **Không dấu chấm ở cuối câu** header:
   - ✅ `fix(api): fix null pointer crash`
   - ❌ `fix(api): fix null pointer crash.`
4. **Viết ngắn gọn, súc tích**, tập trung vào bản chất công việc.
5. **Khuyến khích dùng tiếng Anh** (hoặc tiếng Việt có dấu đồng nhất trong toàn bộ commit log của dự án).

---

## ⚠️ 5. Xử lý Breaking Changes

Nếu thay đổi gây ra **Breaking Change** (làm ngắt kết nối hoặc không tương thích ngược với API/code cũ):

1. Thêm dấu `!` sau `<type>(<scope>)`.
2. Ghi chú rõ `BREAKING CHANGE:` ở phần Footer.

**Ví dụ:**

```text
feat(api)!: change response payload structure for /v1/chat

BREAKING CHANGE: Field `response_text` is renamed to `content` to align with OpenAI specification.
```

---

## 🌿 6. Quy tắc đặt tên Branch (Git Branch Naming)

Tên branch nên tuân theo định dạng: `<type>/<tên-mô-tả-ngắn-gọn>`

- **Feature mới**: `feature/add-agent-memory` hoặc `feat/chat-ui`
- **Sửa lỗi**: `bugfix/fix-token-overflow` hoặc `hotfix/cors-error`
- **Refactor**: `refactor/langgraph-state`
- **Tài liệu**: `docs/update-architecture-diagram`
- **Thử nghiệm**: `experiment/rag-hybrid-search`

---

## 🚫 7. Những commit KHÔNG ĐẠT (Bad Practices)

| Commit Message dở | Tại sao không đạt? | Cách sửa đúng chuẩn |
| :--- | :--- | :--- |
| `fix bug` | Không rõ bug gì, ở module nào | `fix(backend): fix cors policy header for local frontend` |
| `update code` | Quá chung chung, không có ý nghĩa | `refactor(agent): restructure state transition handlers` |
| `WIP` / `test` | Thiếu ngữ cảnh công việc | `test(eval): add benchmark test for retrieval accuracy` |
| `fixed things and updated readme and updated dependencies` | Gom quá nhiều thay đổi vào 1 commit | Tách thành 3 commit riêng biệt: `fix(...)`, `docs(...)`, `chore(...)` |

---

## ✅ 8. Checklist trước khi Commit & Push

- [ ] Code đã chạy thử local thành công, không bị syntax error / broken build.
- [ ] Đã chạy linter / formatter (ví dụ: `ruff check`, `black`, `eslint`...).
- [ ] Không vô tình commit các file nhạy cảm (`.env`, secret keys, credentials).
- [ ] Mỗi commit đại diện cho **1 đơn vị công việc hoàn chỉnh** (Atomic Commit).
- [ ] Commit message tuân thủ theo đúng chuẩn trên.
