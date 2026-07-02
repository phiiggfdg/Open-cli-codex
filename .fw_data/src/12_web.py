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


def _ws_recv_frame(conn: socket.socket) -> bytes | None:
    """Đọc 1 frame WS từ client (luôn masked theo spec). None nếu đóng kết nối."""
    def _recv_exact(n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    hdr = _recv_exact(2)
    if hdr is None:
        return None
    b0, b1 = hdr[0], hdr[1]
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
    return payload


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
                if payload is None:
                    break
                try:
                    msg = json.loads(payload.decode("utf-8"))
                except Exception:
                    continue
                mtype = msg.get("type")
                if mtype == "input":
                    state.web_bridge.push_line(str(msg.get("value", "")))
                elif mtype == "interrupt":
                    state.web_bridge.push_interrupt()
                elif mtype == "answer":
                    pid = msg.get("id")
                    pending = pending_registry.pop(pid, None)
                    if pending is not None:
                        pending.resolve(msg.get("value"))
                # các type khác (vd resize) -- không còn PTY thật, bỏ qua an toàn
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
