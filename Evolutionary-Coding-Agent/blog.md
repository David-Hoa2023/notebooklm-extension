# Khi AI tự ra đề, tự làm bài, và tự kiểm tra: một buổi thí nghiệm với Evolutionary Coding Agent

*Bài viết dành cho độc giả không chuyên kỹ thuật — cập nhật bối cảnh tháng 6/2026*

---

## Bối cảnh: AI viết code không còn là chuyện xa

Năm 2026, rất nhiều công cụ AI có thể viết code theo yêu cầu. Bạn mô tả bài toán, vài phút sau nhận lại một đoạn chương trình — nghe có vẻ đủ dùng.

Nhưng nếu bạn là người thiết kế chương trình đào tạo, quản lý sản phẩm AI, hay đơn giản là người muốn **tin tưởng** vào một hệ thống tự học, câu hỏi lớn hơn luôn là:

- AI có **thực sự học** qua từng lần làm việc, hay mỗi lần đều bắt đầu từ con số không?
- Khi AI **tự nghĩ ra bài tập**, làm sao biết bài đó **công bằng, chấm được, an toàn**?
- Làm sao **đo lường** được tiến bộ — thay vì chỉ xem một demo may mắn?

Dự án **Evolutionary Coding Agent** (Agent lập trình tiến hóa) sinh ra để trả lời những câu hỏi đó. Không phải một chatbot viết code thêm một lần nữa, mà là một **vòng lặp học tập có kiểm chứng**: làm bài → lưu kinh nghiệm → kiểm tra lại → thử sức bài mới → báo cáo bằng số liệu.

---

## Nhân vật: Tiến sĩ Lin và câu hỏi của một người thiết kế chương trình học

Hãy tưởng tượng **Tiến sĩ Lin** — một nhà thiết kế chương trình đào tạo AI. Cô đặt **ba câu hỏi** liên tiếp:

> *Bộ nhớ có **thực sự cải thiện điểm số** không — hay chỉ là cảm giác “AI thông minh hơn”?* (§1 — đo bằng số)

> *Liệu agent có thể tự đề xuất bài luyện tập Python, tự làm, và làm sao để hệ thống **chặn** những bài tập “hỏng” trước khi tốn thời gian và tiền API?* (§3)

> *Và sau khi làm xong — agent có **ghi nhớ** điều gì hữu ích cho lần sau, hay mọi thứ biến mất như một cuộc chat thông thường?* (§2)

Đó chính là kịch bản **Dr. Lin** trong tài liệu dự án — gồm **bằng chứng đo lường** (*run-all*, PG/SG/GG), **khám phá an toàn** (*safe explore*, cổng oracle), và **học bền** (*durable skills*, ngân hàng kỹ năng):

1. Agent được phép **tự nghĩ bài** (không chỉ làm bài có sẵn).
2. Mỗi bài phải qua **cổng kiểm chất lượng** — *oracle gate* — giống biên tập viên duyệt đề thi.
3. Chỉ bài **đề hợp lệ** mới vào phòng thi ảo (*sandbox* Docker — cách ly, không ảnh hưởng máy thật).
4. Bài làm tốt → **skill** (đoạn code tái dùng) được kiểm tra lại trong sandbox rồi lưu vào ngân hàng.
5. Cuối cùng, hệ thống **làm lại bài cũ** (*regression*) để chắc việc học mới không phá việc cũ.

Kịch bản mô tả cả trường hợp xấu (đề kiểm tra sai → bị loại) lẫn trường hợp tốt (quá cổng, giải thành công, skill được lưu). Tháng 6/2026, nhóm dự án đã **chạy thật** cả pipeline đo lường (*run-all*, 6 seed) lẫn explore (*seed 42*) — kết quả dưới đây.

---

## Bộ nhớ có giúp không? — bằng số, không phải cảm giác (§1)

Trước khi hỏi “agent có tự ra đề được không”, Tiến sĩ Lin muốn biết: **khi được phép nhớ**, agent có làm bài **tốt hơn** so với lúc **không nhớ gì** không?

