# ── /web: web nối TRỰC TIẾP vào SessionState của CLI đang chạy ──────────────
#
# ĐỔI KIẾN TRÚC (quyết định đã chốt, thay bản PTY-bridge cũ):
# Trước đây /web spawn 1 tiến trình fw.py con riêng trong PTY, trình duyệt
# chỉ là terminal emulator xem lại byte-stream ANSI — bus/Event chỉ sống
# trong process con nên không thể có render_web (JSON, tool card...).
#
# Kiến trúc mới: /web KHÔNG spawn gì cả. Dùng CHUNG session CLI đang chạy
# trong tay bạn ngay lúc này (chung state, chung messages). Khi bật:
#   1. state.web_bridge.arm() -- khoá bàn phím CLI thật (giống wait_web_mode
#      cũ). main() loop đọc input qua get_next_input(state,...) thay vì gọi
#      thẳng _multiline_input_with_hint.
#   2. render_web(ev) được subscribe vào state.bus -- mọi Event gửi qua WS
#      dạng JSON.
#   3. Client gửi {"type":"input","value":".."}/{"type":"interrupt"}/
#      {"type":"answer","id":..,"value":..} qua WS -- server route vào
#      state.web_bridge hoặc pending_registry tương ứng.
#   4. Đóng tab / bấm "quay lại CLI": disarm() -- bàn phím CLI thật lấy lại
#      quyền.
#
# Hệ quả đã xác nhận trước khi làm (Câu 2 = A): lệnh nào CHƯA emit qua
# state.bus (còn print() thẳng -- vd /mcp, phần input()-confirm của /delete)
# sẽ KHÔNG hiện gì trên web nếu gõ qua web, dù vẫn chạy bình thường qua CLI
# thật. Bổ sung dần sau.

import os
import select
import threading
import json
import socket

# Mime ảnh được cả 3 route (OpenAI-compat gốc, Anthropic, AWS Bedrock) chấp
# nhận — khớp đúng _CONVERSE_IMG_FORMATS ở 01b_aws.py (route hẹp nhất, chỉ
# 4 format cố định). Giữ danh sách này đồng bộ với 01b_aws.py nếu sau này
# Bedrock hỗ trợ thêm định dạng.
_SUPPORTED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}

# LỖ HỔNG ĐÃ SỬA (defense in depth): resize ảnh xuống <=1568px cạnh dài
# (xem MAX_IMAGE_DIM, resizeImageIfNeeded() trong web_index.html) CHỈ chạy
# ở JavaScript phía frontend — backend Python trước đây không kiểm tra lại
# kích thước từng ảnh, chỉ giới hạn TỔNG dung lượng 1 message WS (16MB,
# xem _MAX_WS_MESSAGE_BYTES) và số lượng ảnh/turn (6). Ai đó tự nối
# WebSocket thủ công (bỏ qua UI web, vd script/tool khác gọi thẳng endpoint
# WS) có thể gửi ảnh full-res không qua resize — comment ở
# resizeImageIfNeeded() ghi nhận đã từng gặp thật: ảnh chụp màn hình điện
# thoại full-res (~600KB gốc) base64 hoá ra ~800KB text, estimate_tokens()
# (05_session_db.py, CHARS_PER_TOKEN=4) ước tính ra ~200,000 token CHỈ CHO
# 1 ẢNH, đẩy context bar lên 192–222% ngay turn đầu của session gần như
# rỗng. Backend không có PIL/thư viện xử lý ảnh nào (dự án cố tình tối
# giản dependency cho môi trường Termux — không thêm PIL vì cần biên dịch
# native libjpeg/zlib, không chắc có sẵn mọi máy) nên KHÔNG THỂ tự resize
# ảnh ở đây — chỉ có thể CHẶN (từ chối rõ ràng, báo lỗi cho client) ảnh
# vượt ngưỡng hợp lý, thay vì âm thầm chấp nhận rồi gửi thẳng lên API tốn
# token khổng lồ. Ngưỡng chọn: ảnh ĐÃ resize đúng theo MAX_IMAGE_DIM=1568px
# (JPEG q85 hoặc PNG) rơi vào khoảng 100-400KB gốc → base64 133-533KB —
# đặt ngưỡng 2MB base64/ảnh để có biên độ rộng (PNG phức tạp nén kém hơn
# JPEG, ảnh gần 1568px vẫn có thể to hơn ước lượng trung bình) mà vẫn chặn
# chắc chắn được ảnh full-res rõ ràng chưa qua resize.
_MAX_IMAGE_BASE64_CHARS = 2 * 1024 * 1024  # 2MB base64 text / ảnh


