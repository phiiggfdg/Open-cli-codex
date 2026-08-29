# ── Event system ─────────────────────────────────────────────────────────────
# Mục đích: tách LOGIC (agent_turn, dispatch tool, slash-commands) khỏi
# CÁCH HIỂN THỊ (terminal print ANSI, hay web JSON qua WebSocket).
#
# Nguyên tắc:
#   - Logic không print()/input() trực tiếp nữa — nó gọi emit(...) và,
#     nếu cần chờ người dùng trả lời (permission ask, /setkey...), gọi
#     ask(...) và BLOCK cho tới khi có answer (giống input() cũ).
#   - Có 2 "listener" tiêu thụ event: render_cli (giữ nguyên UX cũ, in ANSI
#     y hệt code gốc) và render_web (dùng khi module 12_web.py chạy, đẩy
#     JSON qua WebSocket).
#   - Mỗi SessionState có 1 EventBus riêng. CLI mặc định gắn render_cli.
#     Khi /web bật, session đó gắn thêm render_web (có thể chạy song song
#     cả hai — người dùng vẫn xem terminal, vừa xem web).
#
# QUAN TRỌNG: file này load NGAY SAU 01_ui.py (cần GREEN/RED/... đã có) và
# TRƯỚC mọi module dùng print() cho luồng model/tool (04,06,07,08,09).
# Không đổi thứ tự trong fw.py nếu không rà lại toàn bộ cross-file globals.

import threading
import uuid as _uuid
import re


class Event:
    """Đơn vị thông điệp trung lập, không biết gì về CLI hay web."""
    __slots__ = ("type", "data", "id")

    def __init__(self, type: str, data: dict | None = None):
        self.type = type
        self.data = data or {}
        self.id = _uuid.uuid4().hex[:12]

    def __repr__(self):
        return f"Event({self.type}, {self.data})"


# ── Danh sách type chuẩn (không bắt buộc, nhưng để tránh gõ sai chuỗi) ───────
EV_TEXT_DELTA      = "text_delta"       # 1 mẩu text model vừa stream ra
EV_THINKING_DELTA  = "thinking_delta"   # 1 mẩu thinking (extended thinking)
EV_TOOL_START      = "tool_start"       # model gọi 1 tool, sắp thực thi
EV_TOOL_END        = "tool_end"         # tool đã chạy xong, có kết quả
EV_TOOL_DENIED     = "tool_denied"      # permission bị từ chối
EV_STEP            = "step"             # bắt đầu 1 step mới trong agent_turn
EV_TURN_START       = "turn_start"       # agent_turn() bắt đầu -- web dùng để
                                          # hiện "đang xử lý" + khoá gửi tin nhắn
                                          # mới, tránh spam trong lúc AI đang chạy
EV_TODO_UPDATE     = "todo_update"      # todos thay đổi
EV_SESSION_META    = "session_meta"     # đổi session/model/agent
EV_INFO            = "info"             # thông báo chung (✓ done, v.v.)
EV_ERROR           = "error"            # lỗi
EV_WARN            = "warn"             # cảnh báo
EV_ASK             = "ask"              # cần người dùng trả lời (blocking)
EV_INTERRUPTED     = "interrupted"      # model bị ngắt giữa chừng
EV_TURN_END        = "turn_end"         # agent_turn() kết thúc hẳn


class PendingAsk:
    """
    Đại diện cho 1 câu hỏi đang chờ người dùng trả lời (permission ask,
    /setkey nhập key mới, xác nhận /delete...). Thay thế input() chặn cứng.

    CLI: gọi .resolve(answer) ngay lập tức sau input() (không có độ trễ).
    Web: server giữ PendingAsk trong dict theo id, trả lời qua
         POST /api/respond/{id} → gọi .resolve(answer) từ thread khác.
    """
    def __init__(self, prompt: str, kind: str = "text", default: str | None = None, extra: dict | None = None):
        self.prompt = prompt
        self.kind = kind          # "text" | "confirm" | "choice"
        self.default = default
        self.extra = extra or {}  # vd {"explanation": "...", "name": "bash"} cho permission ask
        self._event = threading.Event()
        self._answer = None

    def resolve(self, answer):
        self._answer = answer
        self._event.set()

    def wait(self, timeout: float | None = None):
        got = self._event.wait(timeout)
        if not got:
            return self.default
        return self._answer