Cô chạy lệnh `python run.py run-all` — tương đương một **kỳ thi có kiểm soát** trên 6 “hạt giống” ngẫu nhiên khác nhau (seed 42–47), mỗi bài qua ba vòng:

| Vòng | Bộ nhớ | Câu hỏi |
|------|--------|---------|
| **Baseline** | Tắt — như agent mới tinh | Làm được bao nhiêu điểm **không** dựa vào kinh nghiệm cũ? |
| **First pass** | Bật — học và ghi skill | Bộ nhớ **giúp lúc đang học** không? |
| **Second pass** | Đóng băng — không học thêm | Điểm có **giữ vững** sau khi ngừng cập nhật bộ nhớ? |

Buổi chạy mới nhất kéo dài khoảng **4,5 giờ** và ghi **120 lượt** vào nhật ký `logs/trace.jsonl`.

### Ba con số chính (trung bình 6 seed)

| Chỉ số | Ý nghĩa đơn giản | Kết quả |
|--------|------------------|---------|
| **Plasticity Gain (PG)** | Có giúp **khi đang học** không? | **+0,125** — có, nhẹ |
| **Stability Gain (SG)** | Có **ổn định** sau khi đóng băng bộ nhớ? | **−0,042** — hơi tụt |
| **Generalization Gain (GG)** | Có **áp dụng** sang bài chưa thấy? | **+0,083** — khá tích cực |

**Đọc nhanh:** Bộ nhớ giúp một chút trong lúc học (đặc biệt bài toán biểu thức toán SUB_002: **+0,50** điểm). Nhưng sau khi đóng băng, một số bài (JSON, phân tích log) **hơi điểm thấp hơn** — chưa chứng minh được “học xong là mãi giỏi”.

### Giả thuyết thống kê — thẳng thắn

Dashboard còn hỏi hai giả thuyết đã đăng ký trước (H1, H2):

| Giả thuyết | Kết luận buổi chạy mới nhất |
|------------|----------------------------|
| **H1** — điểm vòng đóng băng cao hơn vòng không nhớ | **Không đạt** (p ≈ 0,90); trung bình thậm chí **thấp hơn** một chút — một phần do bài **negative transfer** (mẹo regex cũ làm hỏng bài gửi email) |
| **H2** — điểm ổn định sau đóng băng | **Không đạt** ý nghĩa thống kê (p ≈ 0,73) |

Điều này **không** có nghĩa dự án thất bại. Ngược lại: hệ thống **nói thật** — “có tín hiệu tích cực khi học, chưa đủ bằng chứng để quảng cáo”. Đó là chuẩn nghiên cứu, không phải demo marketing.

> **Kết luận §1:** Evolutionary Coding Agent không chỉ *cảm giác* như học. Nó **đo** PG/SG/GG trên nhiều seed, báo p-value, và chỉ ra cả **negative transfer** — bộ nhớ đôi khi **gây hại**. Tiến sĩ Lin có số liệu để quyết định bước tiếp: thêm seed, sửa trích xuất skill, hay siết curriculum.

---

## Chuyện gì đã xảy ra trong buổi chạy thật?

Trong khoảng **27 phút**, với *seed 42* (cùng “hạt giống” ngẫu nhiên để có thể lặp lại thí nghiệm), agent đã:

| Hạng mục | Kết quả (lần chạy mới nhất) |
|----------|------------------------------|
| Số bài tự nghĩ ra | **4** |
| Bài bị loại ở cổng kiểm chất lượng | **0** (happy path — mọi đề kiểm tra hợp lệ) |
| Bài giải thành công trong sandbox | **4/4** (điểm 10, 9,5, 10, 10) |
| Bài cũ làm lại (regression) | **2/2 đạt** (9,5 và 9,5) |
| Skill trong ngân hàng | **42** tổng, **27** đang active (*retrievable*) |
| Phủ sóng năng lực đã xác minh | **100%** (10/10) |

