# python-pptx (v1.1.0) skill

Dùng khi tạo, chỉnh sửa hoặc phân tích file Microsoft PowerPoint (`.pptx`).

Mục tiêu:

- Tạo file mở sạch trên Microsoft PowerPoint, PowerPoint Mobile, LibreOffice Impress và Canva Import.
- Ưu tiên tính hợp lệ, khả năng chỉnh sửa và tương thích.
- Không tuyên bố file chắc chắn không bị PowerPoint Repair nếu chưa kiểm tra bằng Microsoft PowerPoint thật.
- Animation và transition được phép khi người dùng yêu cầu.
- Do `python-pptx` chưa có API cấp cao đầy đủ cho animation và transition, chỉ xử lý OOXML khi thật sự cần và đã có cấu trúc đáng tin cậy để đối chiếu.

---

## Quy tắc bắt buộc

1. Ưu tiên API public của `python-pptx`.
2. Chỉ sửa OOXML trực tiếp khi API public không hỗ trợ yêu cầu.
3. Không tự dựng XML phức tạp từ trí nhớ.
4. Không dùng OOXML chỉ vì quen làm theo cách đó.
5. File hợp lệ quan trọng hơn hiệu ứng.
6. Minimum code giải quyết đúng yêu cầu.
7. Không thêm tính năng, abstraction hoặc cấu hình ngoài yêu cầu.
8. Không tạo hàng loạt script khám phá API.
9. Không retry nguyên trạng một thao tác đã lỗi hoặc bị policy chặn.
10. Đọc đầy đủ stack trace hoặc thông báo policy trước khi sửa.
11. Không khẳng định mức độ tương thích cao hơn mức đã thực sự kiểm tra.
12. Khi một bước trước đó sai, phải thừa nhận đúng diễn biến, không viết lại lịch sử như thể lỗi chưa từng xảy ra.

---

## Lập kế hoạch trước khi viết code

Trước khi tạo hoặc chỉnh sửa PowerPoint, xác định:

- File mới hay chỉnh file có sẵn.
- Số lượng slide.
- Tỷ lệ slide: 16:9, 4:3 hoặc tùy chỉnh.
- Nội dung và ngôn ngữ.
- Phong cách hình ảnh.
- Nền tảng mở chính:
  - Microsoft PowerPoint desktop.
  - PowerPoint Mobile.
  - LibreOffice Impress.
  - Canva Import.
- Có cần:
  - ảnh;
  - bảng;
  - biểu đồ;
  - hyperlink;
  - speaker notes;
  - video;
  - transition;
  - animation;
  - Morph.
- Yêu cầu nào dùng được API public.
- Yêu cầu nào bắt buộc phải dùng OOXML.
- Mức verify cần thực hiện sau khi tạo.

Trước khi viết OOXML, phải tự hỏi:

- API public có giải quyết được không?
- Có template hoặc XML mẫu đáng tin cậy không?
- Có cần hiệu ứng này thật không?
- Người dùng có chấp nhận rủi ro tương thích không?
- Có cách đơn giản hơn mà vẫn đạt mục tiêu không?

Không dùng sandbox hoặc lỗi runtime như một cơ chế thử-sai khi rule đã nói rõ cách làm đó bị cấm.

---

## Khi nào dùng skill khác

- Task lớn, nhiều module, nhiều đầu ra hoặc phạm vi chưa rõ:
  - gọi `skill(name="spec-driven")` trước khi lập kế hoạch chi tiết.
- Người dùng yêu cầu Canva, thiết kế slide thiên về visual hoặc muốn import sang Canva:
  - gọi `skill(name="canva")` trước;
  - chốt hướng thẩm mỹ;
  - sau đó dùng skill `powerpoint` để tạo `.pptx`.
- Cần tìm ảnh, icon, font hoặc asset web:
  - dùng skill hoặc tool chuyên dụng phù hợp;
  - không bịa URL;
  - không dùng asset chưa xác minh.

---

## Khả năng hỗ trợ chính thức

### Presentation

Hỗ trợ:

- Tạo presentation mới.
- Mở `.pptx` có sẵn.
- Chỉnh sửa presentation.
- Lưu presentation.
- Đổi kích thước slide.
- Tỷ lệ 16:9.
- Tỷ lệ 4:3.
- Kích thước tùy chỉnh.
- Đọc slide master và slide layout ở mức thư viện hỗ trợ.
- Core properties.

