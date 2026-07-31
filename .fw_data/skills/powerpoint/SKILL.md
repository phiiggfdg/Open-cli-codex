# python-pptx (v1.0.2) skill

Dùng khi tạo, chỉnh sửa hoặc phân tích file Microsoft PowerPoint (`.pptx`).

Mục tiêu: tạo file mở sạch trên Microsoft PowerPoint, PowerPoint Mobile, LibreOffice và Canva Import, không bị yêu cầu Repair.

Animation và transition được phép làm khi người dùng cần. Đây không phải tính năng bị cấm, nhưng do `python-pptx` chưa có API cấp cao chính thức nên phải xử lý OOXML cẩn thận, ưu tiên clone cấu trúc từ file mẫu do PowerPoint thật tạo thay vì tự bịa XML.

---

## Nguyên tắc cốt lõi

1. Ưu tiên API công khai của `python-pptx`.
2. Chỉ sửa OOXML trực tiếp khi API chính thức không hỗ trợ yêu cầu.
3. Không tự bịa cấu trúc XML phức tạp từ trí nhớ.
4. File hợp lệ quan trọng hơn hiệu ứng.
5. Không tuyên bố file chắc chắn không bị PowerPoint Repair nếu chưa mở thử bằng Microsoft PowerPoint thật.
6. Không tạo hàng loạt script `check_*.py`, `inspect_*.py`, `list_*.py` chỉ để khám phá API.
7. Chỉ kiểm tra API khi gặp lỗi thực tế hoặc cần xác minh đúng một thuộc tính cụ thể.

---

## Khả năng hỗ trợ chính thức

### Presentation

- Tạo presentation mới.
- Mở và chỉnh sửa `.pptx` có sẵn.
- Lưu presentation.
- Đổi kích thước slide.
- Hỗ trợ tỷ lệ 16:9, 4:3 hoặc kích thước tùy chỉnh.
- Đọc slide master và slide layout ở mức thư viện hỗ trợ.
- Không có API đầy đủ để chỉnh sửa toàn bộ Slide Master như PowerPoint thật.

### Slide

- Thêm slide.
- Chọn slide layout.
- Truy cập placeholder.
- Đọc và chỉnh sửa shape trên slide.
- Notes slide và speaker notes.
- Không có `remove_slide()` public built-in.

### Text

- TextBox.
- Placeholder text.
- TextFrame.
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
- Bullet nhiều cấp ở mức hỗ trợ của thư viện.
- Auto size và text fitting ở mức hỗ trợ hiện có.

Ưu tiên dùng `TextFrame`.

Không tạo nhiều run liên tiếp nếu các run có cùng định dạng. Gộp nội dung vào một run để code và XML gọn hơn.

### Shape

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
- Z-order theo thứ tự shape trong collection, nhưng không giả định có API cấp cao đầy đủ cho mọi thao tác bring-to-front hoặc send-to-back.

Group Shape được hỗ trợ, nhưng không giả định mọi thao tác group hoặc ungroup shape đã tồn tại đều có API tiện lợi như trong PowerPoint.

### Picture

- Chèn ảnh.
- Resize.
- Crop.
- Rotate.
- Đọc kích thước.
- Giữ tỷ lệ khung hình.
- Thay đổi vị trí.

Các định dạng ảnh thực tế còn phụ thuộc vào Pillow và môi trường chạy.

Nếu ảnh không tồn tại, không để pipeline crash. Thay bằng:

- placeholder shape; hoặc
- textbox ghi `Image not found`.

### Table

- Tạo bảng.
- Định dạng text trong cell.
- Alignment.
- Fill.
- Merge cell.
- Điều chỉnh kích thước hàng và cột.
- Border chỉ được hỗ trợ một phần qua API hoặc XML thấp hơn.

Tạo đủ số hàng và cột ngay từ đầu.

Không merge cell nếu không thật sự cần, vì bảng merge phức tạp có thể hiển thị khác giữa PowerPoint, LibreOffice và Canva.

### Chart

Ưu tiên dùng `ChartData` và API chart chính thức.

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
- Stock ở mức hỗ trợ của thư viện.
- Combo chart có thể bị giới hạn tùy cấu trúc file.

Không chỉnh XML chart thủ công nếu API chính thức đã đáp ứng được yêu cầu.

### Hyperlink và action

