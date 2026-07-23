"""推送层：把简报送到用户手机。
渠道由环境变量开关，不配置就静默跳过（简报始终落盘 reports/，推送只是加急通道）：

  - PUSH_KEY   Server酱(sct.ftqq.com) SendKey，微信服务号推送。
               支持逗号分隔多个 key —— 一个 key 对应一个微信，逐个投递。
  - WECOM_KEY  企业微信群机器人 webhook key（markdown 摘要，4K 字节上限）。
"""
import os
import requests

_SCT_ENDPOINT = "https://sctapi.ftqq.com/{key}.send"
_WECOM_ENDPOINT = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
_SCT_BODY_LIMIT = 30000     # Server酱正文上限约 32KB，留余量
_WECOM_BODY_LIMIT = 4000


def _keys_from_env(var):
    return [k.strip() for k in os.environ.get(var, "").split(",") if k.strip()]


def _push_serverchan(key, label, title, content):
    try:
        r = requests.post(_SCT_ENDPOINT.format(key=key),
                          data={"title": title, "desp": content[:_SCT_BODY_LIMIT]},
                          timeout=20)
        payload = r.json()
        detail = payload.get("data") or {}
        if payload.get("code") == 0 and detail.get("error") == "SUCCESS":
            return f"{label}: 成功 (pushid={detail.get('pushid')})"
        return (f"{label}: 接口返回非成功 code={payload.get('code')} "
                f"error={detail.get('error', '')} resp={r.text[:200]}")
    except Exception as e:
        return f"{label}: 异常 {e}"


def _push_wecom(key, title, content):
    try:
        r = requests.post(_WECOM_ENDPOINT.format(key=key),
                          json={"msgtype": "markdown",
                                "markdown": {"content": content[:_WECOM_BODY_LIMIT]}},
                          timeout=15)
        if r.json().get("errcode") == 0:
            return "企业微信: 成功"
        return f"企业微信: 失败 {r.text[:100]}"
    except Exception as e:
        return f"企业微信: 异常 {e}"


def send_brief(content: str, title: str = "秋招雷达日报"):
    """把简报推到所有已配置渠道，逐渠道打印结果"""
    outcomes = []

    sct_keys = _keys_from_env("PUSH_KEY")
    for i, key in enumerate(sct_keys, 1):
        label = f"Server酱#{i}" if len(sct_keys) > 1 else "Server酱"
        outcomes.append(_push_serverchan(key, label, title, content))

    for key in _keys_from_env("WECOM_KEY"):
        outcomes.append(_push_wecom(key, title, content))

    if not outcomes:
        print("未配置推送渠道（PUSH_KEY / WECOM_KEY），跳过推送。简报已保存到 reports/ 目录。")
    for line in outcomes:
        print(f"  推送 {line}")