class EventBus:
    """
    Gắn vào 1 SessionState. Logic gọi bus.emit(...)/bus.ask(...);
    mọi listener đã đăng ký (CLI renderer, web renderer) đều nhận được.
    """
    def __init__(self):
        self._listeners = []   # list[callable(Event)]
        self._ask_handlers = []  # list[callable(PendingAsk) -> None]

    def subscribe(self, fn):
        self._listeners.append(fn)

    def unsubscribe(self, fn):
        if fn in self._listeners:
            self._listeners.remove(fn)

    def subscribe_ask(self, fn):
        """fn(pending: PendingAsk) -> None — phải tự gọi pending.resolve(...)
        (đồng bộ hoặc từ thread khác) khi có câu trả lời."""
        self._ask_handlers.append(fn)

    def emit(self, type: str, **data):
        ev = Event(type, data)
        for fn in list(self._listeners):
            try:
                fn(ev)
            except Exception:
                # 1 listener lỗi không được phép làm gãy agent_turn.
                import traceback
                traceback.print_exc()
        return ev

    def ask(self, prompt: str, kind: str = "text", default=None, timeout=None, extra: dict | None = None):
        """Blocking: gửi PendingAsk tới mọi handler đã đăng ký, đợi 1 trong
        số đó .resolve(). Nếu không có handler nào, trả về default ngay
        (an toàn — không treo agent_turn nếu chưa có UI nào gắn).

        BUG ĐÃ SỬA: trước đây vòng lặp gọi TẤT CẢ handler bất kể handler
        trước đó đã resolve() hay chưa. Kịch bản gặp thật: user bật /web,
        bấm Esc quay lại CLI (disarm() chỉ tắt cờ armed, KHÔNG unsubscribe
        WS khỏi bus -- WS chỉ unsubscribe khi tab đóng hẳn, xem
        _unsubscribe_from ở 12_web.py) nhưng không đóng tab trình duyệt.
        Lần ask() kế tiếp trên CLI (compact, permission-ask, /setkey...):
        cli_ask_handler thấy is_armed()==False nên chạy input() và
        resolve() ngay trên chính thread gọi ask() -- nhưng vòng lặp vẫn
        tiếp tục gọi web_ask_handler (đăng ký sau) dù pending đã có câu
        trả lời, khiến tab web bị "mồ côi" đó bỗng hiện ra 1 card ask vô
        cớ (rõ nhất và đáng ngại nhất là permission-ask cho tool bash) --
        gây hoang mang dù không ảnh hưởng logic thật (giá trị dùng vẫn là
        của CLI, vì pending.wait() chỉ đọc 1 lần ngay sau vòng for này).
        Sửa: dừng gọi handler tiếp theo ngay khi phát hiện đã resolve.
        Không ảnh hưởng multi-tab hợp lệ (nhiều tab đang mở ĐỒNG THỜI,
        chưa ai trả lời) vì lúc đó handler nào cũng được gọi trước khi có
        resolve() nào xảy ra -- chỉ chặn đúng trường hợp resolve xảy ra
        NGAY TRONG handler trước đó (như input() đồng bộ của CLI)."""
        pending = PendingAsk(prompt, kind, default, extra)
        if not self._ask_handlers:
            return default
        for fn in list(self._ask_handlers):
            if pending._event.is_set():
                break
            fn(pending)
        return pending.wait(timeout)


