import requests
import time
import hashlib
import os
import sys

COOKIE = os.environ.get("SMZDM_COOKIE", "")
if not COOKIE:
    print("Error: SMZDM_COOKIE not set")
    sys.exit(1)

KEY = "apr1$AwP!wRRT$gJ/q.X24poeBInlUJC"
SK = "ierkM0OZZbsuBKLoAgQ6OJneLMXBQXmzX+LXkNTuKch8Ui2jGlahuFyWIzBiDq/L"
V = "10.4.1"
UA = "smzdm_android_V10.4.1 rv:841 (22021211RC;Android12;zh)smzdmapp"

headers = {
    "Host": "user-api.smzdm.com",
    "Content-Type": "application/x-www-form-urlencoded",
    "Cookie": COOKIE,
    "User-Agent": UA,
}

def make_sign(params_str):
    return hashlib.md5((params_str + f"&key={KEY}").encode()).hexdigest().upper()

def get_token():
    ts = int(round(time.time() * 1000))
    params = f"f=android&time={ts}&v={V}&weixin=1"
    data = {"f": "android", "v": V, "weixin": 1, "time": ts, "sign": make_sign(params)}
    resp = requests.post("https://user-api.smzdm.com/robot/token", headers=headers, data=data, timeout=15)
    return resp.json()["data"]["token"]

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

def main():
    print("什么值得买签到开始")
    try:
        token = get_token()
        print(f"Token 获取成功")
        
        result = checkin(token)
        msg = result.get("error_msg", "未知")
        print(f"签到: {msg}")
        if result.get("data"):
            d = result["data"]
            print(f"  连续签到: {d.get('daily_num', '?')}天  经验: {d.get('cexperience', '?')}")
        
        reward = all_reward(token)
        rmsg = reward.get("error_msg", "")
        print(f"额外奖励: {'成功' if not rmsg else rmsg}")
        
        print("签到完成")
    except Exception as e:
        print(f"签到失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