# ── Registry: SessionState CLI hiện đang chạy, do main() đăng ký khi gọi
# register_cli_state(state) lúc khởi động. Chỉ 1 phiên tại 1 thời điểm (CLI
# vốn chỉ chạy 1 session -- đúng giả định "dùng chung session, không mở mới").
_cli_state = None
_cli_state_lock = threading.Lock()


def register_cli_state(state):
    """Gọi từ main() ngay sau khi tạo SessionState, để /web biết session
    nào để nối vào."""
    global _cli_state
    with _cli_state_lock:
        _cli_state = state


def get_cli_state():
    with _cli_state_lock:
        return _cli_state



# ── Minimal WebSocket server (stdlib-only, không cần cài thêm gì trên Termux)
# Cài đặt handshake RFC6455 tối giản, đủ dùng cho kênh input/output PTY.
import base64
import hashlib

_WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _ws_accept_key(key: str) -> str:
    sha1 = hashlib.sha1((key + _WS_MAGIC).encode()).digest()
    return base64.b64encode(sha1).decode()


def _ws_send_frame(conn: socket.socket, data: bytes, opcode: int = 0x2):
    """opcode 0x1 = text, 0x2 = binary."""
    length = len(data)
    header = bytearray()
    header.append(0x80 | opcode)
    if length <= 125:
        header.append(length)
    elif length <= 65535:
        header.append(126)
        header += length.to_bytes(2, "big")
    else:
        header.append(127)
        header += length.to_bytes(8, "big")
    try:
        conn.sendall(bytes(header) + data)
    except OSError:
        pass