Không phải lúc nào cũng “mượt” như vậy. Trên toàn dự án, khoảng **75%** đề kiểm tra tự sinh được duyệt trong các lần explore trước; **25%** bị loại — ví dụ dùng công cụ không có trong môi trường thi, hoặc kiểm tra nhầm tên hàm. **Điểm nổi bật** không phải “AI luôn đúng”, mà là **có lớp bảo vệ** trước khi agent lao vào giải bài hỏng.

---

## Học có bền không? — câu hỏi thứ hai của Tiến sĩ Lin

Chatbot thông thường: hỏi xong, trả lời xong, **quên sạch**. Evolutionary Coding Agent khác: mỗi bài làm tốt có thể sinh ra **skill** — mẩu code nhỏ đã được **chạy thử lại** trong sandbox trước khi lưu vào `data/memory/memory.db`.

**Sau buổi explore mới nhất, điều gì được lưu lại?**

| Loại | Ví dụ | Ý nghĩa |
|------|-------|---------|
| Skill doanh số / tồn kho | `_calculate_record_revenue`, `_update_product_summary` | Tính doanh thu, cập nhật tổng theo sản phẩm |
| Skill chuẩn hóa dữ liệu | `normalize_profile_name`, `filter_profile_by_last_login` | Làm sạch hồ sơ người dùng (bài mới so với lần chạy trước) |
| Skill **không** lưu (inactive) | Một số bản trích xuất bị lỗi định dạng | Hệ thống **từ chối** đưa vào ngân hàng — không làm ô nhiễm bộ nhớ |

**Regression — bài cũ có còn làm được không?**

Sau bốn bài mới, hệ thống tự chạy lại `SUB_001` (trích email) và `SUB_003` (kiểm JSON). Cả hai **đạt 9,5/10**. Việc học mới **không phá** bài cũ — đúng kỳ vọng của một hệ thống học có kiểm soát.

**Thẳng thắn:** một số lần trích skill sau regression vẫn **thất bại kiểm tra** (lỗi định dạng code khi lưu). Bài chính vẫn pass; chỉ bước “ghi chú cho lần sau” bị hỏng. Đây là hạng mục cần cải thiện — nhưng cơ chế “chỉ skill verified mới active” đã **chặn** skill hỏng khỏi retrieval.

> **Kết luận §2:** Explore không chỉ “tự ra đề an toàn”. Khi consolidation hoạt động, agent **gửi tiền vào ngân hàng kỹ năng** — và regression chứng minh bài cũ vẫn ổn. Đó là ranh giới giữa demo và **hệ thống học**.

---

## Bốn bài tập agent tự nghĩ ra — giải thích bằng ngôn ngữ đời thường

*(Lần chạy mới nhất, seed 42 — mã bài `EXP_*` thay đổi mỗi lần vì agent tự sinh đề mới.)*

Ba bài đầu vẫn xoay quanh **báo cáo kinh doanh** (Excel vào, tổng hợp ra). Bài thứ ba mở rộng sang **chuẩn hóa dữ liệu người dùng** — cho thấy agent không chỉ lặp một khuôn.

### Bài 1 — Tổng doanh số theo sản phẩm (điểm 10/10)

**Câu hỏi kinh doanh:** Mỗi mã sản phẩm bán được bao nhiêu và thu về bao nhiêu tiền?

Agent tách hàm phụ `calculate_item_revenue` — mẩu code sau được gộp vào skill `_calculate_record_revenue` trong ngân hàng.

### Bài 2 — “Sức khỏe” kho hàng (điểm 9,5/10)

**Câu hỏi kinh doanh:** Tổng giá trị tồn kho? Sản phẩm nào sắp hết?

Dữ liệu thiếu hoặc sai được xử lý nhẹ (coi như 0), giống dashboard quản lý kho cuối ngày.

### Bài 3 — Chuẩn hóa hồ sơ người dùng (điểm 10/10) *(chủ đề mới)*

**Câu hỏi:** Cho danh sách hồ sơ lộn xộn — tên, email, tag, ngày đăng nhập — hãy làm sạch và lọc theo quy tắc.