class SessionState:
    """
    Gom mọi biến trước đây là closure-local trong main()/global module-level
    dùng riêng cho 1 phiên hội thoại. CLI giữ 1 instance làm biến local;
    web server giữ nhiều instance theo session_id trong dict.

    Không cố gom HẾT global cũ vào đây ngay (rủi ro vỡ code cũ) — chỉ những
    gì cần thiết để agent_turn/dispatch chạy độc lập theo từng phiên khi có
    nhiều session chạy song song qua web (CLI trước giờ chỉ có 1 session
    tại 1 thời điểm nên dùng global vẫn ổn, nhưng web thì KHÔNG được dùng
    global chung cho _current_agent/_current_sid/_bash_allow_all... vì
    nhiều người/nhiều tab có thể mở nhiều session cùng lúc).
    """
    def __init__(self, conn, sid, model, agent, api_key, messages):
        self.conn = conn
        self.sid = sid
        self.model = model
        self.agent = agent
        self.api_key = api_key
        self.messages = messages

        self.tool_mode = "batch"
        self.thinking_mode = "off"
        self.bash_allow_all = False

        self.bus = EventBus()
        self.lock = threading.RLock()   # 1 turn tại 1 thời điểm cho mỗi session
        self.web_bridge = None  # gán = WebInputBridge() khi /web bật lần đầu
        self.turn_in_progress = False  # True trong suốt agent_turn() — đọc bởi
        # _send_session_init() (12_web.py) để báo đúng busy/idle cho client mới
        # kết nối (vd reload trang giữa lúc agent đang chạy).

    def emit(self, type: str, **data):
        return self.bus.emit(type, **data)

    def ask(self, prompt: str, kind: str = "text", default=None, timeout=None, extra: dict | None = None):
        return self.bus.ask(prompt, kind, default, timeout, extra)


# ── Thread-local "current state" ────────────────────────────────────────────
# agent_turn(state=...) sống ở đầu call stack, nhưng _check_permission() nằm
# sâu trong run_tool()->_dispatch_tool()->_check_permission() (08_undo_dispatch.py)
# — đổi chữ ký cả chuỗi này (nhiều lambda dispatch table) rủi ro vỡ cao hơn lợi
# ích. Dùng thread-local: agent_turn() set current state khi bắt đầu turn,
# _check_permission() đọc lại qua current_state(). Vì mỗi turn chạy trên 1
# thread riêng (CLI: main thread; web: 1 thread/request sau này), an toàn cho
# cả nhiều session song song.
_state_local = threading.local()


def set_current_state(state):
    _state_local.value = state


def current_state():
    return getattr(_state_local, "value", None)


def clear_current_state():
    _state_local.value = None


# ── CLI renderer: nhận Event, in ra ANSI y hệt hành vi cũ ───────────────────
# Đăng ký hàm này vào bus của session khi chạy qua main() (10_main.py) để
# giữ nguyên trải nghiệm terminal, không lộ thay đổi kiến trúc ra người dùng.
_cli_render_flags = {"first_token": True, "first_thinking": True}


def cli_render_reset():
    """Gọi ở đầu mỗi turn (agent_turn) để reset cờ 'đã in AI:/[thinking] chưa'."""
    _cli_render_flags["first_token"] = True
    _cli_render_flags["first_thinking"] = True