def _ws_recv_frame(conn: socket.socket, poll_timeout: float = 0.5,
                    frame_timeout: float = 60.0) -> bytes | None:
    """Đọc 1 message WS hoàn chỉnh từ client (luôn masked theo spec), gộp
    mọi continuation frame nếu có. None nếu đóng kết nối.

    QUAN TRỌNG (bug đã sửa): trình duyệt có thể tự chia 1 message lớn
    (payload ảnh base64 vài trăm KB/MB) thành NHIỀU frame vật lý -- frame
    đầu tiên mang opcode thật (0x1 text / 0x2 binary) với FIN=0, các frame
    sau đó mang opcode=0x0 (continuation), frame cuối cùng có FIN=1. Code
    cũ đọc ĐÚNG 1 frame vật lý rồi coi đó là cả message -- với payload lớn
    bị trình duyệt fragment, hàm chỉ trả về PHẦN ĐẦU bị cắt cụt của JSON,
    khiến json.loads ở tầng gọi fail (hoặc tệ hơn, phần còn lại của
    connection bị lệch pha vì các byte của continuation frame sau đó bị
    hiểu nhầm thành header của 1 frame WS mới) -- đây chính là nguyên nhân
    "gửi ảnh thì im lặng tuyệt đối, không log" đã gặp: JSON cụt/lệch pha
    khiến _recv_exact của lần đọc TIẾP THEO đọc trúng padding/rác giữa
    dòng, độ dài suy ra sai lệch (có thể rất lớn hoặc âm), khiến _recv_exact
    treo chờ đủ N byte không bao giờ tới (không timeout vì started_frame đã
    True ngay từ byte đầu) -- và toàn bộ vòng lặp bị treo vô thời hạn ở
    ngay _ws_recv_frame, trước khi có cơ hội chạm tới bất kỳ dòng log nào
    tôi thêm ở tầng gọi.

    Sửa: đọc frame vật lý theo đúng vòng lặp WS chuẩn -- lặp cho tới khi
    gặp FIN=1, gộp payload của mọi frame (opcode gốc + các continuation)
    thành 1 message hoàn chỉnh trước khi trả về.
    """
    started_frame = False

    def _recv_exact(n):
        nonlocal started_frame
        buf = b""
        while len(buf) < n:
            try:
                conn.settimeout(frame_timeout if started_frame else poll_timeout)
            except Exception:
                pass
            try:
                chunk = conn.recv(n - len(buf))
            except socket.timeout:
                if started_frame:
                    continue
                raise
            if not chunk:
                return None
            started_frame = True
            buf += chunk
        return buf

    def _recv_one_physical_frame():
        """Đọc đúng 1 frame vật lý WS, trả (fin, opcode, payload) hoặc None."""
        hdr = _recv_exact(2)
        if hdr is None:
            return None
        b0, b1 = hdr[0], hdr[1]
        fin = bool(b0 & 0x80)
        opcode = b0 & 0x0F
        if opcode == 0x8:  # close
            return None
        masked = b1 & 0x80
        length = b1 & 0x7F
        if length == 126:
            ext = _recv_exact(2)
            if ext is None: return None
            length = int.from_bytes(ext, "big")
        elif length == 127:
            ext = _recv_exact(8)
            if ext is None: return None
            length = int.from_bytes(ext, "big")
        mask = _recv_exact(4) if masked else b"\x00\x00\x00\x00"
        if mask is None:
            return None
        payload = _recv_exact(length)
        if payload is None:
            return None
        if masked:
            payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
        return fin, opcode, payload

    # Giới hạn tổng kích thước 1 message đã gộp (defense in depth). Luồng
    # UI thật (frontend đã resize ảnh xuống <=1568px, tối đa 6 ảnh/turn) chỉ
    # tạo message vài MB -- 16MB dư dả, không ảnh hưởng luồng dùng bình
    # thường. Không có giới hạn này, 1 client tự nối WS thủ công (bỏ qua
    # UI) có thể gửi continuation frame vô hạn, khiến parts tích luỹ RAM
    # không giới hạn (server chỉ bind localhost, không xác thực -- rủi ro
    # thấp trong luồng dùng thật, nhưng chi phí thêm giới hạn này gần như
    # bằng 0 nên vẫn thêm cho chắc).
    _MAX_WS_MESSAGE_BYTES = 16 * 1024 * 1024  # 16MB

    try:
        parts = []
        total_len = 0
        message_opcode = None
        while True:
            result = _recv_one_physical_frame()
            if result is None:
                return None
            fin, opcode, payload = result
            if opcode == 0x9 or opcode == 0xA:
                # ping/pong -- không phải data frame, bỏ qua và đọc tiếp
                # (không reset started_frame: vẫn coi là cùng 1 lượt đọc
                # message đang chờ, không cần poll_timeout ngắn lại).
                continue
            if message_opcode is None:
                message_opcode = opcode
            total_len += len(payload)
            if total_len > _MAX_WS_MESSAGE_BYTES:
                # Vượt giới hạn -- đóng kết nối sạch thay vì tích luỹ thêm
                # RAM vô hạn. Không cần gửi close frame WS chuẩn (client
                # cố tình gửi message khổng lồ bất thường không phải luồng
                # UI hợp lệ), chỉ cần không treo/không leak RAM ở server.
                return None
            parts.append(payload)
            if fin:
                break
            # FIN=0: còn continuation frame tiếp theo -- tiếp tục vòng lặp
            # trong cùng _ws_recv_frame() này (không return, không để tầng
            # ngoài coi phần đã đọc là 1 message xong).
        return b"".join(parts)
    finally:
        try:
            conn.settimeout(poll_timeout)
        except Exception:
            pass


