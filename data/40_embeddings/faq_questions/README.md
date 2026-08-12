# Embedding câu hỏi FAQ

Embedding câu hỏi FAQ đã chuẩn hóa hoặc publish để phát hiện trùng nghĩa và tìm kiếm FAQ. Giữ `faq_id` hoặc `question_id` trong metadata. Không embedding suggestion bị từ chối hoặc chưa duyệt vào index FAQ chính thức.

Luồng trả lời chỉ match với FAQ đã `approved/published`. Dùng top-1 threshold và top-1/top-2 margin để tránh chọn nhầm hai FAQ gần nghĩa; cấu hình model hiện tại mặc định lần lượt là `0.86` và `0.035`.

Câu hỏi member chưa có FAQ được embedding trong index suggestion riêng để gom nhóm gửi Admin, không được dùng làm câu trả lời.