def render_cli(ev: Event):
    # ── Im lặng khi web đang armed ───────────────────────────────────────
    # BUG: render_cli LUÔN subscribe cố định vào bus của state (từ đầu
    # main(), không bao giờ unsubscribe). Mọi state.emit(...) -- kể cả khi
    # lệnh đến từ WEB (web_bridge.is_armed()==True, bàn phím CLI đã khoá) --
    # vẫn bị in ra CLI song song, đè lên 4 dòng thông báo gốc của
    # wait_web_mode() (đúng "rác" thấy trong ảnh chụp: /help, cảnh báo
    # /model... tự in ra CLI dù đang dùng qua web, không phải CLI).
    # Sửa: nếu state hiện tại (lấy qua get_cli_state(), định nghĩa ở
    # 12_web.py -- load SAU file này nhưng cùng namespace nên gọi được lúc
    # runtime, xem quy tắc cross-file trong fw.py) có web_bridge đang armed,
    # CLI không in gì cả -- toàn bộ hiển thị nhường cho render_web. Khi
    # user bấm Esc (disarm), render_cli lại in bình thường như cũ.
    try:
        _st = get_cli_state()
    except NameError:
        _st = None
    if _st is not None and getattr(_st, "web_bridge", None) is not None and _st.web_bridge.is_armed():
        return

    t, d = ev.type, ev.data
    if t == EV_THINKING_DELTA:
        if _cli_render_flags["first_thinking"]:
            print(f"\n{DIM}┌─ thinking ─────────────────────{R}")
            print(f"{DIM}│ {R}", end="", flush=True)
            _cli_render_flags["first_thinking"] = False
        # Thụt lề "│ " sau mỗi lần xuống dòng bên trong nội dung thinking,
        # để cả khối luôn nằm gọn trong khung, không lẫn với text chat.
        chunk = d["text"].replace("\n", f"{R}\n{DIM}│ {R}{DIM}")
        print(f"{DIM}{chunk}{R}", end="", flush=True)
    elif t == EV_TEXT_DELTA:
        if _cli_render_flags["first_token"]:
            if not _cli_render_flags["first_thinking"]:
                print(f"\n{DIM}└─────────────────────────────────{R}")
            print(f"\n{GREEN}{BOLD}AI:{R} ", end="", flush=True)
            _cli_render_flags["first_token"] = False
        print(d["text"], end="", flush=True)
    elif t == EV_STEP:
        print(f"{DIM}  ┤ step {d['step']}  ctx ~{d['ctx_est']:,} tok  "
              f"model {d['model']}{R}")
    elif t == EV_TOOL_START:
        icon = TOOL_ICONS.get(d["name"], f"{DIM}⚙")
        print(f"  {icon} {BOLD}{d['name']}{R}  {DIM}{d['preview']}{R}")
    elif t == EV_TOOL_END:
        print(f"  {DIM}╰─ {d['brief']}{'…' if d.get('truncated') else ''}{R}")
    elif t == EV_TOOL_DENIED:
        if d.get("by_user"):
            print(f"  {RED}✗ Denied by user.{R}")
        else:
            print(f"  {RED}✗ {d['name']} denied (agent={d.get('agent')}){R}")
    elif t == EV_INFO:
        if d.get("raw"):
            # Nội dung đã tự có mã màu ANSI riêng (vd HELP) — không bọc thêm
            print(d["text"])
        else:
            print(f"{GREEN}{d['text']}{R}")
    elif t == EV_WARN:
        print(f"{YELLOW}{d['text']}{R}")
    elif t == EV_ERROR:
        print(f"{RED}{d['text']}{R}")
    elif t == EV_INTERRUPTED:
        print(f"{YELLOW}  checkpoint {d.get('checkpoint_id')} saved after interrupt{R}")
    elif t == EV_TURN_END:
        if d.get("summary_line"):
            print(f"{DIM}  {d['summary_line']}{R}")


