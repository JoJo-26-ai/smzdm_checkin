"""
什么值得买 签到 + 每日任务
排除：关注用户/栏目/品牌、评论（需额外配置）、抽奖（需网页解析）
"""
import requests, time, hashlib, os, sys, random

COOKIE = os.environ.get("SMZDM_COOKIE", "")
if not COOKIE:
    print("Error: SMZDM_COOKIE not set")
    sys.exit(1)

KEY = "apr1$AwP!wRRT$gJ/q.X24poeBInlUJC"
SK = "ierkM0OZZbsuBKLoAgQ6OJneLMXBQXmzX+LXkNTuKch8Ui2jGlahuFyWIzBiDq/L"
V = "10.4.1"
UA = "smzdm_android_V10.4.1 rv:841 (22021211RC;Android12;zh)smzdmapp"

headers = {"Host": "user-api.smzdm.com", "Content-Type": "application/x-www-form-urlencoded", "Cookie": COOKIE, "User-Agent": UA}
web_headers = {"Accept": "application/json, text/plain, */*", "Accept-Language": "zh-CN,zh;q=0.9", "Referer": "https://post.smzdm.com/", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Cookie": COOKIE}

def make_sign(params_str):
    return hashlib.md5((params_str + f"&key={KEY}").encode()).hexdigest().upper()

# ========== 基础 API ==========

def api_post(path, extra_params=None):
    """统一 POST 请求，自动签名。extra_params 中可不含 sk。"""
    ts = int(round(time.time() * 1000))
    base = {"f": "android", "v": V, "weixin": "1", "time": str(ts)}
    if extra_params:
        base.update({k: str(v) for k, v in extra_params.items()})
    keys = sorted(base.keys())
    sign_str = "&".join(f"{k}={base[k]}" for k in keys)
    base["sign"] = make_sign(sign_str)
    resp = requests.post(f"https://user-api.smzdm.com{path}", headers=headers, data=base, timeout=15)
    return resp.json()

def get_token():
    ts = int(round(time.time() * 1000))
    params = f"f=android&time={ts}&v={V}&weixin=1"
    data = {"f": "android", "v": V, "weixin": 1, "time": ts, "sign": make_sign(params)}
    resp = requests.post("https://user-api.smzdm.com/robot/token", headers=headers, data=data, timeout=15)
    result = resp.json()
    if result.get("error_code") != "0" and result.get("error_code") != 0:
        raise Exception(f"获取token失败: {result}")
    return result["data"]["token"]

def checkin(token):
    ts = int(round(time.time() * 1000))
    params = f"f=android&sk={SK}&time={ts}&token={token}&v={V}&weixin=1"
    data = {"f": "android", "v": V, "sk": SK, "weixin": 1, "time": ts, "token": token, "sign": make_sign(params)}
    resp = requests.post("https://user-api.smzdm.com/checkin", headers=headers, data=data, timeout=15)
    return resp.json()

def all_reward(token):
    ts = int(round(time.time() * 1000))
    params = f"f=android&sk={SK}&time={ts}&token={token}&v={V}&weixin=1"
    data = {"f": "android", "v": V, "sk": SK, "weixin": 1, "time": ts, "token": token, "sign": make_sign(params)}
    resp = requests.post("https://user-api.smzdm.com/checkin/all_reward", headers=headers, data=data, timeout=15)
    return resp.json()

# ========== 每日任务 ==========

def get_task_list():
    """获取任务列表，返回 (tasks, detail)"""
    result = api_post("/task/list_v2", {"get_total": "1", "limit": "200", "offset": "0", "point_type": "0"})
    if result.get("error_code") != "0" and result.get("error_code") != 0:
        print(f"  获取任务列表失败: {result.get('error_msg', result)}")
        return [], None
    rows = result.get("data", {}).get("rows", [])
    if not rows:
        return [], None
    cell = rows[0].get("cell_data", {})
    activity = cell.get("activity_task", {})
    tasks = []
    for group in activity.get("default_list_v2", []):
        for t in group.get("task_list", []):
            tasks.append(t)
    return tasks, rows[0]

def get_articles(n=10):
    """从 post.smzdm.com 获取推荐文章，返回 [{article_id, channel_id, ...}]"""
    resp = requests.get("https://post.smzdm.com/json_more/?tab_id=tuijian&filterUrl=tuijian", headers=web_headers, timeout=15)
    try:
        data = resp.json()
    except:
        return []
    if data.get("error_code") != 0 and data.get("error_code") != "0":
        return []
    arts = data.get("data", [])[:n]
    return [{"article_id": str(a.get("article_id")), "channel_id": str(a.get("channel_id", ""))} for a in arts]

def receive_reward(task_id, robot_token):
    """领取任务奖励（最小参数，不加 sk）"""
    result = api_post("/task/activity_task_receive", {"task_id": task_id, "robot_token": robot_token})
    if result.get("error_code") == "0" or result.get("error_code") == 0:
        msg = result.get("data", {}).get("reward_msg", "成功")
        return True, msg
    return False, result.get("error_msg", str(result))

def need_articles(task):
    """判断任务是否需要从文章列表获取文章（article_id 为 0 或缺失）"""
    aid = task.get("article_id", "0")
    return aid == "0" or not aid

def get_target_articles(task, count=1):
    """获取任务目标文章：优先用 task 自带的 article_id/channel_id，否则从文章列表获取"""
    aid = task.get("article_id", "0")
    if aid != "0" and aid:
        ch = task.get("channel_id", "0")
        return [{"article_id": str(aid), "channel_id": str(ch)}] * count
    return get_articles(count)

# --- 浏览 ---

def do_view_task(task, robot_token):
    name = task.get("task_name", "浏览文章")
    remaining = int(task.get("task_even_num", 1)) - int(task.get("task_finished_num", 0))
    if remaining <= 0:
        return receive_reward(task["task_id"], robot_token)

    print(f"  [浏览] {name} ({remaining}篇)")
    articles = get_target_articles(task, remaining)
    if not articles:
        print("    获取文章失败")
        return False

    for i, a in enumerate(articles):
        print(f"    阅读 {i+1}/{remaining}...")
        result = api_post("/task/event_view_article_sync", {
            "article_id": a["article_id"],
            "channel_id": a["channel_id"],
            "task_id": task["task_id"],
        })
        if result.get("error_code") == "0" or result.get("error_code") == 0:
            print("    完成")
        else:
            print(f"    失败: {result.get('error_msg', '')}")
        time.sleep(random.randint(3, 6))

    time.sleep(random.randint(2, 4))
    ok, msg = receive_reward(task["task_id"], robot_token)
    print(f"    奖励: {msg}")
    return ok

# --- 分享 ---

def do_share_task(task, robot_token):
    name = task.get("task_name", "分享")
    remaining = int(task.get("task_even_num", 1)) - int(task.get("task_finished_num", 0))
    if remaining <= 0:
        return receive_reward(task["task_id"], robot_token)

    print(f"  [分享] {name} ({remaining}次)")
    articles = get_target_articles(task, remaining)
    if not articles:
        print("    获取文章失败")
        return False

    for i, a in enumerate(articles):
        print(f"    分享 {i+1}/{remaining}...")
        api_post("/share/article_reward", {"article_id": a["article_id"], "channel_id": a["channel_id"]})
        time.sleep(1)
        api_post("/share/daily_reward", {"channel_id": a["channel_id"]})
        time.sleep(1)
        result = api_post("/share/callback", {"article_id": a["article_id"], "channel_id": a["channel_id"], "touchstone_event": "{}"})
        if result.get("error_code") == "0" or result.get("error_code") == 0:
            print("    完成")
        time.sleep(random.randint(3, 5))

    time.sleep(random.randint(2, 4))
    ok, msg = receive_reward(task["task_id"], robot_token)
    print(f"    奖励: {msg}")
    return ok

# --- 点赞 ---

def do_rating_task(task, robot_token):
    name = task.get("task_name", "点赞")
    print(f"  [点赞] {name}")
    redirect = task.get("task_redirect_url", {})
    link_val = redirect.get("link_val", "0")

    articles = get_target_articles(task, 1)
    if not articles:
        print("    获取文章失败")
        return False
    a = articles[0]

    # 取消→点赞→取消→点赞→取消（保持未点赞状态，避免刷量被识别）
    for action in ["like_cancel", "like_create", "like_cancel", "like_create", "like_cancel"]:
        api_post(f"/rating/{action}", {"id": a["article_id"], "channelId": a["channel_id"]})
        time.sleep(random.randint(2, 3))
    print("    完成")

    time.sleep(random.randint(2, 4))
    ok, msg = receive_reward(task["task_id"], robot_token)
    print(f"    奖励: {msg}")
    return ok

# --- 收藏 ---

def do_favorite_task(task, robot_token):
    name = task.get("task_name", "收藏")
    print(f"  [收藏] {name}")
    redirect = task.get("redirect_url", task.get("task_redirect_url", {}))
    link_val = redirect.get("link_val", "0")

    articles = get_target_articles(task, 1)
    if not articles:
        print("    获取文章失败")
        return False
    a = articles[0]

    for action in ["destroy", "create", "destroy"]:
        api_post(f"/favorite/{action}", {"id": a["article_id"], "channelId": a["channel_id"]})
        time.sleep(random.randint(2, 3))
    print("    完成")

    time.sleep(random.randint(2, 4))
    ok, msg = receive_reward(task["task_id"], robot_token)
    print(f"    奖励: {msg}")
    return ok

# --- 任务分发 ---

TASK_HANDLERS = {
    "interactive.view.article": do_view_task,
    "interactive.share": do_share_task,
    "interactive.rating": do_rating_task,
    "interactive.favorite": do_favorite_task,
}

SKIP_TYPES = {
    "interactive.follow.user": "关注用户",
    "interactive.follow.brand": "关注品牌",
    "interactive.follow.column": "关注栏目",
    "guide.crowd": "抽奖（需网页解析）",
    "publish.baoliao_new": "爆料发布",
    "interactive.comment": "评论（需额外配置）",
}

def run_daily_tasks(robot_token):
    print("获取任务列表...")
    tasks, detail = get_task_list()
    if not tasks:
        print("  无任务")
        return 0

    success = 0
    for task in tasks:
        status = task.get("task_status", "")
        name = task.get("task_name", "未知")
        etype = task.get("task_event_type", "")

        # 待领取
        if status == "3":
            ok, msg = receive_reward(task["task_id"], robot_token)
            if ok:
                print(f"  [领取] {name}: {msg}")
                success += 1
            else:
                print(f"  [领取失败] {name}: {msg}")

        # 未完成
        elif status == "2":
            handler = TASK_HANDLERS.get(etype)
            if handler:
                try:
                    if handler(task, robot_token):
                        success += 1
                except Exception as e:
                    print(f"  [异常] {name}: {e}")
            elif etype in SKIP_TYPES:
                print(f"  [跳过] {name} — {SKIP_TYPES[etype]}")
            else:
                print(f"  [跳过] {name} (unknown: {etype})")

        time.sleep(random.randint(3, 5))

    # 限时活动奖励
    if detail:
        cell = detail.get("cell_data", {})
        if cell.get("activity_reward_status") == "1":
            aid = cell.get("activity_id", "")
            aname = cell.get("activity_name", "")
            if aid:
                print(f"\n领取限时活动奖励: {aname}")
                result = api_post("/task/activity_receive", {"activity_id": aid})
                if result.get("error_code") == "0" or result.get("error_code") == 0:
                    rmsg = result.get("data", {}).get("reward_msg", "成功")
                    print(f"  活动奖励: {rmsg}")

    return success

# ========== 主流程 ==========

def main():
    print("=" * 50)
    print("什么值得买 签到 + 每日任务")
    print("=" * 50)

    try:
        token = get_token()
        print(f"\n[Token] 获取成功")

        print("\n--- 签到 ---")
        result = checkin(token)
        print(f"签到: {result.get('error_msg', '未知')}")
        if result.get("data"):
            d = result["data"]
            print(f"  连续签到: {d.get('daily_num', '?')}天  经验: {d.get('cexperience', '?')}")

        reward = all_reward(token)
        rmsg = reward.get("error_msg", "")
        print(f"额外奖励: {'领取成功' if not rmsg else rmsg}")

        print("\n--- 每日任务 ---")
        count = run_daily_tasks(token)
        print(f"\n完成任务数: {count}")
        print("\n全部完成")

    except Exception as e:
        print(f"\n执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
