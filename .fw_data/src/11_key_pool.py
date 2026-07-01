# ##== KEY POOL ==##
# Xoay nhiều API key trong CÙNG 1 provider khi dính lỗi 429 (rate-limit/quota).
#
# QUAN TRỌNG — khác biệt 429 vs lỗi server (500/501/502/503/504):
#   429 = KEY này bị giới hạn (quota/rate) → đổi sang key khác trong pool
#         thường giải quyết được ngay, không cần chờ.
#   5xx = SERVER/PROVIDER đang lỗi → mọi key gọi vào đều dính y hệt, đổi key
#         vô nghĩa. Nhánh 5xx ở 09_api_system.py giữ nguyên hành vi cũ
#         (retry với backoff, CÙNG 1 key) — module này không đụng vào đó.
#
# Model đã chọn (choose_model) không đổi khi xoay key — pool chỉ thay
# Authorization, không thay "model" trong payload.
#
# Lưu trữ: config.json[f"{config_key}_pool"] = list[dict], mỗi phần tử:
#   {"key": str, "fail_count": int, "cooldown_until": float epoch, "last_used": float}
# Key đơn cũ (config.json[config_key] = "xxx") vẫn được đọc nguyên trạng bởi
# get_api_key() (09_api_system.py, không sửa) — KHÔNG phá tương thích ngược.
# Pool chỉ là lớp bổ sung: nếu chưa có "<config_key>_pool", tự coi key đơn
# hiện tại là phần tử đầu tiên (lazy migrate, không cần script riêng).
#
# THREAD-SAFETY: 10_main.py chạy _auto_rename_session trong 1 thread riêng
# (threading.Thread, gọi _call_simple song song với main loop). save_config()
# ghi thẳng file, không lock — 2 thread cùng đọc-sửa-ghi pool gần như đồng
# thời có thể mất update của 1 bên (lost update, read-modify-write race).
# Xác suất thấp (rename chỉ chạy 1 lần/session, timeout 15s) nhưng có thật.
# Dùng RLock module-level bọc quanh mọi read-modify-write để tránh race.
_pool_lock = threading.RLock()

_KEY_COOLDOWN_DEFAULT = 60.0   # giây — dùng khi 429 không kèm Retry-After
_KEY_POOL_STRATEGIES  = ("round_robin", "fill_first")


def _pool_config_key(prov_key: str | None = None) -> str:
    """Tên field trong config.json chứa pool, vd 'fireworks_api_key_pool'."""
    prov = PROVIDERS[prov_key] if prov_key else _prov()
    return prov["config_key"] + "_pool"


def _pool_load(prov_key: str | None = None) -> list[dict]:
    """
    Load pool của 1 provider. Nếu chưa có pool nhưng có key đơn legacy,
    tự tạo pool 1 phần tử từ key đó (migrate ngầm, không ghi file cho tới
    khi thật sự cần — tránh side-effect khi chỉ đọc).
    """
    prov_key = prov_key or _active_provider
    prov = PROVIDERS[prov_key]
    cfg = load_config()
    pool = cfg.get(_pool_config_key(prov_key))
    if pool:
        return pool
    # Chưa có pool → thử migrate từ key đơn (env hoặc config)
    legacy = cfg.get(prov["config_key"], "").strip()
    if not legacy:
        legacy = os.environ.get(prov["env_key"], "").strip()
    if legacy:
        return [{"key": legacy, "fail_count": 0, "cooldown_until": 0.0, "last_used": 0.0}]
    return []


def _pool_save(prov_key: str, pool: list[dict]):
    cfg = load_config()
    cfg[_pool_config_key(prov_key)] = pool
    save_config(cfg)


def _pool_strategy(prov_key: str | None = None) -> str:
    cfg = load_config()
    return cfg.get(f"{_pool_config_key(prov_key)}_strategy", "round_robin")


def _pool_mask(key: str) -> str:
    """Ẩn phần giữa key khi hiển thị, giống format /setkey đang dùng."""
    if len(key) <= 12:
        return key[:2] + "..." + key[-2:]
    return f"{key[:8]}...{key[-4:]}"


def _pool_available(pool: list[dict], now: float | None = None) -> list[dict]:
    """Lọc các entry không còn bị cooldown."""
    now = now if now is not None else time.time()
    return [e for e in pool if e.get("cooldown_until", 0) <= now]


