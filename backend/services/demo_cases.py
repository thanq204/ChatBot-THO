from backend.models.moderation import MemberSubmission

DEMO_CASES = [
    MemberSubmission(user_id="U001", text="Cảm ơn mọi người đã hỗ trợ mình hoàn thành bài.", channel="general"),
    MemberSubmission(user_id="U002", text="Cho mình hỏi buổi họp ngày mai bắt đầu lúc mấy giờ?", channel="general"),
    MemberSubmission(user_id="U003", text="Bấm vào link này để nhận tiền miễn phí, chỉ còn 5 phút.", channel="general"),
    MemberSubmission(user_id="U004", text="Mày ngu thế thì nghỉ khỏi nhóm đi.", channel="general"),
    MemberSubmission(
        user_id="U005", text="Làm ăn kiểu này thì nghỉ luôn đi.", channel="project",
        recent_context=["Bạn gửi lại file giúp mình nhé."],
    ),
    MemberSubmission(
        user_id="U006", text="Ra đường gặp tao là biết.", channel="gaming",
        recent_context=["Bọn mình đang đùa với nhau về trận game tối qua."],
    ),
]