Giới hạn:

- Không có API public đầy đủ để chỉnh toàn bộ Slide Master như PowerPoint thật.
- Không giả định mọi thành phần theme hoặc master đều chỉnh được an toàn bằng API cấp cao.

### Slide

Hỗ trợ:

- Thêm slide.
- Chọn slide layout.
- Truy cập placeholder.
- Đọc shape.
- Chỉnh sửa shape.
- Notes slide.
- Speaker notes ở mức API hiện có.

Giới hạn:

- Không có `remove_slide()` public built-in.
- Xóa slide cần private API hoặc chỉnh package cẩn thận.
- Sau khi xóa hoặc sắp xếp slide, cần kiểm tra hyperlink nội bộ và relationship liên quan.

### Text

Hỗ trợ:

- TextBox.
- Placeholder text.
- `TextFrame`.
- Paragraph.
- Rich text bằng nhiều run.
- Font family.
- Font size.
- Bold.
- Italic.
- Underline.
- Font color.
- Paragraph alignment.
- Vertical alignment.
- Margin.
- Line spacing.
- Bullet nhiều cấp ở mức thư viện hỗ trợ.
- Auto size và text fitting ở mức hiện có.

Quy tắc:

- Ưu tiên dùng `TextFrame`.
- Không tạo nhiều run liên tiếp nếu chúng có cùng định dạng.
- Gộp nội dung cùng định dạng vào một run để code và XML gọn hơn.
- Không phụ thuộc vào font hiếm nếu file cần mở trên nhiều thiết bị.
- Khi dùng font không phổ biến, phải dự kiến font fallback.

### Shape

Hỗ trợ:

- AutoShape.
- Rectangle.
- Oval.
- Triangle.
- Arrow.
- Callout.
- Flowchart shape.
- Action button.
- Connector.
- Line.
- Freeform ở mức API hỗ trợ.
- Group Shape.
- Rotate.
- Resize.
- Position.
- Fill.
- Line formatting.

Lưu ý:

- Z-order thường phụ thuộc thứ tự shape trong collection.
- Không giả định luôn có API cấp cao đầy đủ cho mọi thao tác bring-to-front hoặc send-to-back.
- Group Shape được hỗ trợ nhưng không giả định mọi thao tác group hoặc ungroup đã có API tiện lợi như PowerPoint.

### Picture

Hỗ trợ:

- Chèn ảnh.
- Resize.
- Crop.
- Rotate.
- Đọc kích thước.
- Giữ tỷ lệ khung hình.
- Đổi vị trí.

Định dạng ảnh thực tế phụ thuộc vào Pillow và môi trường chạy.

Nếu ảnh không tồn tại hoặc không đọc được:

- không để pipeline crash nếu ảnh không phải phần bắt buộc;
- thay bằng placeholder shape; hoặc
- textbox ghi `Image not found`.

Không dùng exception rộng để che lỗi không liên quan.

Chỉ fallback khi:

- file không tồn tại;
- ảnh không đọc được;
- việc bỏ ảnh không làm sai mục tiêu chính.

Ví dụ:

```python
from pathlib import Path

image_path = Path("image.png")

if image_path.is_file():
    slide.shapes.add_picture(
        str(image_path),
        left,
        top,
        width,
        height,
    )
else:
    placeholder = slide.shapes.add_textbox(
        left,
        top,
        width,
        height,
    )
    placeholder.text_frame.text = "Image not found"
```

### Table

Hỗ trợ:

- Tạo bảng.
- Text trong cell.
- Alignment.
- Fill.
- Merge cell.
- Điều chỉnh kích thước hàng.
- Điều chỉnh kích thước cột.
- Border ở mức API hoặc OOXML thấp hơn.

Quy tắc:

- Tạo đủ số hàng và cột ngay từ đầu.
- Không tạo bảng lớn rồi xóa hàng hoặc cột bằng private API nếu không cần.
- Chỉ merge cell khi layout thật sự yêu cầu.
- Hạn chế merge phức tạp vì PowerPoint, LibreOffice và Canva có thể render khác nhau.
- Không hack border XML hàng loạt nếu thiết kế không cần border đặc biệt.