def pool_get_current(prov_key: str | None = None) -> str | None:
    """
    Trả về key nên dùng NGAY LÚC NÀY theo strategy đã chọn, ưu tiên key
    không cooldown. Dùng khi bắt đầu 1 request mới (không phải khi retry
    429 giữa chừng — retry dùng pool_rotate_after_429 bên dưới).
    """
    with _pool_lock:
        prov_key = prov_key or _active_provider
        pool = _pool_load(prov_key)
        if not pool:
            return None
        avail = _pool_available(pool)
        if avail:
            # Có key rảnh thật → sort theo strategy như cũ.
            if _pool_strategy(prov_key) == "fill_first":
                avail.sort(key=lambda e: e.get("fail_count", 0))
            else:  # round_robin: ưu tiên key lâu chưa dùng nhất
                avail.sort(key=lambda e: e.get("last_used", 0))
            return avail[0]["key"]
        # Hết key rảnh → chọn key sắp hết cooldown SỚM NHẤT (không phải
        # key lâu chưa dùng nhất — 2 tiêu chí khác nhau, dùng last_used ở
        # đây có thể trả về đúng key còn cooldown dài nhất).
        soonest = min(pool, key=lambda e: e.get("cooldown_until", 0))
        return soonest["key"]


def pool_mark_success(current_key: str, prov_key: str | None = None):
    """Gọi API thành công → giảm fail_count (decay), cập nhật last_used."""
    with _pool_lock:
        prov_key = prov_key or _active_provider
        pool = _pool_load(prov_key)
        if not pool:
            return
        changed = False
        for e in pool:
            if e["key"] == current_key:
                e["fail_count"] = max(0, e.get("fail_count", 0) - 1)
                e["last_used"]  = time.time()
                changed = True
                break
        if changed:
            _pool_save(prov_key, pool)


def pool_rotate_after_429(current_key: str, retry_after: float | None,
                           prov_key: str | None = None) -> str | None:
    """
    Gọi khi vừa dính HTTP 429 với current_key. Đánh cooldown cho key đó,
    rồi trả về 1 key KHÁC đang rảnh trong pool (None nếu không có / pool
    chỉ có 1 key → caller tự rơi về nhánh sleep-and-retry cũ).
    """
    with _pool_lock:
        prov_key = prov_key or _active_provider
        pool = _pool_load(prov_key)
        if len(pool) <= 1:
            # Chỉ 1 key (hoặc chưa cấu hình pool) — không có gì để xoay.
            # Vẫn ghi cooldown để lần request kế (sau khi hết retry ở đây)
            # không vội đấm lại đúng key này ngay lập tức nếu caller gọi lại.
            if pool:
                pool[0]["cooldown_until"] = time.time() + (retry_after or _KEY_COOLDOWN_DEFAULT)
                pool[0]["fail_count"] = pool[0].get("fail_count", 0) + 1
                _pool_save(prov_key, pool)
            return None

        now = time.time()
        for e in pool:
            if e["key"] == current_key:
                e["cooldown_until"] = now + (retry_after or _KEY_COOLDOWN_DEFAULT)
                e["fail_count"] = e.get("fail_count", 0) + 1
                break
        _pool_save(prov_key, pool)

        others = [e for e in pool if e["key"] != current_key and e.get("cooldown_until", 0) <= now]
        if not others:
            return None
        others.sort(key=lambda e: e.get("last_used", 0))
        return others[0]["key"]