def _ws_handshake(conn: socket.socket, headers: dict) -> bool:
    key = headers.get("sec-websocket-key")
    if not key:
        return False
    accept = _ws_accept_key(key)
    resp = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
    )
    conn.sendall(resp.encode())
    return True


# ── HTTP + WS handler (stdlib http.server, single-threaded per connection) ──
import http.server
import socketserver

_STATIC_INDEX = None  # được set lúc start_web_server từ file cạnh module này


class _Handler(http.server.BaseHTTPRequestHandler):
    fw_path = None  # class-level, set trước khi serve

    def log_message(self, fmt, *args):
        pass  # im lặng — không làm loãng terminal CLI chính

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            body = _STATIC_INDEX.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/ws"):
            self._handle_ws()
            return
        self.send_response(404)
        self.end_headers()

    def _handle_ws(self):
        headers = {k.lower(): v for k, v in self.headers.items()}
        if headers.get("upgrade", "").lower() != "websocket":
            self.send_response(400)
            self.end_headers()
            return
        conn = self.connection
        if not _ws_handshake(conn, headers):
            return

        state = get_cli_state()
        if state is None:
            # Chưa có session CLI nào đăng ký (không nên xảy ra vì /web chỉ
            # gọi được từ trong main() sau khi register_cli_state đã chạy) --
            # đóng kết nối sạch thay vì crash thread.
            try:
                conn.close()
            except Exception:
                pass
            return

        send_lock = threading.Lock()

        def send_json(obj):
            data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
            with send_lock:
                _ws_send_frame(conn, data, opcode=0x1)

        pending_registry = {}
        render_web = make_render_web(send_json)
        ask_handler = make_web_ask_handler(send_json, pending_registry)

        def _subscribe_to(st):
            """Gắn listener vào state hiện tại + đảm bảo có web_bridge."""
            if st.web_bridge is None:
                st.web_bridge = WebInputBridge()
            st.bus.subscribe(render_web)
            st.bus.subscribe_ask(ask_handler)

        def _unsubscribe_from(st):
            st.bus.unsubscribe(render_web)
            try:
                st.bus._ask_handlers.remove(ask_handler)
            except (ValueError, AttributeError):
                pass

        def _send_session_init(st):
            try:
                send_json({
                    "type": "session_init",
                    "data": {
                        "sid": st.sid,
                        "model": st.model,
                        "agent": st.agent,
                        "messages": st.messages,
                        # BUG ĐÃ SỬA: _vision_support_get()/_vision_support_set()
                        # (09_api_system.py) đã ghi cache đúng mỗi khi 1 turn có
                        # ảnh thành công/thất bại, nhưng CHƯA TỪNG có nơi nào gọi
                        # _vision_support_get() để đọc lại -- cache chỉ ghi,
                        # không đọc. Hệ quả: mỗi lần connect WS mới (hoặc /sessions
                        # đổi qua model đã biết chắc KHÔNG hỗ trợ ảnh từ trước),
                        # maybeResetVisionBlock() ở frontend luôn mở khoá nút ảnh
                        # vô điều kiện -- người dùng phải tốn 1 lần gửi ảnh thật,
                        # đợi lỗi HTTP xảy ra lại thì mới bị khoá lại, dù thông
                        # tin này đã có sẵn trong config.json. Gửi kèm giá trị đã
                        # biết (None nếu chưa từng thử) để frontend tự quyết định
                        # khoá ngay từ đầu, không cần đợi thử lại.
                        "vision_support": _vision_support_get(st.model),
                        # /codeweb: phục hồi panel preview khi reload trang/
                        # reconnect WS -- xem codeweb_get_session_preview_state()
                        # ở 13_codeweb.py + comment ở "codeweb_preview_ack" phía
                        # trên (nơi state này được ghi lại mỗi khi client báo
                        # 1 preview vừa pass). Rỗng nếu session chưa từng có
                        # preview nào pass hoặc chưa phải codeweb.
                        "codeweb_preview": codeweb_get_session_preview_state(st.sid),
                    },
                })
            except Exception:
                pass

        _subscribe_to(state)
        _send_session_init(state)

        # Timeout ngắn để vòng lặp có cơ hội kiểm tra định kỳ xem state CLI
        # có bị đổi không (vd /sessions tạo SessionState mới) -- nếu có,
        # unsubscribe khỏi bus cũ và subscribe lại vào bus mới, tránh kết
        # nối WS "mồ côi" nói chuyện với 1 session đã không còn hoạt động.
        try:
            conn.settimeout(0.5)
        except Exception:
            pass

        stop = threading.Event()

        try:
            while not stop.is_set():
                try:
                    payload = _ws_recv_frame(conn)
                except socket.timeout:
                    # Không có message mới trong 0.5s -- cơ hội để kiểm tra
                    # đổi session, rồi quay lại chờ tiếp.
                    current = get_cli_state()
                    if current is not None and current is not state:
                        _unsubscribe_from(state)
                        state = current
                        _subscribe_to(state)
                        _send_session_init(state)
                    continue
                except Exception:
                    # BẤT KỲ exception nào khác socket.timeout ở đây (vd lỗi
                    # trong chính _ws_recv_frame) TRƯỚC ĐÂY không được bắt --
                    # nó bay thẳng ra khỏi vòng while, xuyên qua finally, làm
                    # chết lặng lẽ thread xử lý connection này (ThreadingHTTPServer
                    # không tự log exception của thread con ra đâu cả) --
                    # đúng hiện tượng "im lặng tuyệt đối, không dấu vết" khi
                    # gửi ảnh lớn. Đóng kết nối sạch thay vì để thread chết
                    # vô hình -- client sẽ tự reconnect (xem ws.onclose ở
                    # web_index.html).
                    break
                if payload is None:
                    break
                try:
                    msg = json.loads(payload.decode("utf-8"))
                except Exception:
                    continue
                mtype = msg.get("type")
                try:
                    if mtype == "input":
                        images = msg.get("images")
                        if images:
                            # Validate tối thiểu: chỉ nhận list dict có "data"
                            # (base64) + "mime" hợp lệ — bỏ qua entry rác thay
                            # vì crash cả turn. Giới hạn số ảnh/turn để tránh
                            # 1 client ác ý hoặc lỗi UI gửi hàng trăm ảnh làm
                            # nổ payload/token trong 1 request.
                            candidate_images = [
                                im for im in images
                                if isinstance(im, dict) and im.get("data") and im.get("mime")
                            ][:6]
                            # FIX: trước đây mọi mime được chấp nhận ở đây rồi
                            # trôi xuống tận adapter (01b_aws.py/01c_anthropic.py)
                            # mới xử lý — Bedrock âm thầm bỏ qua mime lạ
                            # (silent drop, AI không biết có ảnh), còn
                            # Anthropic gửi thẳng mime lạ lên API thật, gây lỗi
                            # 400 bị hiểu nhầm thành "model không hỗ trợ vision"
                            # (_is_vision_error ở 09_api_system.py), làm sai
                            # cache vision_support cho model đó vĩnh viễn dù
                            # model hỗ trợ ảnh bình thường. Lọc mime KHÔNG hợp
                            # lệ NGAY TẠI ĐÂY — sớm nhất có thể — và báo lại
                            # cho client biết rõ, thay vì để lỗi trôi xuống
                            # tầng dưới rồi bị hiểu sai nguyên nhân.
                            clean_images = [im for im in candidate_images
                                             if im.get("mime", "").lower() in _SUPPORTED_IMAGE_MIMES]
                            n_rejected = len(candidate_images) - len(clean_images)
                            if n_rejected:
                                state.emit(EV_WARN, text=(
                                    f"{n_rejected} ảnh bị bỏ qua do định dạng không hỗ trợ "
                                    f"(chỉ hỗ trợ: {', '.join(sorted(_SUPPORTED_IMAGE_MIMES))})."))
                            # LỖ HỔNG ĐÃ SỬA: chặn ảnh base64 quá lớn (chưa
                            # qua resize đúng cách, hoặc client bỏ qua UI web
                            # gửi thẳng ảnh full-res) — xem giải thích đầy đủ
                            # ở _MAX_IMAGE_BASE64_CHARS phía trên. Lọc SAU
                            # bước mime, TRƯỚC khi đưa vào turn — ảnh bị chặn
                            # ở đây không bao giờ tới _strip_old_images/
                            # estimate_tokens hay gọi API thật, tránh tốn
                            # token khổng lồ chỉ để rồi phát hiện muộn.
                            _n_before_size_filter = len(clean_images)
                            clean_images = [im for im in clean_images
                                             if len(im.get("data", "")) <= _MAX_IMAGE_BASE64_CHARS]
                            _n_oversized = _n_before_size_filter - len(clean_images)
                            if _n_oversized:
                                _mb = _MAX_IMAGE_BASE64_CHARS / (1024 * 1024)
                                state.emit(EV_WARN, text=(
                                    f"{_n_oversized} ảnh bị bỏ qua vì quá lớn "
                                    f"(vượt {_mb:.0f}MB sau mã hoá — ảnh chưa được thu nhỏ "
                                    f"đúng cách, thử chụp/chọn ảnh khác hoặc giảm độ phân "
                                    f"giải trước khi gửi)."))
                        else:
                            clean_images = None
                        if clean_images:
                            state.web_bridge.push_line_with_images(
                                str(msg.get("value", "")), clean_images)
                        else:
                            state.web_bridge.push_line(str(msg.get("value", "")))
                    elif mtype == "interrupt":
                        state.web_bridge.push_interrupt()
                    elif mtype == "answer":
                        pid = msg.get("id")
                        pending = pending_registry.pop(pid, None)
                        if pending is not None:
                            pending.resolve(msg.get("value"))
                    elif mtype == "codeweb_preview_ack":
                        # /codeweb: JS báo NGƯỢC lại server rằng 1 preview (auto
                        # HOẶC thủ công) vừa PASS ở phía client -- server không
                        # tự biết kết quả check (chạy trong iframe sandbox phía
                        # trình duyệt), nên cần tin nhắn nhỏ này để LƯU LẠI state
                        # (path + html) cho _send_session_init() gửi lại khi
                        # reload trang/reconnect WS. Không round-trip qua
                        # ask()/pending_registry -- không ai đang chờ trả lời,
                        # đây chỉ là ghi cache, xem codeweb_remember_preview_ack()
                        # ở 13_codeweb.py.
                        codeweb_remember_preview_ack(
                            state, msg.get("path", ""), msg.get("html", ""))
                    # các type khác (vd resize) -- không còn PTY thật, bỏ qua an toàn
                except Exception:
                    # Lớp bắt tổng: trước đây bất kỳ lỗi nào ở đây (vd push_line_with_images
                    # ném exception vì lý do chưa lường hết) sẽ bay ra khỏi while,
                    # làm chết lặng lẽ thread WS -- không log, không báo UI, y hệt
                    # hiện tượng "im lặng tuyệt đối" đã gặp. Nuốt lỗi ở đây để
                    # vòng lặp tiếp tục phục vụ các message sau, thay vì để cả
                    # kết nối chết theo 1 message lỗi.
                    pass
        finally:
            stop.set()
            _unsubscribe_from(state)


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