Skill lưu lại gồm `normalize_profile_name`, `normalize_profile_email`, `filter_profile_by_last_login`… — minh chứng agent **mở rộng** sang bài không trùng ba lần chạy trước.

### Bài 4 — Báo cáo bán hàng chi tiết (điểm 10/10)

Tổng hợp theo mã sản phẩm khi mỗi dòng có thêm tên và ngày bán. Skill `_update_product_summary` được lưu sau khi verify.

---

## Đọc dashboard trong 2 phút

Sau buổi chạy, Tiến sĩ Lin mở file `logs/dashboard.html` trên trình duyệt. Phần **Phase 5: kết quả active exploration** trả lời ba câu hỏi: agent đã biết đủ “môn học” chưa, bài tự ra có an toàn không, và agent có làm được bài tự nghĩ ra không.

### Hàng trên — bốn con số cần nhớ

| Chỉ số | Ý nghĩa đơn giản | Kết quả buổi chạy seed 42 |
|--------|------------------|---------------------------|
| **Keyword (taxonomy) coverage** | Agent *có vẻ* biết bao nhiêu chủ đề, dựa trên từ khóa trong code (cách đo lỏng hơn) | **100%** — 10/10 năng lực |
| **Skill-backed coverage** | Agent *thực sự* chứng minh được bao nhiêu chủ đề bằng skill đã kiểm tra trong sandbox (cách đo chặt hơn) | **100%** — 10/10 đã xác minh |
| **Oracle validation rate** | Tỷ lệ đề kiểm tra tự sinh được duyệt *trước* khi agent làm bài | **100%** — 4 validated, 0 rejected |
| **Self-proposed task success** | Tỷ lệ bài tự nghĩ ra mà agent giải thành công | **100%** — 4/4 passed |

Hai cột coverage tách **“trông có vẻ biết”** (trái) và **“chứng minh được là biết”** (phải). Dự án tin cột phải hơn — khó “ảo” hơn.

Lưu ý: buổi seed 42 là **happy path** (mọi thứ 100%). Các lần chạy khác có thể thấy oracle rejected > 0 — đó là dấu hiệu **cổng bảo vệ hoạt động**, không phải lỗi hệ thống.

### Biểu đồ trái — độ “mới lạ” của bài tự đề xuất

**Novelty score** đo bài agent tự nghĩ *mới đến mức nào* (0 = quen, 1 = rất mới):

| Bài | Mã (lần chạy đầu) | Novelty (xấp xỉ) |
|-----|-------------------|------------------|
| Task 1 | EXP_B1C875E8 | ~0,28 |
| Task 2 | EXP_7DD3B295 | ~0,23 |
| Task 3 | EXP_BA5187E5 | ~0,21 |
| Task 4 | EXP_1D47D63C | ~0,19 |

*(Lần chạy mới nhất: EXP_9A645CAC → EXP_901F40A2 — novelty tương tự, đi xuống dần khi agent khai thác cùng vùng chủ đề.)*

Đường đi xuống dần — bài sau hơi ít “mới” hơn vì cả bốn đều cùng chủ đề tổng hợp doanh số/tồn kho. Novelty **không phải điểm thi**; nó chỉ cho biết agent đang khám phá xa hay lặp biến thể quen thuộc.

### Bảng phải — bản đồ 10 năng lực

Hệ thống chia kỹ năng lập trình thành **10 nhóm**: thuật toán, cấu trúc dữ liệu, ngày giờ, xử lý lỗi, file, JSON, biểu thức toán, regex, chuỗi, và kiểm thử.

Hai cột song song:

- **Từ khóa** — coi là “đã phủ” nếu thấy dấu hiệu trong tên hàm hoặc mô tả.
- **Thực tế (verified skill-backed)** — chỉ tính khi có skill **active, đã chạy thử thành công** trong sandbox.