def pool_rotate_after_429_verbose(current_key: str, retry_after: float | None,
                                   prov_key: str | None = None) -> dict:
    """
    Bản chi tiết của pool_rotate_after_429 — dùng riêng cho mục đích LOG,
    không đổi hành vi xoay key (vẫn gọi đúng logic cooldown/chọn key như
    bản gốc). Trả về dict đủ thông tin để in log rõ ràng:

        {
            "rotated": bool,              # có xoay được sang key khác không
            "old_index": int,             # số thứ tự (1-based) của key vừa 429
            "old_mask": str,              # key vừa 429, đã che
            "new_key": str | None,        # key mới thật (để caller dùng gọi API)
            "new_index": int | None,      # số thứ tự key mới
            "new_mask": str | None,       # key mới, đã che
            "free_count": int,            # số key đang rảnh SAU khi xoay (không tính key vừa 429)
            "total": int,                 # tổng số key trong pool
            "soonest_index": int | None,  # nếu hết key rảnh: key nào hết cooldown sớm nhất
            "soonest_mask": str | None,
            "soonest_wait": float | None, # còn bao nhiêu giây nữa key đó rảnh
        }

    Không dùng hàm này để lấy key thật cho request — vẫn gọi
    pool_rotate_after_429() như cũ cho việc đó, hàm này chỉ để log.
    Gọi 2 hàm liên tiếp là AN TOÀN: cooldown/fail_count được ghi lại bằng
    key nên lần gọi thứ 2 (idempotent theo current_key) chỉ cập nhật lại
    đúng entry đó, không tạo side-effect khác hay xoay thêm lần nữa.
    """
    with _pool_lock:
        prov_key = prov_key or _active_provider
        pool = _pool_load(prov_key)
        total = len(pool)

        old_index = None
        for i, e in enumerate(pool, start=1):
            if e["key"] == current_key:
                old_index = i
                break

        result = {
            "rotated": False, "old_index": old_index,
            "old_mask": _pool_mask(current_key),
            "new_key": None, "new_index": None, "new_mask": None,
            "free_count": 0, "total": total,
            "soonest_index": None, "soonest_mask": None, "soonest_wait": None,
        }

        if total <= 1:
            if pool:
                pool[0]["cooldown_until"] = time.time() + (retry_after or _KEY_COOLDOWN_DEFAULT)
                pool[0]["fail_count"] = pool[0].get("fail_count", 0) + 1
                _pool_save(prov_key, pool)
                result["soonest_index"] = 1
                result["soonest_mask"] = _pool_mask(pool[0]["key"])
                result["soonest_wait"] = retry_after or _KEY_COOLDOWN_DEFAULT
            return result

        now = time.time()
        for e in pool:
            if e["key"] == current_key:
                e["cooldown_until"] = now + (retry_after or _KEY_COOLDOWN_DEFAULT)
                e["fail_count"] = e.get("fail_count", 0) + 1
                break
        _pool_save(prov_key, pool)

        others = [e for e in pool if e["key"] != current_key]
        free = [e for e in others if e.get("cooldown_until", 0) <= now]
        result["free_count"] = len(free)

        if free:
            free.sort(key=lambda e: e.get("last_used", 0))
            chosen = free[0]
            result["rotated"] = True
            result["new_key"] = chosen["key"]
            result["new_mask"] = _pool_mask(chosen["key"])
            result["new_index"] = next(
                i for i, e in enumerate(pool, start=1) if e["key"] == chosen["key"])
        else:
            # Hết key rảnh — tìm key nào hết cooldown sớm nhất (kể cả key
            # vừa 429, vì có thể retry_after của nó ngắn hơn key khác).
            soonest = min(pool, key=lambda e: e.get("cooldown_until", 0))
            result["soonest_index"] = next(
                i for i, e in enumerate(pool, start=1) if e["key"] == soonest["key"])
            result["soonest_mask"] = _pool_mask(soonest["key"])
            result["soonest_wait"] = max(0.0, soonest.get("cooldown_until", 0) - now)

        return result


def pool_add_key(key: str, prov_key: str | None = None) -> int:
    """Thêm 1 key vào pool. Trả về số lượng key trong pool sau khi thêm."""
    with _pool_lock:
        prov_key = prov_key or _active_provider
        pool = _pool_load(prov_key)
        if any(e["key"] == key for e in pool):
            return len(pool)  # đã có, không thêm trùng
        pool.append({"key": key, "fail_count": 0, "cooldown_until": 0.0, "last_used": 0.0})
        _pool_save(prov_key, pool)
        return len(pool)


def pool_remove_key(index: int, prov_key: str | None = None) -> str | None:
    """Xoá key theo index (1-based, khớp thứ tự hiển thị /listkeys). Trả về key đã xoá."""
    with _pool_lock:
        prov_key = prov_key or _active_provider
        pool = _pool_load(prov_key)
        if not (1 <= index <= len(pool)):
            return None
        removed = pool.pop(index - 1)
        _pool_save(prov_key, pool)
        return removed["key"]


def pool_set_strategy(strategy: str, prov_key: str | None = None) -> bool:
    if strategy not in _KEY_POOL_STRATEGIES:
        return False
    with _pool_lock:
        prov_key = prov_key or _active_provider
        cfg = load_config()
        cfg[f"{_pool_config_key(prov_key)}_strategy"] = strategy
        save_config(cfg)
        return True


def pool_list(prov_key: str | None = None) -> list[dict]:
    """Trả về pool kèm trạng thái cooldown đã tính sẵn (giây còn lại, >0 nghĩa là đang bận)."""
    with _pool_lock:
        prov_key = prov_key or _active_provider
        now = time.time()
        out = []
        for e in _pool_load(prov_key):
            remain = max(0.0, e.get("cooldown_until", 0) - now)
            out.append({**e, "cooldown_remaining": remain})
        return out