def cli_ask_handler(pending: PendingAsk):
    """Handler mặc định cho CLI: gọi input() ngay lập tức, y hệt code cũ.

    BUG ĐÃ SỬA: cli_ask_handler được subscribe_ask() 1 LẦN lúc khởi động
    main() và KHÔNG BAO GIỜ unsubscribe khi /web bật (khác với render_cli,
    vốn tự im lặng khi armed -- xem comment ở render_cli phía trên).
    EventBus.ask() gọi TUẦN TỰ mọi handler trong _ask_handlers theo thứ tự
    đăng ký (for fn in list(self._ask_handlers): fn(pending)) -- vì
    cli_ask_handler luôn đăng ký TRƯỚC web_ask_handler (web chỉ subscribe
    khi WS connect, tức là SAU), input() ở đây chặn đồng bộ ngay tại vòng
    lặp đó, khiến web_ask_handler (đứng sau trong list) không bao giờ được
    gọi tới trong khi CLI thật đang armed (không ai gõ input() đó) -- web
    client không bao giờ nhận được message "ask", permission-ask treo vô
    thời hạn (ask() không có timeout mặc định, xem PendingAsk.wait()).
    Thêm vào đó, input() ở đây đọc chung stdin fd với thread _watch_esc
    (12_web.py) đang tty.setraw() + select() trên cùng fd -- tranh chấp
    đọc phím giữa 2 thread, kết quả không xác định.

    Sửa: cli_ask_handler tự phát hiện web_bridge đang armed (giống hệt
    cách render_cli đã làm ở trên, cùng pattern get_cli_state()) và return
    NGAY, không gọi input() và không resolve() -- nhường quyền trả lời
    hoàn toàn cho web_ask_handler (EventBus.ask() vẫn đợi đúng cách qua
    pending.wait(), chỉ cần 1 handler resolve() là đủ). Khi user bấm Esc
    (disarm), CLI lấy lại quyền như cũ, không đổi hành vi gì khác."""
    try:
        _st = get_cli_state()
    except NameError:
        _st = None
    if _st is not None and getattr(_st, "web_bridge", None) is not None and _st.web_bridge.is_armed():
        return
    try:
        explanation = pending.extra.get("explanation") if pending.extra else None
        if explanation:
            print(f"\n  {YELLOW}{'─'*56}{R}")
            for line in explanation.splitlines():
                print(f"  {line}")
            print(f"  {YELLOW}{'─'*56}{R}")
            ans = input(f"  {CYAN}Allow? [y/N/a(ll)]: {R}").strip().lower()
        elif pending.kind == "confirm":
            clean_prompt = pending.prompt.strip()
            clean_prompt = re.sub(r"\s*\[[yY]/[nN]\]:?$", "", clean_prompt)
            hint = "[Y/n]" if (pending.default or "").lower() in ("y", "yes") else "[y/N]"
            ans = input(f"  {CYAN}{clean_prompt}{R} {DIM}{hint}: {R}").strip().lower()
            if not ans:
                ans = pending.default or "n"
        elif pending.kind == "choice":
            print(f"  {CYAN}{pending.prompt}{R}")
            options = pending.extra.get("options") if pending.extra else []
            for i, opt in enumerate(options, 1):
                print(f"    {YELLOW}{i}.{R} {opt}")
            raw = input(f"  {CYAN}Chọn số hoặc gõ trực tiếp: {R}").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                ans = options[int(raw) - 1]
            elif not raw and pending.default is not None:
                ans = pending.default
            else:
                ans = raw
        else:
            prompt_str = pending.prompt
            if not prompt_str.endswith(" ") and not prompt_str.endswith(":"):
                prompt_str += ": "
            ans = input(f"  {CYAN}{prompt_str}{R}").strip()
            if not ans and pending.default is not None:
                ans = pending.default
    except (EOFError, KeyboardInterrupt):
        ans = pending.default
    pending.resolve(ans)


