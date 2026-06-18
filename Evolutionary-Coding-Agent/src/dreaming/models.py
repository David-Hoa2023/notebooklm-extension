from pydantic import BaseModel, Field

class DreamInsight(BaseModel):
    content: str = Field(..., description="Nội dung bài học kinh nghiệm viết bằng tiếng Việt")
    importance: float = Field(..., description="Độ quan trọng từ 1.0 đến 10.0")
    evidence_task_ids: list[str] = Field(..., description="Danh sách mã bài tập làm minh chứng cho bài học này")
    scope: str = Field(..., description="Phạm vi áp dụng: 'global', 'session', hoặc 'task'")
    domain: str = Field(..., description="Domain chủ đề (ví dụ: regex, smtp, math...)")
    confidence: float = Field(..., description="Độ tự tin/tin cậy từ 0.0 đến 1.0")
    vertical: str = Field(default="generic", description="Business vertical chủ đề (sales, marketing, finance, generic)")

class DreamResult(BaseModel):
    session_summary: str = Field(..., description="Tóm tắt kết quả của phiên làm việc viết bằng tiếng Việt")
    insights: list[DreamInsight] = Field(..., description="Danh sách các bài học kinh nghiệm thu hoạch được")
    noise_discarded_summary: str = Field(..., description="Tóm tắt các thông tin nhiễu, lỗi hoặc trùng lặp bị loại bỏ")