Dòng cuối **“Không còn khoảng trống (100% verified)!”** nghĩa là không còn lỗ hổng trong bản đồ năng lực. Con số này phản ánh **bộ nhớ skill tích lũy của cả dự án**, không chỉ riêng bốn bài seed 42 — nhưng buổi explore vừa rồi là minh chứng trực quan rằng vòng lặp vẫn hoạt động tốt.

### Bốn câu hỏi — bốn câu trả lời

1. **Agent đủ “môn học” chưa?** → Skill-backed coverage **100%**.
2. **Bài tự ra có an toàn, chấm được không?** → Oracle validation **100%** (lần chạy mới nhất: 0 rejected).
3. **Agent làm được bài tự nghĩ ra không?** → Self-proposed success **4/4**.
4. **Có gì được lưu cho lần sau?** → **27 skill active**, regression **2/2** — học có bền, không chỉ one-shot.

Dashboard còn nhiều phần khác (điểm từng bài, giả thuyết thống kê H1/H2, chi phí token…) — nhưng **khu vực Phase 5** trên là nơi Tiến sĩ Lin nhìn đầu tiên để đánh giá buổi thí nghiệm khám phá an toàn.

---

## Tại sao dự án này khác — và đáng chú ý?

Giữa vô số demo AI viết code, **Evolutionary Coding Agent** nổi bật ở năm điểm có thể giải thích mà không cần đọc source code:

### 1. Học có bằng chứng, không chỉ cảm giác

Nhiều sản phẩm nói “AI ngày càng thông minh”. Dự án này **đo** trên 6 seed và ~4,5 giờ chạy thật:

- Agent làm tốt hơn khi **được nhớ** kinh nghiệm cũ không? → PG **+0,125** (có, nhưng chưa chứng minh thống kê)
- Khi **đóng băng** bộ nhớ, agent có **ổn định** không? → SG **−0,042** (hơi tụt trên trung bình)
- Agent có **áp dụng** được sang bài chưa thấy không? → GG **+0,083**

Kết quả hiển thị trên **dashboard HTML** — biểu đồ, p-value, từng bài một. Đó là tư duy **khoa học** hơn marketing.

### 2. Tự ra đề — nhưng có “biên tập viên” ảo

Agent không chỉ giải bài; nó **đề xuất bài mới**. Rủi ro lớn nhất là đề tự sinh **không chấm được** hoặc **chấm sai**.

Dự án giải quyết bằng **cổng oracle**:

- Cấm đề kiểm tra phụ thuộc công cụ không có trong phòng thi.
- Bắt buộc đề kiểm tra đúng **tên hàm** trong đề bài.
- Chạy thử với “đáp án cố ý sai” — nếu vẫn pass thì đề **vô dụng**, bị loại.

Đây là ý tưởng **an toàn trước, tốn tiền sau** — bài hỏng bị loại sớm, không kéo agent vào vòng sửa lỗi vô ích.

### 3. Kỹ năng lưu lại phải được **xác minh**

Không phải mọi đoạn code agent viết đều được tin. Chỉ những **skill** (đoạn tiện ích tái sử dụng) **vượt qua kiểm tra trong sandbox** mới được đánh dấu *active* và dùng cho bài sau.

Tính đến tháng 6/2026, hệ thống đạt **100% phủ sóng năng lực đã xác minh** trên 10 nhóm kỹ năng (từ xử lý chuỗi, JSON, regex đến kiểm thử). Không phải “đoán có kỹ năng” bằng từ khóa — mà **chứng minh bằng code chạy được**.

### 4. Phòng thủ trước trí nhớ “độc hại”

AI có thể học **sai** — ví dụ ghi nhớ quy tắc vô lý (“luôn trả về chuỗi rỗng”) hoặc áp dụng kinh nghiệm sai ngữ cảnh (mẹo regex vào bài gửi email).

Dự án xây nhiều lớp bảo vệ: phát hiện mâu thuẫn, **cách ly** insight độc hại, lọc khi làm bài nhạy cảm. Trong thế giới agent tự học lâu dài, **độ tin cậy của bộ nhớ** quan trọng ngang độ thông minh của model.

### 5. Minh bạch và lặp lại được