# ── Web input bridge ─────────────────────────────────────────────────────────
# Khi /web bật (dùng CHUNG session CLI đang chạy, không mở session mới —
# quyết định đã chốt), CLI thật bị khoá bàn phím (giống wait_web_mode cũ).
# Vòng lặp chính trong main() không còn gọi thẳng _multiline_input_with_hint
# khi web đang "cầm quyền" — nó gọi get_next_input(state, prompt) bên dưới,
# hàm này tự quyết định lấy từ bàn phím thật hay từ hàng đợi web.
class WebInputBridge:
    def __init__(self):
        self._queue = None
        self._armed = threading.Event()
        # Cờ RIÊNG cho việc ngắt AI đang stream trả lời (KHÁC hẳn _queue ở
        # trên, vốn chỉ dùng cho input dòng lệnh mới giữa các turn). Trước
        # đây push_interrupt() chỉ đẩy vào _queue -- next_line() (chỉ được
        # gọi ở get_next_input(), tức là LÚC ĐANG CHỜ INPUT MỚI) mới đọc
        # được nó, nhưng agent_turn() chạy đồng bộ ngay trên main thread khi
        # AI đang trả lời, main() không hề gọi get_next_input() lúc đó -- vì
        # vậy bấm ^C trên web trong lúc AI đang stream KHÔNG có tác dụng gì,
        # interrupt chỉ nằm im trong _queue tới khi turn xong mới bị next
        # get_next_input() "ăn" nhầm thành 1 dòng input rỗng. Cờ mới này
        # được _stream_response() (09_api_system.py) poll sau mỗi chunk SSE
        # nhận về -- đúng chỗ duy nhất có thể ngắt kịp thời trong lúc stream.
        self._stream_interrupt = threading.Event()
        # Ảnh đi kèm dòng input gần nhất lấy ra từ next_line() — chỉ khác
        # None khi dòng đó tới từ push_line_with_images() (nguồn DUY NHẤT:
        # WS handler /web). Đọc bởi get_next_input() ngay sau next_line().
        self.last_images = None

    def _q(self):
        if self._queue is None:
            import queue as _q
            self._queue = _q.Queue()
        return self._queue

    def arm(self):
        self._armed.set()

    def disarm(self):
        self._armed.clear()
        # Dọn luôn cờ stream interrupt khi disarm (vd bấm Esc trên CLI thật
        # để lấy lại quyền) -- phòng trường hợp có 1 request ngắt còn treo
        # lại chưa kịp bị agent_turn() tiêu thụ (xem clear_stream_interrupt,
        # đây mới là nơi dọn CHÍNH cho trường hợp ^C bấm lúc idle -- xem
        # push_interrupt() bên dưới).
        self._stream_interrupt.clear()

    def is_armed(self):
        return self._armed.is_set()

    def push_line(self, line: str):
        self._q().put(("line", line))

    def push_line_with_images(self, line: str, images: list):
        """Như push_line() nhưng kèm ảnh (chỉ nguồn duy nhất: WS handler
        của /web — xem 12_web.py). Ảnh được đính kèm qua tuple thay vì field
        riêng trên bridge, để tránh race condition nếu có nhiều dòng input
        xếp hàng nhanh liên tiếp (mỗi dòng tự mang đúng ảnh của chính nó,
        không phụ thuộc biến trạng thái chia sẻ có thể bị ghi đè)."""
        self._q().put(("line_img", (line, images)))

    def push_interrupt(self):
        # Set cả 2: cờ stream (đọc bởi _stream_response trong lúc AI đang
        # trả lời -- đây là đường DUY NHẤT thật sự ngắt được AI) VÀ queue cũ
        # (đọc bởi next_line() lúc đang chờ input mới -- main() nhận
        # KeyboardInterrupt ở đó nhưng theo yêu cầu SẼ KHÔNG làm gì cả nếu
        # lúc đó không có gì đang chạy, xem 10_main.py). Nếu rơi vào trường
        # hợp "idle" (không có turn nào đang stream), _stream_interrupt vừa
        # set ở đây sẽ không có ai tiêu thụ ngay -- nó được dọn sạch ở lần
        # agent_turn() kế tiếp (clear_stream_interrupt(), gọi đầu mỗi turn),
        # đảm bảo không ngắt oan turn không liên quan.
        self._stream_interrupt.set()
        self._q().put(("interrupt", None))

    def clear_stream_interrupt(self):
        """Gọi TRƯỚC MỖI TURN MỚI (đầu agent_turn) để đảm bảo không có cờ
        rác sót lại từ 1 lần ^C trước đó bấm lúc idle (không có gì đang
        stream) -- đây là nơi dọn CHÍNH cho trường hợp đó, vì idle ^C không
        còn tự disarm() nữa (theo yêu cầu: ^C lúc idle không làm gì cả)."""
        self._stream_interrupt.clear()

    def consume_stream_interrupt(self) -> bool:
        """True nếu có yêu cầu ngắt đang chờ xử lý (gọi từ vòng lặp đọc
        stream) -- tự clear ngay khi trả về True, mỗi request ngắt chỉ dùng
        được 1 lần, tránh ngắt luôn cả turn kế tiếp do cờ còn sót lại."""
        if self._stream_interrupt.is_set():
            self._stream_interrupt.clear()
            return True
        return False

    def next_line(self):
        """Block tới khi có dòng mới hoặc interrupt, hoặc trả None nếu
        session bị disarm trong lúc chờ (poll mỗi 0.25s). Trả về string
        (giữ nguyên contract cũ — nhiều nơi gọi get_next_input() kỳ vọng
        string thẳng, không phải tuple). Ảnh đi kèm (nếu có, chỉ từ
        push_line_with_images() — nguồn DUY NHẤT là WS handler /web, xem
        12_web.py) được cất tạm vào self.last_images, đọc ra ngay bởi
        get_next_input() SAU LỆNH GỌI next_line() này, trước khi bất kỳ
        dòng nào khác có thể ghi đè (next_line() tiếp theo chỉ chạy sau khi
        caller đã lấy input hiện tại đi xử lý — không có race ở đây vì
        get_next_input() luôn đọc last_images ngay sau khi return)."""
        while True:
            if not self._armed.is_set():
                return None
            try:
                kind, payload = self._q().get(timeout=0.25)
            except Exception:
                continue
            if kind == "interrupt":
                raise KeyboardInterrupt()
            if kind == "line_img":
                text, images = payload
                self.last_images = images
                return text
            self.last_images = None
            return payload