### Chart

Ưu tiên dùng:

```python
from pptx.chart.data import ChartData
```

Các nhóm chart thường dùng:

- Column.
- Bar.
- Line.
- Pie.
- Doughnut.
- Area.
- Radar.
- Scatter.
- Bubble.
- Stock ở mức thư viện hỗ trợ.

Combo chart có thể bị giới hạn tùy cấu trúc file.

Ví dụ:

```python
from pptx.chart.data import ChartData

chart_data = ChartData()
chart_data.categories = ["A", "B", "C"]
chart_data.add_series("Series 1", (10, 20, 30))
```

Quy tắc:

- Không sửa `chart.xml` thủ công nếu API public đã đủ.
- Nếu yêu cầu vượt API, nói rõ giới hạn trước khi sửa XML.
- Không tạo biểu đồ chỉ để trang trí nếu dữ liệu không phù hợp với chart.

### Hyperlink và action

Hỗ trợ:

- URL.
- `mailto:`.
- Hyperlink trên text run.
- Click action trên shape.
- Link nội bộ tới slide khác khi slide đích đã tồn tại.

URL hoặc `mailto:`:

```python
run.hyperlink.address = "https://example.com"
```

Link nội bộ:

```python
shape.click_action.target_slide = target_slide
```

Quy tắc:

- Không tạo link nội bộ tới slide chưa tồn tại.
- Sau khi xóa hoặc sắp xếp lại slide, kiểm tra link nội bộ.
- Không giả định relationship cũ luôn còn hợp lệ sau khi chỉnh package.

### Media

#### Video

`add_movie()` là API experimental.

Luôn:

- kiểm tra file tồn tại;
- truyền đúng `mime_type`;
- dùng poster frame nếu có;
- không giả định mọi codec đều chạy trên PowerPoint;
- không giả định file `.mp4` luôn dùng codec tương thích.

Ví dụ:

```python
from pathlib import Path

video_path = Path("sample.mp4")

if video_path.is_file():
    slide.shapes.add_movie(
        str(video_path),
        left,
        top,
        width,
        height,
        poster_frame_image="poster.png",
        mime_type="video/mp4",
    )
else:
    placeholder = slide.shapes.add_textbox(
        left,
        top,
        width,
        height,
    )
    placeholder.text_frame.text = "Video not found"
```

Nếu không có poster frame:

- có thể dùng hành vi mặc định của thư viện;
- phải báo rõ chưa cung cấp poster tùy chỉnh.

Nhúng được video không đảm bảo thiết bị đích phát được codec đó.

#### Audio

Không có API cấp cao ổn định tương đương `add_audio()`.

Không tuyên bố hỗ trợ audio hoàn chỉnh nếu chưa xác minh:

- media relationship;
- content type;
- XML liên quan;
- khả năng phát trên PowerPoint đích.

### Notes

Hỗ trợ:

- Truy cập notes slide.
- Thêm hoặc chỉnh sửa speaker notes ở mức API hiện có.

Không giả định mọi thành phần notes master đều chỉnh được bằng API public.

### Core properties

Các thuộc tính thường dùng:

- Author.
- Title.
- Subject.
- Category.
- Keywords.
- Comments.
- Content status.
- Language.
- Version.
- Created.
- Modified.
- Last modified by.

Ví dụ:

```python
props = prs.core_properties
props.title = "Demo"
props.author = "Author"
props.subject = "PowerPoint demo"
props.category = "Presentation"
props.keywords = "pptx, python-pptx"
props.comments = "Generated with python-pptx"
```

`Company` không thuộc `core_properties`.

`Company` thường nằm trong extended application properties, ví dụ:

```text
docProps/app.xml
```

`python-pptx` không cung cấp API public thông thường để chỉnh thuộc tính này.

Nếu người dùng bắt buộc cần `Company`:

- nói rõ đây không phải Core Property;
- chỉ sửa extended properties bằng OOXML khi thật sự cần;
- kiểm tra lại package sau khi chỉnh.

### Theme và hiệu ứng

Hỗ trợ một phần:

- Theme colors.
- Theme fonts.
- Fill.
- Transparency ở một số đối tượng.
- Shadow thông qua `ShadowFormat` ở mức API hiện có.