Hỗ trợ:

- URL.
- `mailto:`.
- Hyperlink trên text run.
- Click action trên shape.
- Link nội bộ tới slide khác khi slide đích đã tồn tại.

Ví dụ link nội bộ:

```python
shape.click_action.target_slide = target_slide

Không tạo hyperlink nội bộ tới một slide chưa tồn tại hoặc chưa xác định rõ.

Media

Video qua add_movie().

add_movie() là API experimental.

Audio không có API cấp cao riêng ổn định tương đương add_audio().


Không tuyên bố hỗ trợ audio hoàn chỉnh nếu chưa xác minh đúng media relationship và XML liên quan.

Notes

Truy cập notes slide.

Thêm hoặc chỉnh sửa speaker notes ở mức API hiện có.


Core properties

Các thuộc tính thường dùng:

Author.

Title.

Subject.

Category.

Keywords.

Comments.

Content status.

Language.

Version.

Created.

Modified.

Last modified by.


Ví dụ:

props = prs.core_properties
props.title = "Demo"
props.author = "Author"
props.subject = "PowerPoint demo"
props.category = "Presentation"
props.keywords = "pptx, python-pptx"
props.comments = "Generated with python-pptx"

Company không thuộc core_properties.

Company thường nằm trong extended application properties, ví dụ docProps/app.xml. python-pptx không cung cấp API public thông thường để chỉnh thuộc tính này.

Nếu người dùng bắt buộc cần Company:

nói rõ đây không phải Core Property;

chỉ sửa extended properties bằng OOXML khi thật sự cần;

kiểm tra lại package sau khi chỉnh.


Theme và hiệu ứng

Hỗ trợ một phần:

Theme colors.

Theme fonts.

Fill.

Transparency ở một số đối tượng.

Shadow thông qua ShadowFormat ở mức API hiện có.


Không giả định hỗ trợ đầy đủ:

Glow.

Reflection.

Soft edges.

3D format.

Artistic effects.

Designer.

SmartArt.



---

Xóa slide

python-pptx không có remove_slide() public built-in.

Có thể xóa slide bằng private API:

def delete_slide(prs, index):
    slide_id = prs.slides._sldIdLst[index]
    relationship_id = slide_id.rId

    prs.part.drop_rel(relationship_id)
    del prs.slides._sldIdLst[index]

Lưu ý:

Đây là private API.

Không có cam kết ổn định giữa các phiên bản.

Phải kiểm tra index hợp lệ trước khi xóa.

Các link nội bộ trỏ tới slide bị xóa có thể trở thành relationship lỗi hoặc link chết.

Nếu presentation phức tạp, phải kiểm tra lại hyperlinks, custom shows và relationship liên quan.


Không chỉ xóa node <p:sldId> mà bỏ qua relationship của presentation nếu có thể dọn đúng relationship.


---

Animation và transition

python-pptx 1.0.2 chưa có API cấp cao chính thức để tạo hoặc chỉnh sửa đầy đủ:

Shape animation.

Text animation.

Entrance effect.

Emphasis effect.

Exit effect.

Motion path.

Trigger.

Slide transition.

Morph.


Đây là giới hạn của thư viện, không phải giới hạn của định dạng .pptx.

PowerPoint lưu các tính năng này trong OOXML, chủ yếu tại ppt/slides/slideN.xml.

Cấu trúc tổng quát:

<p:sld>
  <p:cSld>...</p:cSld>
  <p:clrMapOvr>...</p:clrMapOvr>
  <p:transition>...</p:transition>
  <p:timing>...</p:timing>
  <p:extLst>...</p:extLst>
</p:sld>

Không tự viết toàn bộ slide.xml từ đầu.

Luôn thao tác trên slide._element, vì đây là cây lxml mà python-pptx đã load và dựng sẵn.


---

Transition đơn giản

Transition đơn giản có thể chèn trực tiếp bằng OOXML nếu cấu trúc đã được xác minh.

Ví dụ chèn transition và giữ đúng thứ tự node:

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
        slide_element.insert(slide_element.index(timing), transition)
    elif extension_list is not None:
        slide_element.insert(
            slide_element.index(extension_list),
            transition,
        )
    else:
        slide_element.append(transition)

    return transition

Không thêm tham số như duration_ms nếu code thực tế không ghi thời lượng đó vào XML.

Không quảng cáo hỗ trợ duration tùy ý nếu chưa xác minh schema và PowerPoint version tương ứng.

Transition phải nằm đúng vị trí theo thứ tự schema, thường sau clrMapOvr và trước timing hoặc extLst.


---

Animation trong slide

Cấu trúc <p:timing> sâu và dễ sai.

Nó có thể chứa nhiều tầng:

<p:tnLst>.

<p:par>.

<p:seq>.

<p:cTn>.

<p:childTnLst>.

<p:condLst>.

behavior node.

target node.

<p:spTgt spid="...">.


Không cung cấp hàm animation dở dang có tên như thể đã hoạt động hoàn chỉnh.

Không tự dựng timing tree phức tạp từ trí nhớ.

Cách an toàn nhất

1. Tạo một file mẫu bằng Microsoft PowerPoint thật.


2. Chỉ thêm một animation đơn giản vào một shape.


3. Lưu file mẫu.


4. Giải nén .pptx.


5. Đọc phần <p:timing> trong ppt/slides/slideN.xml.


6. Clone đúng cây XML từ mẫu.


7. Remap toàn bộ timing ID cần thiết.


8. Thay spid bằng shape.shape_id của shape đích.


9. Chèn vào slide đúng vị trí.


10. Kiểm tra lại file.



Animation đơn giản có thể thực hiện đáng tin cậy khi clone từ template do PowerPoint tạo và chỉ thay các ID cần thiết.

Không coi việc tự dựng toàn bộ timing tree từ đầu là ổn định.

Quy tắc ID

Mỗi id trong các node timing phải duy nhất trong toàn bộ timing tree của slide.

Không chỉ đổi một id rồi giữ nguyên các ID còn lại từ template.

Phải xác định toàn bộ ID đã tồn tại trước khi thêm node mới.

spid trong <p:spTgt> phải bằng shape.shape_id.

shape.shape_id không phải index của shape trong slide.shapes.


Slide đã có animation

Nếu slide đã có <p:timing>:

không tạo <p:timing> thứ hai;

clone hoặc append đúng node con vào timing tree hiện tại;

bảo toàn ID và quan hệ timing sẵn có;

không thay toàn bộ timing tree nếu không có chủ đích rõ ràng.


Animation phức tạp

Trước khi làm các hiệu ứng sau, hỏi lại người dùng nếu yêu cầu chưa thật sự rõ:

Motion path tùy chỉnh.

Nhiều trigger lồng nhau.

Animation đồng bộ nhiều shape.

Animation theo từng từ hoặc từng ký tự.

Animation phụ thuộc media timeline.

Morph giữa các slide.

Sequence phức tạp có after-previous và with-previous trộn lẫn.


Nói rõ rủi ro:

PowerPoint có thể Repair file.

LibreOffice có thể bỏ qua hiệu ứng.

Canva có thể không import animation.

PowerPoint Mobile có thể hiển thị khác bản desktop.



---

Nguyên tắc sửa OOXML

Không sửa trực tiếp các phần sau nếu API chính thức đã hỗ trợ yêu cầu:

Text.

Shape.

Picture.

Table.

Chart.

Standard hyperlink.

Core properties.


Không sửa tay:

ppt/presentation.xml.

ppt/_rels/.

ppt/slides/_rels/.

ppt/charts/.

[Content_Types].xml.


trừ khi thật sự cần và hiểu rõ relationship/package structure.

Các trường hợp được phép cân nhắc:

Animation.

Transition.

Extended properties như Company.

Tính năng PowerPoint không có API public trong python-pptx.


Khi sửa XML:

1. Không tạo XML bằng nối chuỗi.


2. Dùng lxml.etree.


3. Dùng qn() cho namespace đã được python-pptx định nghĩa.


4. Không tạo namespace prefix tùy tiện.


5. Giữ đúng thứ tự node theo schema.


6. Không tạo relationship ID trùng.


7. Không tạo timing ID trùng.


8. Không tạo node trùng khi slide đã có node tương ứng.


9. Không chỉnh nhiều phần OOXML cùng lúc nếu có thể chia thành từng bước nhỏ để kiểm tra.




---

Video

add_movie() là experimental.

Luôn:

kiểm tra file tồn tại;

truyền đúng mime_type;

dùng poster frame nếu có;

không giả định PowerPoint phát được mọi codec;

không giả định file .mp4 luôn dùng codec PowerPoint hỗ trợ.


Ví dụ:

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

Nếu không có poster frame, có thể dùng poster mặc định theo hành vi thư viện, nhưng phải báo rõ.

Nhúng được video không đảm bảo thiết bị đích phát được codec đó.


---

Hình ảnh

Kiểm tra file trước khi chèn:

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

Không dùng exception rộng để che mọi lỗi.

Chỉ fallback khi lỗi đúng là file không tồn tại hoặc ảnh không đọc được và việc bỏ ảnh không làm sai mục tiêu chính.


---

Hyperlink

URL hoặc mailto trên run:

run.hyperlink.address = "https://example.com"

Link tới slide khác:

shape.click_action.target_slide = target_slide

Chỉ tạo link nội bộ sau khi slide đích đã tồn tại.

Sau khi xóa hoặc sắp xếp lại slide, kiểm tra các link nội bộ liên quan.


---

Chart

Dùng API chính thức:

from pptx.chart.data import ChartData

chart_data = ChartData()
chart_data.categories = ["A", "B", "C"]
chart_data.add_series("Series 1", (10, 20, 30))

Không tự sửa chart.xml chỉ để đổi dữ liệu hoặc format mà API hiện tại đã hỗ trợ.

Nếu yêu cầu chart vượt quá API, nói rõ giới hạn trước khi sửa XML.


---

Table

Tạo đúng kích thước ngay từ đầu.

Không tạo bảng lớn rồi xóa hàng hoặc cột bằng private API nếu không cần.

Merge cell chỉ khi layout thật sự yêu cầu.

Không giả định LibreOffice hoặc Canva render merge cell giống PowerPoint hoàn toàn.

Không hack border XML hàng loạt nếu thiết kế không cần border đặc biệt.



---

Kiểm tra sau khi generate

save() thành công không có nghĩa là PowerPoint sẽ mở file mà không Repair.

Mức 1: bắt buộc

Lưu và mở lại bằng python-pptx:

from pptx import Presentation

prs.save(output_path)
verified = Presentation(output_path)

Việc này xác nhận:

package có thể đọc;

XML đủ well-formed để python-pptx parse;

cấu trúc cơ bản chưa bị hỏng nghiêm trọng.


Nó không xác nhận đầy đủ rằng PowerPoint sẽ không Repair animation hoặc transition.

Mức 2: bắt buộc nếu sửa OOXML thủ công

Kiểm tra:

file là ZIP hợp lệ;

toàn bộ XML liên quan parse được;

relationship target tồn tại;

không có relationship ID trùng;

không có timing ID trùng trong slide;

spid trỏ tới shape tồn tại;

không có hai <p:timing> hoặc hai <p:transition> ngoài chủ đích.


Có thể dùng thư viện chuẩn zipfile và lxml đã có trong dependency stack.

Không tạo một hệ thống validator khổng lồ nếu chỉ cần kiểm tra vài file XML vừa chỉnh.

Mức 3: xác nhận PowerPoint thật

Muốn khẳng định:

> File mở sạch và không bị Microsoft PowerPoint Repair



thì phải:

mở file bằng Microsoft PowerPoint desktop; hoặc

dùng một validator OOXML phù hợp có khả năng kiểm tra schema liên quan.


Nếu chưa làm bước này, chỉ được báo:

> File đã qua kiểm tra cấu trúc cơ bản và mở lại thành công bằng python-pptx.



Không được tuyên bố tuyệt đối rằng PowerPoint sẽ không Repair.


---

Khả năng tương thích

Ưu tiên:

1. Microsoft PowerPoint desktop.


2. PowerPoint Mobile.


3. LibreOffice Impress.


4. Canva Import.



Các thành phần thường tương thích tốt:

Text.

Picture.

Basic shape.

Table đơn giản.

Chart phổ biến.

URL hyperlink.


Các thành phần có thể khác nhau giữa nền tảng:

Theme.

Font fallback.

Complex table merge.

Video codec.

Shadow.

Transparency.

Custom XML effects.

Animation.

Transition.

Morph.


Nếu người dùng chủ yếu mở bằng Canva:

ưu tiên text, picture, shape, table và chart;

hạn chế layout phụ thuộc font đặc biệt;

báo trước rằng animation và transition có thể bị bỏ qua;

không cần loại bỏ animation nếu file chủ yếu dùng trong PowerPoint.



---

Workflow khi tạo PowerPoint

1. Đọc yêu cầu.


2. Xác định output:

số slide;

tỷ lệ;

nội dung;

phong cách;

nền tảng mở chính;

có animation, transition hoặc media hay không.



3. Nếu task lớn hoặc mơ hồ, dùng skill spec-driven.


4. Dùng API public của python-pptx trước.


5. Chỉ dùng OOXML cho phần API không hỗ trợ.


6. Không viết hàng loạt script để khám phá thư viện.


7. Chạy script tạo file.


8. Nếu lỗi:

đọc stack trace;

xác định đúng dòng lỗi;

sửa nguyên nhân;

chạy lại.



9. Không retry nguyên trạng.


10. Nếu edit thất bại do old_str not found:

đọc đúng đoạn liên quan;

thử sửa lại một lần;

nếu vẫn thất bại, dùng apply_patch;

không lặp vòng edit → read → edit nhiều lần.



11. Lưu file.


12. Mở lại bằng Presentation(output_path).


13. Nếu đã sửa OOXML, kiểm tra thêm XML và relationships.


14. Chỉ thông báo hoàn thành khi file đã qua verify phù hợp.




---

Không tự khám phá API quá mức

Không tạo nhiều file dạng:

check_api.py.

check_shapes.py.

check_props.py.

inspect_pptx.py.

list_methods.py.

list_enum.py.


Chỉ tạo probe nhỏ khi:

lỗi thực tế phụ thuộc đúng một API;

tài liệu skill không đủ trả lời;

kiểm tra đó trực tiếp giúp sửa lỗi đang gặp.


Sau khi probe xong, xóa file tạm nếu người dùng không cần giữ.

Ưu tiên viết code chính ngắn và chạy thử, thay vì nghiên cứu toàn bộ bề mặt API trước.


---

Simplicity First

Viết minimum code giải quyết đúng yêu cầu.

Không tạo framework cho một file PowerPoint demo.

Không tạo class nếu vài hàm nhỏ đã đủ.

Không viết 900 dòng nếu có thể giải quyết rõ ràng trong 200 đến 300 dòng.

Chỉ tạo helper khi logic được dùng lại hoặc giúp code dễ đọc rõ rệt.

Không thêm tính năng ngoài yêu cầu.

Không tạo cấu hình, plugin system hoặc abstraction không ai yêu cầu.

Không kiểm tra mọi API của thư viện trước khi bắt đầu.

Không biến demo PowerPoint thành một presentation engine tổng quát.


Tự hỏi:

> Một senior engineer có cho rằng giải pháp này quá phức tạp so với yêu cầu không?



Nếu có, đơn giản hóa trước khi tiếp tục.


---

Báo cáo sau khi hoàn thành

Tóm tắt ngắn:

File code đã tạo hoặc sửa.

File .pptx đầu ra.

Các tính năng đã thực hiện.

Các yêu cầu không thực hiện được.

Giới hạn đó thuộc:

API python-pptx;

định dạng PPTX;

môi trường hoặc asset đầu vào.


Cách chạy.

Cách verify.

Mức kiểm tra đã thực hiện:

reopen bằng python-pptx;

kiểm tra OOXML;

mở bằng PowerPoint thật hay chưa.



Không giải thích lại toàn bộ code nếu người dùng không yêu cầu.


---

Kết luận

python-pptx là công cụ ưu tiên, không phải giới hạn tuyệt đối của PowerPoint.

Nếu API chính thức hỗ trợ, dùng API.

Nếu PowerPoint hỗ trợ nhưng python-pptx chưa có API, có thể dùng OOXML khi người dùng thật sự cần.

Animation và transition được phép làm, nhưng phải theo quy trình:

1. Lấy XML mẫu do PowerPoint thật tạo.


2. Clone đúng cấu trúc.


3. Remap ID và spid.


4. Chèn đúng vị trí.


5. Không tạo node trùng.


6. Kiểm tra package và XML.


7. Mở lại bằng python-pptx.


8. Không khẳng định chắc chắn không Repair nếu chưa thử bằng Microsoft PowerPoint thật.



File hợp lệ luôn quan trọng hơn hiệu ứng.