def get_next_input(state, prompt: str):
    """Điểm nối DUY NHẤT thay cho _multiline_input_with_hint trực tiếp trong
    main(). Nếu session có web bridge đang armed, chờ input từ đó (bàn phím
    CLI thật bị khoá lúc này). Ngược lại, hành vi y hệt cũ.

    QUAN TRỌNG: next_line() trả None khi bridge bị disarm giữa lúc đang chờ
    (vd user bấm Esc trên CLI để lấy lại quyền) -- đây KHÔNG phải EOF, không
    được trả None lên main() (main() coi None là EOF/Ctrl-D -> "Goodbye" và
    thoát hẳn CLI, sẽ là bug nghiêm trọng). Khi disarm xảy ra, quyền input
    đã quay lại bàn phím thật -> loop lại và đọc bàn phím ngay, không trả
    None ra ngoài."""
    while True:
        bridge = getattr(state, "web_bridge", None) if state is not None else None
        if bridge is not None and bridge.is_armed():
            line = bridge.next_line()
            if line is None and not bridge.is_armed():
                # Bị disarm trong lúc chờ (không phải EOF thật) -> quyền đã
                # về bàn phím CLI, đọc lại ngay từ đầu vòng lặp.
                continue
            return line
        return _multiline_input_with_hint(prompt)


def get_next_input_images(state):
    """Trả về list ảnh (hoặc None) đi kèm dòng input VỪA LẤY bởi
    get_next_input() ngay trước đó. Gọi hàm này ngay sau get_next_input()
    trong cùng vòng lặp, trước khi gọi lại get_next_input() lần nữa (last_images
    bị next_line() ghi đè ở lần gọi kế tiếp).

    QUAN TRỌNG (gate): chỉ có giá trị khi input đó đến từ WS handler của
    /web (bridge.is_armed() == True tại thời điểm nhận) — bàn phím CLI thật
    không có đường nào gọi push_line_with_images(), nên nhánh else luôn trả
    None. Đây là điểm gác duy nhất đảm bảo CLI không bao giờ vô tình mang
    theo ảnh (xem thiết kế đã chốt: ảnh chỉ tồn tại trong luồng /web)."""
    bridge = getattr(state, "web_bridge", None) if state is not None else None
    if bridge is not None and bridge.is_armed():
        images = getattr(bridge, "last_images", None)
        bridge.last_images = None  # tiêu thụ 1 lần, tránh dính sang turn sau
        return images
    return None


# ── Web renderer: nhận Event, gửi JSON qua WebSocket ─────────────────────────
def make_render_web(send_json):
    """Trả về render_web(ev) gắn với 1 kết nối WS cụ thể."""
    def render_web(ev: Event):
        t, d = ev.type, ev.data
        try:
            send_json({"type": t, "data": d, "id": ev.id})
        except Exception:
            pass
    return render_web


def make_web_ask_handler(send_json, pending_registry):
    """Trả về ask_handler(pending) gắn với 1 kết nối WS. pending_registry là
    dict[str, PendingAsk] dùng chung với WS handler để route câu trả lời từ
    client về đúng PendingAsk."""
    def web_ask_handler(pending: PendingAsk):
        pid = _uuid.uuid4().hex[:12]
        pending_registry[pid] = pending
        try:
            send_json({
                "type": "ask",
                "id": pid,
                "prompt": pending.prompt,
                "kind": pending.kind,
                "default": pending.default,
                "extra": pending.extra,
            })
        except Exception:
            pending.resolve(pending.default)
    return web_ask_handler