Không giả định hỗ trợ đầy đủ:

- Glow.
- Reflection.
- Soft edges.
- 3D format.
- Artistic effects.
- Designer.
- SmartArt.

---

## Xóa slide

`python-pptx` không có `remove_slide()` public built-in.

Có thể xóa slide bằng private API:

```python
def delete_slide(prs, index):
    if index < 0 or index >= len(prs.slides):
        raise IndexError("Slide index out of range")

    slide_id = prs.slides._sldIdLst[index]
    relationship_id = slide_id.rId

    prs.part.drop_rel(relationship_id)
    del prs.slides._sldIdLst[index]
```

Lưu ý:

- Đây là private API.
- Không có cam kết ổn định giữa các phiên bản.
- Phải kiểm tra index trước khi xóa.
- Link nội bộ tới slide bị xóa có thể trở thành link chết.
- Custom shows và relationship khác có thể bị ảnh hưởng.
- Presentation phức tạp cần kiểm tra lại package sau khi xóa.

Không chỉ xóa node `<p:sldId>` rồi bỏ lại relationship của presentation nếu có thể dọn đúng relationship.

---

## Animation và transition

`python-pptx` 1.0.2 chưa có API cấp cao đầy đủ để tạo hoặc chỉnh sửa:

- Shape animation.
- Text animation.
- Entrance effect.
- Emphasis effect.
- Exit effect.
- Motion path.
- Trigger.
- Slide transition.
- Morph.

Đây là giới hạn của thư viện, không phải giới hạn của định dạng `.pptx`.

PowerPoint lưu các thành phần này trong OOXML, thường tại:

```text
ppt/slides/slideN.xml
```

Cấu trúc slide tổng quát:

```xml
<p:sld>
  <p:cSld>...</p:cSld>
  <p:clrMapOvr>...</p:clrMapOvr>
  <p:transition>...</p:transition>
  <p:timing>...</p:timing>
  <p:extLst>...</p:extLst>
</p:sld>
```

Quy tắc:

- Không tự viết toàn bộ `slide.xml` từ đầu khi không có schema hoặc template đáng tin cậy.
- Thao tác trên `slide._element` khi có thể.
- Không thay toàn bộ XML của slide chỉ để thêm một hiệu ứng.
- Giữ nguyên nội dung và relationship không liên quan.

---

## Transition đơn giản

Transition đơn giản có thể chèn bằng OOXML khi:

- cấu trúc đã được xác minh;
- tag transition được PowerPoint hỗ trợ;
- vị trí node đúng schema.

Ví dụ:

```python
from lxml import etree
from pptx.oxml.ns import qn


def add_transition(slide, transition_tag="fade", speed="med"):
    """
    Thêm transition đơn giản.

    transition_tag thường dùng:
    fade, wipe, push, cut

    Không giả định mọi tag đều tương thích với mọi phiên bản PowerPoint.
    """
    slide_element = slide._element

    existing = slide_element.find(qn("p:transition"))
    if existing is not None:
        slide_element.remove(existing)

    transition = etree.Element(qn("p:transition"))
    transition.set("spd", speed)
    etree.SubElement(transition, qn(f"p:{transition_tag}"))

    timing = slide_element.find(qn("p:timing"))
    extension_list = slide_element.find(qn("p:extLst"))

    if timing is not None:
        slide_element.insert(
            slide_element.index(timing),
            transition,
        )
    elif extension_list is not None:
        slide_element.insert(
            slide_element.index(extension_list),
            transition,
        )
    else:
        slide_element.append(transition)

    return transition
```

Không thêm tham số như `duration_ms` nếu code không thật sự ghi thời lượng đó vào XML.

Không quảng cáo hỗ trợ duration tùy ý nếu chưa xác minh schema và phiên bản PowerPoint tương ứng.

Transition thường phải nằm:

- sau `p:clrMapOvr`;
- trước `p:timing`;
- trước `p:extLst`.

Nếu slide đã có transition:

- không tạo transition thứ hai;
- thay hoặc chỉnh node hiện tại có chủ đích.

---

## Animation trong slide

Cấu trúc `<p:timing>` sâu và dễ sai.

Nó có thể chứa:

- `<p:tnLst>`.
- `<p:par>`.
- `<p:seq>`.
- `<p:cTn>`.
- `<p:childTnLst>`.
- `<p:condLst>`.
- behavior node.
- target node.
- `<p:spTgt spid="...">`.

Không cung cấp hàm animation dở dang có tên như thể đã hoạt động hoàn chỉnh.

Không tự dựng timing tree phức tạp từ trí nhớ.

### Cách an toàn nhất

1. Tạo file mẫu bằng Microsoft PowerPoint thật.
2. Thêm đúng một animation đơn giản vào một shape.
3. Lưu file mẫu.
4. Giải nén `.pptx`.
5. Đọc phần `<p:timing>` trong `ppt/slides/slideN.xml`.
6. Clone đúng cây XML từ mẫu.
7. Xác định toàn bộ timing ID trong template.
8. Remap tất cả ID cần thiết.
9. Thay `spid` bằng `shape.shape_id` của shape đích.
10. Chèn node vào đúng vị trí.
11. Kiểm tra package và XML.
12. Mở lại bằng `python-pptx`.
13. Khi có thể, mở thử bằng Microsoft PowerPoint thật.

Animation đơn giản có thể đáng tin cậy hơn khi clone từ template do PowerPoint tạo và chỉ thay đúng các ID cần thiết.

Không coi việc tự dựng toàn bộ timing tree từ đầu là ổn định nếu chưa có schema, template hoặc testcase xác minh.

### Quy tắc ID

- Mỗi ID trong timing tree phải duy nhất trong slide.
- Không chỉ đổi một ID rồi giữ nguyên các ID còn lại từ template.
- Phải xác định các ID đã tồn tại trước khi thêm node mới.
- `spid` trong `<p:spTgt>` phải bằng `shape.shape_id`.
- `shape.shape_id` không phải index của shape trong `slide.shapes`.

### Slide đã có animation

Nếu slide đã có `<p:timing>`:

- không tạo `<p:timing>` thứ hai;
- append hoặc clone đúng node con vào timing tree hiện tại;
- bảo toàn timing ID và quan hệ sẵn có;
- không thay toàn bộ timing tree nếu không có chủ đích rõ ràng.

### Animation phức tạp

Hỏi lại người dùng nếu yêu cầu chưa đủ rõ đối với:

- Motion path tùy chỉnh.
- Nhiều trigger lồng nhau.
- Animation đồng bộ nhiều shape.
- Animation theo từng từ.
- Animation theo từng ký tự.
- Animation phụ thuộc media timeline.
- Morph giữa các slide.
- Sequence phức tạp trộn:
  - after previous;
  - with previous;
  - on click.

Nói rõ rủi ro:

- PowerPoint có thể Repair file.
- LibreOffice có thể bỏ qua hiệu ứng.
- Canva có thể không import animation.
- PowerPoint Mobile có thể hiển thị khác desktop.
- Morph thường phụ thuộc vào cấu trúc và metadata do PowerPoint tạo.

---

## Nguyên tắc sửa OOXML

Không sửa trực tiếp các phần sau nếu API public đã hỗ trợ yêu cầu:

- Text.
- Shape.
- Picture.
- Table.
- Chart.
- Standard hyperlink.
- Core properties.

Không sửa tay các file package nhạy cảm nếu không thật sự cần:

- `ppt/presentation.xml`.
- `ppt/_rels/`.
- `ppt/slides/_rels/`.
- `ppt/charts/`.
- `[Content_Types].xml`.

Các trường hợp có thể cân nhắc OOXML:

- Animation.
- Transition.
- Extended properties như `Company`.
- Tính năng PowerPoint không có API public.
- Một thuộc tính cụ thể đã được xác minh bằng template hoặc schema.

Khi sửa XML:

1. Không tạo XML bằng nối chuỗi.
2. Dùng `lxml.etree`.
3. Dùng `qn()` cho namespace đã được `python-pptx` định nghĩa.
4. Không tạo namespace prefix tùy tiện.
5. Giữ đúng thứ tự node theo schema.
6. Không tạo relationship ID trùng.
7. Không tạo timing ID trùng.
8. Không tạo node trùng khi slide đã có node tương ứng.
9. Không sửa nhiều phần OOXML cùng lúc nếu có thể chia thành các bước nhỏ.
10. Không xóa node không liên quan.
11. Không thay nguyên package khi chỉ cần sửa một node.
12. Ghi rõ phần nào dùng private API hoặc OOXML trực tiếp.