Mỗi lần chạy ghi **nhật ký trace** (`logs/trace.jsonl`): đề xuất gì, loại vì sao, điểm bao nhiêu, mất bao lâu. Dùng **seed** cố định để tái hiện thí nghiệm. Đây là chuẩn mà giới nghiên cứu cần — và cũng là điều doanh nghiệp cần khi muốn **audit** hệ thống AI.

---

## Bài học từ buổi thí nghiệm Dr. Lin

**Cho người không viết code**, câu chuyện rút gọn như sau:

> Chúng ta không chỉ hỏi AI “viết giúp tôi một hàm”. Chúng ta xây một **giáo viên ảo** biết tự ra bài, tự chấm, **lưu skill đã kiểm chứng**, tự làm lại bài cũ — và quan trọng nhất: **có cơ chế từ chối bài hỏng trước khi thi**.

Hai lần chạy seed 42 đều **lạc quan** (4/4 pass, regression đạt). Lần mới nhất còn cho thấy **ngân hàng skill phình ra** (24 → 27 active) và agent **thử chủ đề mới** (chuẩn hóa hồ sơ). Thiết kế hệ thống **không phụ thuộc may mắn** — các lần explore khác vẫn có thể thấy oracle rejected, và skill trích xuất thất bại vẫn bị **cô lập** khỏi bộ nhớ dùng được.

---

## Dự án đang ở đâu hôm nay?

Tính đến phiên làm việc cuối tháng 6/2026:

- **26/26** bài kiểm thử tự động pass.
- **100%** năng lực cốt lõi có skill đã xác minh; **27** skill active trong ngân hàng.
- Vòng **khám phá chủ động** (Phase 5) và **bằng chứng đo lường** (Phase 6) hoàn thiện ở mức demo nghiên cứu.
- **`run-all` 6 seed** đã chạy thật (~4,5 h): PG +0,125, SG −0,042, GG +0,083; H1/H2 **chưa** đạt ý nghĩa thống kê (p ≈ 0,21 / 0,73).
- Bộ nhớ skill đã **sửa chữa và sao lưu** sau lỗi merge hiếm (skill biến thành văn bản mô tả) — minh chứng vận hành lâu dài.
- **Hai lần explore seed 42** + **một lần run-all** đã chạy thật, log tại `logs/trace.jsonl`.

Thách thức tiếp theo: (1) đạt ý nghĩa thống kê — cần thêm seed hoặc siết nhiễu (negative transfer); (2) **skill extraction** — một số bản trích xuất vẫn lỗi định dạng khi lưu; (3) **ổn định sau đóng băng** — SG âm trên SUB_003 và COMPLEX_001.

---

## Kết luận: Điều worth watching

Thế giới AI coding đang chạy đua **tốc độ viết code**. Evolutionary Coding Agent chọn hướng khác: **tốc độ học có kiểm soát**.

Nếu bạn quan tâm đến giáo dục AI, agent doanh nghiệp, hay đơn giản là muốn biết “AI tự luyện tập an toàn trông như thế nào”, câu chuyện Tiến sĩ Lin là một lăng kính dễ hình dung:

- Agent **tự nghĩ bài** — từ doanh số, tồn kho đến chuẩn hóa hồ sơ.
- **Cổng chất lượng** giữ đề thi công bằng.
- **Ngân hàng skill** giữ những gì đã chứng minh chạy được.
- **Sandbox** giữ máy bạn an toàn.
- **Dashboard** giữ lời hứa bằng số liệu.

Đó không phải tương lai xa. Đó là những gì đã chạy được — và đang được ghi lại từng dòng trong nhật ký thí nghiệm.

---

*Tài liệu liên quan: [use-case.md](use-case.md) (Dr. Lin §1 run-all + §2 durable skills + §3 oracle gates), [walkthrough.md](walkthrough.md), [memory.md](memory.md). Báo cáo: `logs/dashboard.html`; kiểm tra §1: `scratch/verify_memory_evidence.py`; kiểm tra §2: `scratch/verify_durable_skills.py`.*