_server_instance = None
_server_thread = None
_server_addr = None  # (host, port) của server đang chạy, None nếu chưa start


def start_web_server(fw_path: str, host: str = "127.0.0.1", port: int = 8765):
    """Khởi động server local phục vụ trang web + WS bridge tới PTY chạy fw.py.
    Gọi từ lệnh /web trong 10_main.py. An toàn gọi nhiều lần — nếu đã chạy,
    trả về (host, port) hiện tại mà không khởi tạo lại."""
    global _server_instance, _server_thread, _STATIC_INDEX, _server_addr

    if _server_instance is not None:
        return _server_addr

    # QUAN TRỌNG: __file__ trong namespace chung là path của fw.py (module
    # loader set), KHÔNG PHẢI path của chính 12_web.py — vì mọi module exec()
    # chung 1 namespace (xem fw.py:_load_modules). Vì vậy không thể dùng
    # os.path.abspath(__file__) ở đây để tìm file cạnh 12_web.py; phải suy
    # ra từ fw_path (path fw.py thật) được truyền vào từ nơi gọi.
    fw_dir = os.path.dirname(os.path.abspath(fw_path))
    candidates = [
        os.path.join(fw_dir, ".fw_data", "src", "web_index.html"),
        os.path.join(fw_dir, "web_index.html"),  # trường hợp fw_path đã là .fw_data/src/fw.py
    ]
    static_path = next((c for c in candidates if os.path.exists(c)), candidates[0])
    try:
        with open(static_path, "r", encoding="utf-8") as f:
            _STATIC_INDEX = f.read()
    except Exception:
        _STATIC_INDEX = "<html><body>web_index.html not found</body></html>"

    _Handler.fw_path = fw_path
    _server_instance = _ThreadingHTTPServer((host, port), _Handler)
    _server_thread = threading.Thread(target=_server_instance.serve_forever, daemon=True)
    _server_thread.start()
    _server_addr = (host, port)
    return _server_addr