---

## Kiểm tra sau khi generate

`save()` thành công không có nghĩa là Microsoft PowerPoint chắc chắn mở file mà không Repair.

### Mức 1: bắt buộc

Lưu và mở lại bằng `python-pptx`:

```python
from pptx import Presentation

prs.save(output_path)
verified = Presentation(output_path)
```

Việc này xác nhận:

- package có thể đọc;
- XML đủ well-formed để `python-pptx` parse;
- cấu trúc cơ bản chưa hỏng nghiêm trọng.

Nó không xác nhận đầy đủ:

- animation hoạt động đúng;
- transition hoạt động đúng;
- PowerPoint sẽ không Repair;
- Canva sẽ giữ nguyên mọi hiệu ứng.

### Mức 2: bắt buộc khi sửa OOXML thủ công

Kiểm tra tối thiểu:

- file là ZIP hợp lệ;
- các XML vừa chỉnh parse được;
- relationship target tồn tại;
- không có relationship ID trùng;
- không có timing ID trùng;
- `spid` trỏ tới shape tồn tại;
- không có hai `<p:timing>` ngoài chủ đích;
- không có hai `<p:transition>` ngoài chủ đích;
- node nằm đúng vị trí tương đối trong slide XML.

Có thể dùng:

- `zipfile`;
- `lxml`;
- API đọc package hiện có.

Không tạo một validator khổng lồ nếu chỉ cần kiểm tra vài file XML vừa chỉnh.

### Mức 3: xác nhận bằng PowerPoint thật

Muốn khẳng định:

> File mở sạch và không bị Microsoft PowerPoint Repair.

thì phải:

- mở file bằng Microsoft PowerPoint desktop; hoặc
- dùng validator OOXML đủ khả năng kiểm tra schema liên quan.

Nếu chưa thực hiện bước này, chỉ được báo:

> File đã qua kiểm tra cấu trúc cơ bản và mở lại thành công bằng python-pptx.

Nếu đã sửa OOXML:

> File đã qua kiểm tra cấu trúc cơ bản, XML liên quan đã parse thành công và file mở lại được bằng python-pptx. Chưa xác nhận bằng Microsoft PowerPoint desktop.

Không tuyên bố tuyệt đối nếu chưa có bằng chứng tương ứng.

---

## Khả năng tương thích

Thứ tự ưu tiên mặc định:

1. Microsoft PowerPoint desktop.
2. PowerPoint Mobile.
3. LibreOffice Impress.
4. Canva Import.

Các thành phần thường tương thích tốt:

- Text.
- Picture.
- Basic shape.
- Table đơn giản.
- Chart phổ biến.
- URL hyperlink.

Các thành phần có thể hiển thị khác nhau:

- Theme.
- Font fallback.
- Complex table merge.
- Video codec.
- Shadow.
- Transparency.
- Custom XML effects.
- Animation.
- Transition.
- Morph.

Nếu người dùng chủ yếu mở bằng Canva:

- ưu tiên text, picture, shape, table và chart;
- hạn chế layout phụ thuộc font hiếm;
- hạn chế hiệu ứng phụ thuộc XML đặc thù của PowerPoint;
- báo trước animation và transition có thể bị bỏ qua;
- không cần loại bỏ animation nếu file vẫn chủ yếu dùng trong PowerPoint.

---

## Workflow khi tạo PowerPoint

1. Đọc yêu cầu.
2. Xác định output:
   - số slide;
   - tỷ lệ;
   - nội dung;
   - ngôn ngữ;
   - phong cách;
   - nền tảng mở chính;
   - asset cần thiết;
   - animation, transition hoặc media.
3. Nếu task lớn hoặc mơ hồ, dùng `spec-driven`.
4. Nếu thiên về visual hoặc Canva, dùng `canva` trước.
5. Lập dàn ý slide.
6. Chọn API public phù hợp.
7. Chỉ dùng OOXML cho phần API không hỗ trợ.
8. Không viết hàng loạt script khám phá thư viện.
9. Viết script chính ngắn gọn.
10. Chạy script tạo file.
11. Nếu lỗi:
    - đọc toàn bộ stack trace;
    - xác định đúng dòng lỗi;
    - phân loại lỗi;
    - sửa nguyên nhân thực tế;
    - không retry nguyên trạng.
