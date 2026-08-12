---
name: computer-graphics
description: Dựng scene 2D/3D bằng code — geometry, transform, camera/projection, lighting, depth, animation — và các hệ có trạng thái hình học rời rạc (Rubik's cube, board game 3D, puzzle, robot arm, bất kỳ thứ gì là "state machine + rigid-body transform + renderer"). Dùng khi user yêu cầu dựng hình 3D, mô phỏng vật lý/hình học, visualization kỹ thuật, hoặc debug một scene render sai (vật thể lệch vị trí, tối đen, xuyên nhau, xoay sai). Không phải để tạo ảnh nghệ thuật — xem phần "Generative/algorithmic art" ở cuối nếu đúng use-case đó.
---

# Computer Graphics

Trọng tâm của skill: **kiến thức graphics đúng, độc lập công nghệ.** Không
mặc định bất kỳ thư viện nào.

## Tôn trọng constraint của task trước

Đọc kỹ yêu cầu công nghệ trong request trước khi chọn cách implement:

- User nói "no WebGL, no libraries", "Canvas 2D thuần" → dùng Canvas 2D API
  gốc của trình duyệt (`getContext('2d')`), tự viết phép chiếu/quay bằng
  toán học nếu cần hiệu ứng 3D. Không tự ý load p5.js/Three.js.
- User cho phép hoặc yêu cầu Three.js → dùng Three.js.
- User yêu cầu WebGL trực tiếp → dùng WebGL API gốc.
- User không nói gì cụ thể → hỏi ngắn hoặc chọn phương án ít dependency nhất
  đáp ứng đúng yêu cầu (thường là Canvas 2D nếu scene không quá phức tạp).
  Không tự thêm CDN/thư viện chỉ vì "quen dùng".

Skill này không áp đặt công nghệ. Phần code mẫu bên dưới dùng tên hàm kiểu
p5.js/WebGL chỉ để minh họa khái niệm — dịch sang API thực tế đang dùng
(Canvas 2D thuần, Three.js, WebGL gốc...) khi implement.

---

## 1. Discrete geometric state — thường bị bỏ sót nhất

Nhiều bài toán "3D" thực chất là **state machine + rigid-body transform +
renderer**, không chỉ là "vẽ một mesh". Ví dụ điển hình: Rubik's cube, board
game 3D, robot arm, mô hình lắp ráp.

Trước khi đụng tới render, xác định rõ:

- **Đơn vị trạng thái là gì?** (cubie, quân cờ, khớp nối...) — mỗi đơn vị
  cần vị trí (position) và hướng (orientation) riêng, tách biệt khỏi mesh
  hình học dùng để vẽ nó.
- **Identity của các thành phần con** — với Rubik: mỗi mặt dán (sticker)
  thuộc cubie nào, ở mặt nào của cubie đó. Đừng để render logic tự suy luận
  ngược từ vị trí hiện tại; giữ identity tường minh trong data.
- **Phép biến đổi hợp lệ là gì** — với Rubik: chọn 1 lớp (layer selection
  theo trục + chỉ số lát), xoay 90°/180°/270° (quarter-turn convention phải
  cố định và nhất quán — ví dụ chiều xoay dương theo quy tắc bàn tay phải
  nhìn từ phía mặt đó ra ngoài).
- **Rotation composition** — khi 1 đơn vị bị xoay nhiều lần, orientation
  phải cộng dồn đúng (nhân ma trận/quaternion theo đúng thứ tự, không cộng
  góc Euler trực tiếp vì không giao hoán).
- **Snap-to-grid** — sau mỗi phép xoay hợp lệ (ví dụ đúng 90°), vị trí và
  hướng phải khớp lại lưới rời rạc chính xác, không tích lũy sai số float.
  Làm tròn về giá trị lưới hợp lệ gần nhất sau mỗi thao tác, không để trôi
  dần qua nhiều lần xoay.
- **Invariant cần giữ đúng mọi lúc** — ví dụ Rubik: tổng số cubie không đổi
  (27), không có cubie trùng vị trí, mỗi màu xuất hiện đúng số sticker quy
  định (9/màu với cube 3×3). Viết invariant ra tường minh trước khi code,
  dùng nó làm test sau này (xem mục Verification).

Tách rõ 2 lớp trong code:

- **Model layer**: state rời rạc thuần (vị trí/hướng logic, identity), không
  phụ thuộc thư viện render.
- **Render layer**: đọc model, vẽ ra scene bằng transform thực tế (mục 3).

Không trộn 2 lớp — logic xoay/kiểm tra invariant phải chạy được và test
được mà không cần khởi tạo canvas/WebGL.

---

## 2. Coordinate system & conventions

Xác định và ghi rõ ngay từ đầu (comment hoặc trong model layer), vì mỗi API
có quy ước khác nhau:

- Hệ tay phải hay tay trái?
- Trục Y hướng lên hay hướng xuống? (Canvas 2D DOM: Y xuống. p5 WEBGL: Y
  xuống. Three.js: Y lên theo mặc định — không giả định, phải kiểm tra API
  đang dùng.)
- Gốc tọa độ ở đâu (góc trên-trái, tâm canvas, tâm object)?
- Đơn vị góc: radian hay độ? (thường phải set tường minh, ví dụ
  `angleMode(RADIANS)` ở p5.)

Ghi sai quy ước là nguồn lỗi phổ biến nhất khi object "xoay sai hướng" hoặc
"lệch vị trí" — kiểm tra mục này trước khi nghi ngờ công thức toán.

---

## 3. Transformations

Stack biến đổi cộng dồn theo kiểu immediate-mode (API kiểu p5/WebGL) hoặc
scene-graph phân cấp (Three.js, dùng `object.add(child)` để con thừa hưởng
transform cha). Chọn đúng mô hình theo API đang dùng.

Với API immediate-mode, luôn bọc đẩy/khôi phục trạng thái quanh mỗi object
để tránh rò rỉ transform sang object kế tiếp (`push()`/`pop()` hoặc tương
đương).

Thứ tự transform chuẩn: **translate → rotate → scale** (đặt vị trí, xoay
quanh gốc cục bộ, rồi co giãn cục bộ). Đảo thứ tự làm object xoay quanh gốc
thế giới thay vì gốc chính nó — đây là nguyên nhân phổ biến khi object "văng
ra sai vị trí" lúc xoay.

Composite rotation (nhiều phép xoay chồng lên nhau, như Rubik ở mục 1) nên
dùng ma trận hoặc quaternion, không cộng dồn góc Euler trực tiếp — Euler
angle không giao hoán và gây gimbal lock khi tích lũy.

---

## 4. Camera & Projection

Hai loại phối cảnh, chọn theo mục đích chứ không theo mặc định của thư viện:

- **Perspective**: có foreshortening (xa nhỏ gần to), cảm giác chiều sâu tự
  nhiên. Dùng cho scene mô phỏng thị giác thật.
- **Orthographic**: không foreshortening, giữ tỉ lệ chính xác. Dùng cho
  visualization kỹ thuật, blueprint, isometric, hoặc khi cần đo đạc đúng
  tỉ lệ trên hình.

Tham số near/far-plane (hoặc tương đương) phải bọc sát range thực tế của
scene — quá lệch gây **z-fighting** (bề mặt gần nhau nhấp nháy do mất độ
chính xác depth buffer).

Nếu cho phép tương tác xoay góc nhìn (orbit control kiểu chuột/touch), chỉ
thêm khi user cần xem tương tác — không tự ý thêm nếu task chỉ cần 1 khung
hình/animation cố định.

---

## 5. Lighting

Nếu API có lighting model sẵn (Phong-like — p5 WEBGL, Three.js
MeshStandardMaterial...), dùng trực tiếp thay vì tự viết shader trừ khi task
yêu cầu hiệu ứng đặc biệt.

- Cần ít nhất 1 ambient + 1 directional/point light — chỉ ambient quá thấp
  mà thiếu nguồn sáng hướng làm cả scene tối đen, trông như lỗi thay vì chủ
  đích.
- Lighting đúng phụ thuộc **normal đúng**. Nếu tự dựng mesh bằng vertex thủ
  công, giữ **winding order nhất quán** (counter-clockwise nhìn từ ngoài mặt
  vào, theo quy ước hầu hết engine) để normal được tính đúng hướng — sai
  winding làm mặt tối ngược hoặc bị cull nhầm.
- Công cụ debug hữu ích: material tô màu theo normal (`normalMaterial()`
  ở p5, hoặc tương đương) để kiểm tra trực quan mesh có đúng hướng pháp
  tuyến không, tách biệt khỏi vấn đề ánh sáng.

---

## 6. Depth & occlusion

- Depth test (nếu API bật, thường là mặc định cho 3D) tự xử lý object gần
  che object xa — **trừ vật liệu trong suốt (alpha < 1)**.
- Với alpha blending: depth test không tự sắp xếp đúng thứ tự vẽ giữa các
  object trong suốt chồng nhau. Phải tự sort theo khoảng cách tới camera
  (xa → gần) trước khi vẽ, hoặc chấp nhận không cần trong suốt nếu task
  không yêu cầu.
- Nếu object "xuyên" nhau sai logic dù không dùng alpha: kiểm tra trước
  near/far-plane có bọc đúng scene không, và có 2 mặt phẳng trùng khít gây
  z-fighting không — đừng vội nghi ngờ transform logic.
- Sort theo depth mỗi frame tốn kém với số lượng object lớn — chỉ làm khi
  thật sự cần transparency đúng thứ tự.

---

## 7. Animation & interaction

- Animation trạng thái rời rạc (như 1 lượt xoay Rubik) nên tách 2 phần: nội
  suy góc/vị trí mượt trong lúc animate (dùng easing, không tuyến tính cứng
  nếu cần cảm giác tự nhiên), và **snap về trạng thái lưới chính xác** khi
  animation kết thúc (xem mục 1). Đừng để trạng thái model bị cập nhật sớm
  trước khi animation hoàn tất, tránh input tiếp theo áp dụng lên state
  chưa "chốt".
- Input xử lý thao tác (click, kéo, phím) nên map sang **lệnh trên model
  layer** (ví dụ "xoay layer X theo trục Y") trước, rồi model layer mới sinh
  animation — không xử lý trực tiếp trên render layer.

---

## 8. Performance

- Mesh tĩnh lặp lại nhiều lần (nhiều object cùng hình dạng) nên dựng 1 lần,
  cache lại (instancing hoặc buffer geometry tùy API), không rebuild mỗi
  frame.
- Kiểm tra frame rate thực tế khi scene có nhiều object động, không giả
  định "chắc mượt".

---

## 9. Verification — kiểm chứng trước khi xem

**Programmatic verification luôn đi trước visual verification.** Với hệ có
discrete state (mục 1), viết test kiểm tra invariant bằng code trước khi
nhờ user xem bằng mắt:

Ví dụ với Rubik's cube:

- Scramble → state phải khác solved.
- Scramble rồi áp lại đúng chuỗi solve → state phải về solved.
- Luôn đúng 54 sticker, đúng 9 sticker mỗi màu (cube 3×3).
- Luôn đúng 27 cubie, không mất/thừa/trùng vị trí.
- Mỗi cubie có orientation hợp lệ (khớp 1 trong các phép xoay hợp lệ của
  nhóm đối xứng khối lập phương, không phải giá trị bất kỳ).

Quy trình:

1. Viết test cho invariant cụ thể của bài toán (không phải test chung
   chung) — chạy được độc lập, không cần mở trình duyệt.
2. Chạy test, sửa tới khi pass.
3. Chỉ sau đó mới `write` file render/UI và gọi `verify` để user tự mở xem
   bằng mắt.
4. Không tuyên bố "render đúng/đẹp" nếu chưa qua bước 3 — verified (đã chạy
   test, đã qua verify) và assumed (đoán) là hai việc khác nhau.

Nếu user chạy trong CLI này (Termux): dùng `serve: python -m http.server`
để đưa URL xem thử khi cần, không tự ý mở trình duyệt nếu không được yêu
cầu.

---

## Generative / algorithmic art (tùy chọn — chỉ khi đúng use-case)

Phần này **không phải mặc định** của skill — chỉ dùng khi user thật sự
muốn nghệ thuật sinh bằng thuật toán (flow field, fractal, particle art
trừu tượng), không dùng cho visualization kỹ thuật, game, simulation, hay
bài toán có discrete state như mục 1.

- Có thể (không bắt buộc) đặt tên trào lưu thẩm mỹ và mô tả ngắn hướng tiếp
  cận (noise field, particle behavior, biến thiên tham số...) nếu điều đó
  giúp định hướng code — nhưng **không tạo file `.md` riêng theo mặc định**,
  không viết "philosophy" 4-6 đoạn trừ khi user yêu cầu rõ.
- Dùng seeded randomness (`randomSeed`/tương đương) nếu cần khả năng tái
  lập kết quả.
- Tham số nên tunable theo thuộc tính hệ thống (số lượng, scale, xác suất,
  tỉ lệ, góc, ngưỡng) nếu build UI điều khiển — chỉ thêm UI slider/seed
  navigation khi user cần khám phá biến thể, không thêm mặc định cho mọi
  yêu cầu.
- Output: 1 file `.html` tự chứa nếu cần chạy ngay trong trình duyệt, dùng
  đúng công nghệ user đã chỉ định (xem "Tôn trọng constraint của task").

---

## Tóm tắt quy trình

1. Đọc constraint công nghệ trong request — không tự chọn thư viện nếu
   user đã nói rõ.
2. Nếu bài toán có discrete state (mục 1): tách model layer khỏi render
   layer, định nghĩa invariant trước.
3. Implement render theo mục 2-6 (coordinate, transform, camera, lighting,
   depth) bằng đúng API đã chọn.
4. Animation/interaction map qua model layer trước (mục 7).
5. Viết test invariant, chạy pass trước (mục 9).
6. `write` file, sau đó `verify` để user xác nhận bằng mắt.

Minimum code giải quyết đúng vấn đề — không tạo thêm file, bước, hay ràng
buộc UI ngoài những gì task thật sự cần.