def web_server_running() -> bool:
    return _server_instance is not None


def web_server_addr():
    """Trả về (host, port) của server đang chạy, hoặc None nếu chưa start."""
    return _server_addr


# ── Chế độ "đang chạy web": chặn ô nhập CLI chính, Esc để quay lại ──────────
#
# BUG ĐÃ SỬA (quan trọng): bản trước wait_web_mode() tự nó dùng stdin.read(1)
# chặn cứng ngay tại đây để canh phím Esc/Ctrl-C -- nghĩa là hàm này KHÔNG
# BAO GIỜ return cho tới khi user bấm Esc trên CLI thật. Trong khi đó, việc
# "lấy dòng user gõ trên web rồi gọi agent_turn" nằm ở vòng lặp while True
# trong main() (qua get_next_input), vòng lặp đó chỉ chạy lại được SAU KHI
# wait_web_mode() return. Kết quả: gõ trên web bị "cất vào hàng đợi" nhưng
# không ai từng lấy ra để hỏi AI -- web đứng im vĩnh viễn.
#
# Sửa: việc "canh phím Esc CLI" chuyển sang 1 thread nền riêng, không chặn.
# wait_web_mode() arm() bridge rồi return NGAY, để main() loop tiếp tục chạy
# get_next_input -> agent_turn bình thường (nhận input từ web). Thread nền
# chỉ có nhiệm vụ duy nhất: đọc phím CLI thật, phát hiện Esc/Ctrl-C thì
# disarm() bridge (lúc đó get_next_input tự rơi về đọc bàn phím CLI, logic
# này đã có sẵn và đúng từ trước, không đổi gì thêm ở đó).
def wait_web_mode(state, host: str, port: int, color_fns=None):
    """
    Arm state.web_bridge rồi return ngay (không chặn) -- vòng lặp CLI chính
    (main(), qua get_next_input) chạy tiếp bình thường và nhận input từ web.
    Một thread nền riêng canh phím Esc/Ctrl-C trên CLI thật; khi phát hiện,
    tự disarm() để trả quyền input lại cho bàn phím CLI. Server + WS vẫn
    chạy nền suốt, không đổi.
    """
    import sys as _sys
    if state.web_bridge is None:
        state.web_bridge = WebInputBridge()
    state.web_bridge.arm()
    G = (color_fns or {}).get("GREEN", "")
    DIMc = (color_fns or {}).get("DIM", "")
    Rc = (color_fns or {}).get("R", "")

    msg = (
        f"\n  {G}◈ Web UI đang chạy: http://{host}:{port}/{Rc}\n"
        f"  {DIMc}Ô nhập CLI tạm khoá — thao tác trên trình duyệt.{Rc}\n"
        f"  {DIMc}Nhấn Esc để quay lại CLI (web server vẫn chạy nền).{Rc}\n"
        f"  {DIMc}(Web UI vẫn nhận lệnh và AI vẫn trả lời trong lúc này.){Rc}\n"
    )
    print(msg)

    if not _sys.stdin.isatty():
        # Không có TTY thật (vd đang test/piped) -- không thể raw-read để
        # canh Esc. Bridge vẫn armed, web vẫn hoạt động bình thường; chỉ là
        # không có cách Esc để thoát qua CLI trong môi trường không TTY này.
        return

    import termios, tty as _tty
    fd = _sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except Exception:
        return

    def _watch_esc():
        # QUAN TRỌNG: nếu setraw/tcgetattr lỗi ngay khi thread bắt đầu (vd
        # terminal lạ, PTY không đầy đủ controlling terminal -- gặp thật khi
        # test: "Inappropriate ioctl for device"), đây là lỗi THIẾT LẬP việc
        # theo dõi phím Esc, KHÔNG PHẢI tín hiệu Esc thật từ user. Trước đây
        # lỗi này bị nuốt rồi rơi thẳng vào finally -> disarm() ngay lập tức,
        # khiến web bridge tắt trước khi user kịp dùng gì. Giờ phân biệt rõ:
        # lỗi setup (chưa vào được vòng theo dõi) -> KHÔNG disarm, chỉ bỏ
        # qua tính năng "Esc để thoát" trong phiên này, web vẫn hoạt động
        # bình thường. Chỉ disarm khi thực sự nhận được Esc/Ctrl-C hoặc lỗi
        # xảy ra SAU KHI đã vào vòng theo dõi (terminal bị đóng giữa chừng).
        entered_loop = False
        try:
            _tty.setraw(fd)
            entered_loop = True
            while state.web_bridge.is_armed():
                r, _, _ = select.select([fd], [], [], 0.25)
                if fd not in r:
                    continue
                ch = _sys.stdin.read(1)
                if ch == "\x1b":
                    r2, _, _ = select.select([fd], [], [], 0.05)
                    if fd in r2:
                        nxt = _sys.stdin.read(1)
                        if nxt == "[":
                            _sys.stdin.read(1)  # nuốt phần còn lại của arrow-key
                    state.web_bridge.disarm()
                    break
                if ch == "\x03":  # Ctrl-C
                    state.web_bridge.disarm()
                    break
        except Exception:
            if entered_loop:
                # Lỗi xảy ra khi đang theo dõi (vd terminal đóng đột ngột) --
                # coi như mất khả năng theo dõi, an toàn nhất là trả quyền
                # về CLI (disarm) để không kẹt input ở đâu không rõ.
                state.web_bridge.disarm()
            # else: lỗi ngay lúc setup -> không disarm, xem docstring trên.
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass
            if not state.web_bridge.is_armed():
                print(f"\n  {DIMc}Đã quay lại CLI.{Rc}\n")

    t = threading.Thread(target=_watch_esc, daemon=True)
    t.start()
    # Return ngay -- KHÔNG join thread. main() loop tiếp tục chạy song song,
    # get_next_input() sẽ lấy input từ web_bridge (armed) cho tới khi thread
    # nền này disarm() nó.