12. Lưu file.
13. Mở lại bằng `Presentation(output_path)`.
14. Nếu sửa OOXML:
    - kiểm tra ZIP;
    - parse XML;
    - kiểm tra relationship;
    - kiểm tra ID;
    - kiểm tra shape target.
15. Chỉ thông báo hoàn thành khi file đã qua mức verify phù hợp.

---

## Workflow khi chỉnh sửa PowerPoint có sẵn

1. Mở file gốc bằng `Presentation`.
2. Đọc cấu trúc slide cần chỉnh.
3. Không xây lại toàn bộ deck nếu chỉ cần sửa vài thành phần.
4. Giữ nguyên:
   - theme;
   - layout;
   - master;
   - relationship;
   - metadata;
   - nội dung không liên quan.
5. Sửa đúng slide và đúng shape.
6. Không dựa vào index shape nếu file có thể thay đổi.
7. Khi có thể, định vị shape bằng:
   - name;
   - placeholder type;
   - text đặc trưng;
   - shape ID;
   - vị trí đã xác minh.
8. Lưu ra file mới nếu người dùng không yêu cầu ghi đè.
9. Mở lại và verify.
10. Nếu có hyperlink, animation hoặc media, kiểm tra relationship liên quan.

---

## Xử lý lỗi tool và code

- Đọc đầy đủ thông báo lỗi trước khi chọn bước tiếp theo.
- Phân biệt:
  - lỗi code;
  - lỗi dữ liệu;
  - lỗi dependency;
  - lỗi file;
  - lỗi policy;
  - lỗi tương thích.
- Không gọi lại nguyên command đã thất bại.
- Không đổi nhẹ quote, khoảng trắng hoặc cú pháp rồi retry cùng một pattern bị cấm.
- Chỉ retry khi nguyên nhân đã được sửa thực sự.
- Không dùng command bị policy cấm để verify.
- Không dùng inline eval nếu môi trường cấm `python -c` hoặc `node -e`.
- Khi cần verify bằng Python, viết file `.py` tin cậy trong project rồi chạy file đó.
- Không tuyên bố thành công khi tool chưa chạy thành công.
- Nếu không có cách hợp lệ trong policy, dừng và nói rõ giới hạn.

Nếu một bước trước đã sai:

- thừa nhận trực tiếp;
- mô tả đúng lệnh hoặc cách làm đã sai;
- nói rõ vì sao sai;
- nêu cách đã sửa;
- không trả lời như thể lần thử sai chưa từng xảy ra.

Ví dụ đúng:

> Ở bước đầu tôi đã dùng `cd ... && python3`, dù policy cấm `&&`. Đó là lỗi tuân thủ của tôi. Tôi đã sửa bằng cách chạy `python3` với đường dẫn đầy đủ.

---

## Không tự khám phá API quá mức

Không tạo hàng loạt file dạng:

- `check_api.py`.
- `check_shapes.py`.
- `check_props.py`.
- `inspect_pptx.py`.
- `list_methods.py`.
- `list_enum.py`.
- `verify_final.py`.
- `verify_final_2.py`.

Chỉ tạo probe nhỏ khi:

- lỗi thực tế phụ thuộc đúng một API;
- tài liệu skill không đủ trả lời;
- probe trực tiếp giúp sửa lỗi đang gặp;
- không có cách kiểm tra đơn giản hơn.

Sau khi probe xong:

- xóa file tạm nếu người dùng không cần giữ;
- không để lại nhiều script rác trong project.

Ưu tiên:

- đọc tài liệu hiện có;
- viết code chính ngắn;
- chạy thử;
- sửa lỗi thật.

Không nghiên cứu toàn bộ bề mặt API trước khi bắt đầu một task nhỏ.

---

## Simplicity First

Viết minimum code giải quyết đúng yêu cầu.

Không:

- tạo framework cho một file PowerPoint;
- tạo presentation engine tổng quát;
- tạo class nếu vài hàm nhỏ đã đủ;
- thêm config system không ai yêu cầu;
- thêm plugin system;
- thêm abstraction chỉ dùng một lần;
- thêm error handling cho tình huống không thể xảy ra;
- thêm hiệu ứng hoặc slide ngoài yêu cầu;
- tạo nhiều theme khi người dùng chỉ cần một deck;
- viết 900 dòng nếu 200 đến 300 dòng đã giải quyết rõ ràng.

Chỉ tạo helper khi:

- logic dùng lại nhiều lần; hoặc
- helper làm code dễ đọc rõ rệt.

Trước khi hoàn thành, tự hỏi:

> Một senior engineer có cho rằng giải pháp này quá phức tạp so với yêu cầu không?

Nếu có, đơn giản hóa.

---

## Chất lượng thiết kế slide

Trừ khi người dùng yêu cầu phong cách khác:

- Dùng bố cục rõ ràng.
- Giữ hierarchy giữa title, heading và body.
- Không nhồi quá nhiều nội dung vào một slide.
- Không đặt text sát mép slide.
- Không để text đè lên shape, ảnh hoặc thành phần giao diện.
- Không dùng font quá nhỏ để nhét nội dung.
- Giữ khoảng trắng đủ thở.
- Dùng màu có độ tương phản phù hợp.
- Không lạm dụng card, khung, badge hoặc header dày.
- Không để thanh điều hướng, số slide hoặc decoration chiếm diện tích nội dung quá mức.
- Với slide giáo dục, ưu tiên:
  - nội dung dễ đọc;
  - ví dụ rõ;
  - bài tập có không gian làm bài;
  - hình ảnh hỗ trợ đúng nội dung.
- Với slide song ngữ:
  - phân cấp rõ ngôn ngữ chính và bản dịch;
  - không làm cả hai ngôn ngữ cạnh tranh thị giác ngang nhau nếu gây rối;
  - giữ cách trình bày nhất quán giữa các slide.

Khi tạo thumbnail hoặc collage preview:

- preview chỉ dùng để quan sát tổng thể;
- không coi thumbnail là bằng chứng rằng text không tràn;
- cần kiểm tra slide ở kích thước thật nếu layout dày.

---

## Báo cáo sau khi hoàn thành

Tóm tắt ngắn:

- File code đã tạo hoặc sửa.
- File `.pptx` đầu ra.
- Số lượng slide.
- Các tính năng đã thực hiện.
- Yêu cầu chưa thực hiện được.
- Giới hạn thuộc:
  - API `python-pptx`;
  - định dạng PPTX;
  - môi trường;
  - asset đầu vào;
  - nền tảng đích.
- Cách chạy.
- Cách verify.
- Mức kiểm tra đã thực hiện:
  - reopen bằng `python-pptx`;
  - kiểm tra OOXML;
  - mở bằng PowerPoint thật hay chưa.

Không giải thích lại toàn bộ code nếu người dùng không yêu cầu.

Không nói:

> File chắc chắn không bị Repair.

trừ khi đã kiểm tra bằng Microsoft PowerPoint thật hoặc validator phù hợp.

---

## Kết luận

`python-pptx` là công cụ ưu tiên, không phải giới hạn tuyệt đối của PowerPoint.

- Nếu API public hỗ trợ, dùng API public.
- Nếu PowerPoint hỗ trợ nhưng `python-pptx` chưa có API, có thể dùng OOXML khi thật sự cần.
- Không tự dựng XML phức tạp khi chưa có cấu trúc đáng tin cậy.
- Animation và transition được phép, nhưng phải ưu tiên template do PowerPoint thật tạo.

Quy trình animation an toàn:

1. Lấy XML mẫu do PowerPoint thật tạo.
2. Clone đúng cấu trúc.
3. Remap toàn bộ timing ID cần thiết.
4. Thay đúng `spid`.
5. Chèn đúng vị trí.
6. Không tạo node trùng.
7. Kiểm tra package và XML.
8. Mở lại bằng `python-pptx`.
9. Không khẳng định chắc chắn không Repair nếu chưa thử bằng Microsoft PowerPoint thật.

File hợp lệ, dễ mở và dễ chỉnh sửa luôn quan trọng hơn hiệu ứng.