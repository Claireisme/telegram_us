#!/usr/bin/env python3
from __future__ import annotations

import html
import secrets
import sys
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.storage.db import GeneratedPostRecord, RadarDB
from src.telegram.sender import TelegramSendError, send_message


SESSIONS: set[str] = set()
VALID_MODES = {"manual", "semi_auto", "auto"}


class AdminHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not self._is_authenticated():
            return self._render_login()

        path = urlparse(self.path).path
        if path == "/":
            return self._render_dashboard()
        if path == "/sources":
            return self._render_sources()
        if path == "/post":
            return self._render_post()
        if path == "/logs":
            return self._render_logs()
        if path == "/login":
            return self._render_login()
        return self._not_found()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        form = self._read_form()
        if path == "/login":
            return self._handle_login(form)
        if not self._is_authenticated():
            return self._redirect("/login")
        if path == "/settings":
            return self._handle_settings(form)
        if path == "/action":
            return self._handle_action(form)
        return self._not_found()

    def log_message(self, format: str, *args) -> None:
        return

    @property
    def settings(self) -> Settings:
        return self.server.settings  # type: ignore[attr-defined]

    def _db(self) -> RadarDB:
        db = RadarDB(self.settings.database_path)
        db.init_schema()
        return db

    def _is_authenticated(self) -> bool:
        if not self.settings.admin_password:
            return True
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            key, _, value = part.strip().partition("=")
            if key == "radar_session" and value in SESSIONS:
                return True
        return False

    def _handle_login(self, form: dict[str, list[str]]) -> None:
        password = _one(form, "password")
        if self.settings.admin_password and password != self.settings.admin_password:
            return self._render_login(error="密码不正确")
        token = secrets.token_urlsafe(24)
        SESSIONS.add(token)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", f"radar_session={token}; HttpOnly; SameSite=Lax")
        self.end_headers()

    def _handle_settings(self, form: dict[str, list[str]]) -> None:
        send_mode = _one(form, "send_mode", "manual")
        if send_mode not in VALID_MODES:
            send_mode = "manual"
        include_sales = "true" if _one(form, "include_sales") == "on" else "false"
        send_interval = _clamp_int(
            _one(form, "send_interval_seconds", "30"),
            default=30,
            minimum=0,
            maximum=3600,
        )
        scheduler_interval = _clamp_int(
            _one(form, "scheduler_interval_minutes", "60"),
            default=60,
            minimum=5,
            maximum=1440,
        )
        scheduler_duration = _clamp_int(
            _one(form, "scheduler_duration_days", "7"),
            default=7,
            minimum=1,
            maximum=365,
        )
        db = self._db()
        try:
            db.set_setting("send_mode", send_mode)
            db.set_setting("include_sales", include_sales)
            db.set_setting("send_interval_seconds", str(send_interval))
            db.set_setting("scheduler_interval_minutes", str(scheduler_interval))
            db.set_setting("scheduler_duration_days", str(scheduler_duration))
        finally:
            db.close()
        self._redirect("/")

    def _handle_action(self, form: dict[str, list[str]]) -> None:
        action = _one(form, "action")
        post_id_raw = _one(form, "post_id")
        if not post_id_raw.isdigit():
            return self._redirect("/")
        post_id = int(post_id_raw)
        db = self._db()
        try:
            post = db.get_generated_post(post_id)
            if post is None:
                return self._redirect("/")
            if action == "approve":
                db.update_generated_post_status(post_id, "approved")
            elif action == "reject":
                db.update_generated_post_status(post_id, "rejected")
            elif action == "reset":
                db.update_generated_post_status(post_id, "candidate")
            elif action == "send":
                self._send_post(db, post)
        finally:
            db.close()
        self._redirect("/")

    def _send_post(self, db: RadarDB, post: GeneratedPostRecord) -> None:
        if post.status not in {"candidate", "approved"}:
            return
        db.update_generated_post_status(post.id, "approved")
        try:
            result = send_message(
                bot_token=self.settings.telegram_bot_token,
                channel_id=self.settings.telegram_channel_id,
                text=post.body,
                dry_run=self.settings.dry_run,
            )
        except TelegramSendError:
            db.update_generated_post_status(post.id, "candidate")
            raise
        if self.settings.dry_run:
            db.update_generated_post_status(post.id, "candidate")
            return
        message = result.get("result") or {}
        message_id = "" if message.get("message_id") is None else str(message.get("message_id"))
        db.record_sent_post(post.id, message_id, self.settings.telegram_channel_id)
        db.update_generated_post_status(post.id, "sent")

    def _render_dashboard(self) -> None:
        db = self._db()
        try:
            app_settings = db.get_settings()
            status_counts = db.count_posts_by_status()
            recent_posts = db.list_recent_posts(limit=30)
            daily_counts = db.daily_post_counts(days=30)
            today_generated = db.count_posts_since_days(1)
            week_generated = db.count_posts_since_days(7)
            month_generated = db.count_posts_since_days(30)
            today_sent = db.count_sent_since_days(1)
            week_sent = db.count_sent_since_days(7)
            month_sent = db.count_sent_since_days(30)
        finally:
            db.close()

        body = f"""
        <section class="topbar">
          <div>
            <h1>美股异动雷达</h1>
            <p>本地运营后台</p>
          </div>
          <a class="button secondary" href="/logs">日志</a>
        </section>

        <section class="stats">
          {_stat_card("今日生成", today_generated)}
          {_stat_card("本周生成", week_generated)}
          {_stat_card("本月生成", month_generated)}
          {_stat_card("今日发送", today_sent)}
          {_stat_card("本周发送", week_sent)}
          {_stat_card("本月发送", month_sent)}
        </section>

        <section id="settings" class="panel">
          <h2>发送模式</h2>
          <div class="scheduler-summary">
            {_scheduler_item("下次抓取时间", _format_scheduler_time(app_settings.get("scheduler_next_run_at", "")))}
            {_scheduler_item("上次抓取时间", _format_scheduler_time(app_settings.get("scheduler_last_run_at", "")))}
            {_scheduler_item("调度器状态", _scheduler_status_label(app_settings.get("scheduler_status", "")))}
          </div>
          <form class="settings-form" method="post" action="/settings">
            <div class="mode-row">
              {_mode_option("manual", "手动", app_settings.get("send_mode", "manual"))}
              {_mode_option("semi_auto", "半自动", app_settings.get("send_mode", "manual"))}
              {_mode_option("auto", "自动发送", app_settings.get("send_mode", "manual"))}
            </div>
            <div class="settings-fields">
              <label class="check">
                <input type="checkbox" name="include_sales" {"checked" if app_settings.get("include_sales") == "true" else ""}>
                包含 Form 4 公开市场卖出
              </label>
              <label>
                单条发送间隔（秒）
                <input class="number" type="number" name="send_interval_seconds" min="0" max="3600" value="{html.escape(app_settings.get("send_interval_seconds", "30"))}">
              </label>
              <label>
                抓取间隔（分钟）
                <input class="number" type="number" name="scheduler_interval_minutes" min="5" max="1440" value="{html.escape(app_settings.get("scheduler_interval_minutes", "60"))}">
              </label>
              <label>
                持续运行（天）
                <input class="number" type="number" name="scheduler_duration_days" min="1" max="365" value="{html.escape(app_settings.get("scheduler_duration_days", "7"))}">
              </label>
              <button class="button" type="submit">保存设置</button>
            </div>
            <p class="help-text">自动发送时，本轮新内容会按顺序发送；每两条之间按这里设置等待。</p>
          </form>
        </section>

        <section class="grid">
          <div class="panel">
            <h2>状态</h2>
            <table>
              <tbody>
                {_status_row("candidate", status_counts)}
                {_status_row("approved", status_counts)}
                {_status_row("sent", status_counts)}
                {_status_row("rejected", status_counts)}
              </tbody>
            </table>
          </div>
          <div class="panel">
            <h2>近 30 天</h2>
            <table>
              <thead><tr><th>日期</th><th>生成</th><th>发送</th></tr></thead>
              <tbody>{''.join(_daily_row(row) for row in daily_counts)}</tbody>
            </table>
          </div>
        </section>

        <section id="posts" class="panel">
          <h2>最近推送</h2>
          <table>
            <thead><tr><th>ID</th><th>状态</th><th>类型</th><th>标题</th><th>时间</th><th>操作</th></tr></thead>
            <tbody>{''.join(_post_row(post) for post in recent_posts)}</tbody>
          </table>
        </section>
        """
        self._html("美股异动雷达后台", body)

    def _render_post(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        post_id_raw = _one(query, "id")
        if not post_id_raw.isdigit():
            return self._redirect("/")
        db = self._db()
        try:
            post = db.get_generated_post(int(post_id_raw))
        finally:
            db.close()
        if post is None:
            return self._not_found()
        body = f"""
        <section class="topbar">
          <div><h1>{html.escape(post.title)}</h1><p>{html.escape(post.status)} · {html.escape(post.post_type)}</p></div>
          <a class="button secondary" href="/">返回</a>
        </section>
        <section class="panel">
          <pre class="post-body">{html.escape(post.body)}</pre>
          <div class="actions">{_action_buttons(post)}</div>
        </section>
        """
        self._html(post.title, body)

    def _render_logs(self) -> None:
        radar_log = _tail_file(self.settings.log_path)
        error_log = _tail_file(self.settings.error_log_path)
        body = f"""
        <section class="topbar">
          <div><h1>运行日志</h1><p>最近 120 行</p></div>
          <a class="button secondary" href="/">返回</a>
        </section>
        <section class="grid">
          <div class="panel"><h2>radar.log</h2><pre>{html.escape(radar_log)}</pre></div>
          <div class="panel"><h2>errors.log</h2><pre>{html.escape(error_log)}</pre></div>
        </section>
        """
        self._html("运行日志", body)

    def _render_sources(self) -> None:
        sources = _data_sources()
        body = f"""
        <section class="topbar">
          <div><h1>信息来源</h1><p>当前抓取与后续计划接入的平台清单</p></div>
          <a class="button secondary" href="/">返回</a>
        </section>
        <section class="source-grid">
          {''.join(_source_card(source) for source in sources)}
        </section>
        """
        self._html("信息来源", body)

    def _render_login(self, error: str = "") -> None:
        body = f"""
        <section class="login panel">
          <h1>美股异动雷达</h1>
          <p>输入后台密码</p>
          {"<p class='error'>" + html.escape(error) + "</p>" if error else ""}
          <form method="post" action="/login">
            <input type="password" name="password" placeholder="ADMIN_PASSWORD">
            <button class="button" type="submit">进入后台</button>
          </form>
        </section>
        """
        self._html("登录", body, chrome=False)

    def _read_form(self) -> dict[str, list[str]]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        return parse_qs(raw)

    def _redirect(self, path: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", path)
        self.end_headers()

    def _not_found(self) -> None:
        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()
        self.wfile.write(b"not found")

    def _html(self, title: str, body: str, chrome: bool = True) -> None:
        content = (
            f"<div class='app-shell'>{_sidebar()}<main class='content'>{body}</main></div>"
            if chrome
            else f"<main class='login-shell'>{body}</main>"
        )
        page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
{content}
</body>
</html>"""
        encoded = page.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _one(values: dict[str, list[str]], key: str, default: str = "") -> str:
    items = values.get(key)
    return items[0] if items else default


def _clamp_int(raw: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _sidebar() -> str:
    return """
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">美</div>
        <div>
          <strong>美股异动雷达</strong>
          <span>运营控制台</span>
        </div>
      </div>
      <nav class="nav">
        <a class="nav-item active" href="/">总览</a>
        <a class="nav-item" href="/#settings">调度设置</a>
        <a class="nav-item" href="/sources">信息来源</a>
        <a class="nav-item" href="/#posts">推送队列</a>
        <a class="nav-item" href="/logs">运行日志</a>
      </nav>
      <div class="sidebar-footer">
        <span>本地模式</span>
        <strong>127.0.0.1</strong>
      </div>
    </aside>
    """


def _stat_card(label: str, value: int) -> str:
    return f"<div class='stat'><span>{html.escape(label)}</span><strong>{value}</strong></div>"


def _data_sources() -> list[dict[str, str]]:
    return [
        {
            "name": "SEC EDGAR",
            "status": "已接入",
            "use": "13F、13D、13G、Form 4、机构和内部人披露",
            "note": "官方来源，当前用于聪明钱调仓和 Form 4 内幕交易推送。",
            "url": "https://www.sec.gov/edgar/search/",
        },
        {
            "name": "SEC company submissions JSON",
            "status": "已接入",
            "use": "按 CIK 追踪机构和上市公司最新披露",
            "note": "当前通过追踪 CIK 拉取 Berkshire、Citadel、ARK、Scion 以及重点发行人。",
            "url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
        },
        {
            "name": "U.S. House Clerk Financial Disclosure",
            "status": "已接入",
            "use": "众议员 PTR 交易披露索引和 PDF 原文链接，含 Pelosi 等重点人物",
            "note": "当前已自动下载年度 ZIP 并解析 PTR 索引；交易明细 PDF 深度解析下一步继续做。",
            "url": "https://disclosures-clerk.house.gov/FinancialDisclosure",
        },
        {
            "name": "U.S. Senate Public Financial Disclosure",
            "status": "受限接入",
            "use": "参议员 PTR 交易披露",
            "note": "当前已接入官方搜索入口可用性检查；该站存在交互访问限制，报告明细自动解析需单独处理。",
            "url": "https://efdsearch.senate.gov/search/",
        },
        {
            "name": "Yahoo Finance / Stooq / Alpha Vantage",
            "status": "待评估",
            "use": "基础行情、股价、涨跌幅、交易日至今表现",
            "note": "MVP 阶段用于补充行情字段，后续可替换为更稳定的专业行情源。",
            "url": "https://www.alphavantage.co/documentation/",
        },
        {
            "name": "Tradier / Polygon Options",
            "status": "待评估",
            "use": "期权异动、大额 Call/Put、成交量/OI 异常",
            "note": "期权实时数据成本更高，第一阶段先评估低成本 API，再升级专业源。",
            "url": "https://polygon.io/options",
        },
    ]


def _source_card(source: dict[str, str]) -> str:
    status_class = {
        "已接入": "connected",
        "受限接入": "limited",
        "计划接入": "planned",
        "待评估": "watching",
    }.get(source["status"], "")
    return f"""
    <article class="source-card">
      <div class="source-head">
        <h2>{html.escape(source["name"])}</h2>
        <span class="source-status {status_class}">{html.escape(source["status"])}</span>
      </div>
      <p><strong>用途：</strong>{html.escape(source["use"])}</p>
      <p><strong>备注：</strong>{html.escape(source["note"])}</p>
      <a href="{html.escape(source["url"])}" target="_blank" rel="noreferrer">{html.escape(source["url"])}</a>
    </article>
    """


def _mode_option(value: str, label: str, current: str) -> str:
    return f"""
    <label class="radio">
      <input type="radio" name="send_mode" value="{value}" {"checked" if current == value else ""}>
      {html.escape(label)}
    </label>
    """


def _scheduler_item(label: str, value: str) -> str:
    return f"""
    <div class="scheduler-item">
      <span>{html.escape(label)}</span>
      <strong>{html.escape(value)}</strong>
    </div>
    """


def _scheduler_status_label(status: str) -> str:
    labels = {
        "running": "运行中",
        "stopped": "已停止",
        "error": "异常",
    }
    return labels.get(status, "调度器未启动")


def _format_scheduler_time(raw: str) -> str:
    if not raw:
        return "暂无"
    if raw == "抓取中":
        return raw
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    local_time = parsed.astimezone()
    return local_time.strftime("%Y-%m-%d %H:%M:%S")


def _status_row(status: str, counts: dict[str, int]) -> str:
    return f"<tr><td>{status}</td><td>{counts.get(status, 0)}</td></tr>"


def _daily_row(row: tuple[str, int, int]) -> str:
    day, generated, sent = row
    return f"<tr><td>{html.escape(day)}</td><td>{generated}</td><td>{sent}</td></tr>"


def _post_row(post: GeneratedPostRecord) -> str:
    return f"""
    <tr>
      <td>{post.id}</td>
      <td><span class="badge {html.escape(post.status)}">{html.escape(post.status)}</span></td>
      <td>{html.escape(post.post_type)}</td>
      <td><a href="/post?id={post.id}">{html.escape(post.title)}</a></td>
      <td>{html.escape(post.created_at)}</td>
      <td>{_action_buttons(post)}</td>
    </tr>
    """


def _action_buttons(post: GeneratedPostRecord) -> str:
    buttons = []
    if post.status == "candidate":
        buttons.append(_button(post.id, "approve", "批准"))
        buttons.append(_button(post.id, "reject", "拒绝", "secondary"))
        buttons.append(_button(post.id, "send", "发送"))
    elif post.status == "approved":
        buttons.append(_button(post.id, "send", "发送"))
        buttons.append(_button(post.id, "reset", "退回", "secondary"))
        buttons.append(_button(post.id, "reject", "拒绝", "secondary"))
    elif post.status == "rejected":
        buttons.append(_button(post.id, "reset", "重置", "secondary"))
    return "<div class='actions'>" + "".join(buttons) + "</div>"


def _button(post_id: int, action: str, label: str, variant: str = "") -> str:
    klass = "button small" + (f" {variant}" if variant else "")
    return f"""
    <form method="post" action="/action">
      <input type="hidden" name="post_id" value="{post_id}">
      <input type="hidden" name="action" value="{html.escape(action)}">
      <button class="{klass}" type="submit">{html.escape(label)}</button>
    </form>
    """


def _tail_file(path: Path, limit: int = 120) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-limit:])


CSS = """
:root {
  color-scheme: light;
  --bg: #f6f8fb;
  --panel: #ffffff;
  --panel-soft: #f1f5f9;
  --line: #d9e2ec;
  --text: #10212b;
  --muted: #62717d;
  --green: #16c784;
  --blue: #1877f2;
  --red: #d64545;
  --shadow: 0 10px 30px rgba(15, 35, 50, 0.07);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
}
.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  background: #ffffff;
  border-right: 1px solid var(--line);
  padding: 20px 14px;
  display: flex;
  flex-direction: column;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 18px;
  border-bottom: 1px solid var(--line);
}
.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--blue), var(--green));
  color: #ffffff;
  display: grid;
  place-items: center;
  font-weight: 800;
  font-size: 18px;
}
.brand strong,
.brand span {
  display: block;
}
.brand span {
  color: var(--muted);
  font-size: 12px;
  margin-top: 2px;
}
.nav {
  display: grid;
  gap: 6px;
  padding: 18px 0;
}
.nav-item {
  color: var(--text);
  padding: 10px 12px;
  border-radius: 7px;
  font-weight: 600;
}
.nav-item:hover,
.nav-item.active {
  background: #eaf3ff;
  color: var(--blue);
}
.sidebar-footer {
  margin-top: auto;
  padding: 12px;
  background: var(--panel-soft);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.sidebar-footer span,
.sidebar-footer strong {
  display: block;
}
.sidebar-footer span {
  color: var(--muted);
  font-size: 12px;
}
.sidebar-footer strong {
  margin-top: 3px;
}
.content {
  min-width: 0;
  padding: 22px;
}
.login-shell { max-width: 390px; margin: 14vh auto 0; padding: 0 16px; }
h1, h2 { margin: 0; line-height: 1.2; }
h1 { font-size: 24px; }
h2 { font-size: 16px; margin-bottom: 14px; }
p { margin: 6px 0 0; color: var(--muted); }
a { color: var(--blue); text-decoration: none; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }
th { color: var(--muted); font-weight: 600; }
tr:hover td { background: #f8fbff; }
pre { overflow: auto; white-space: pre-wrap; word-break: break-word; color: var(--text); }
input[type="password"], input.number {
  width: 100%;
  background: #ffffff;
  border: 1px solid var(--line);
  color: var(--text);
  padding: 10px;
  border-radius: 6px;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  margin-bottom: 16px;
  padding: 16px;
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 18px;
  box-shadow: var(--shadow);
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.stat {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  box-shadow: var(--shadow);
}
.stat span { display: block; color: var(--muted); }
.stat strong { display: block; font-size: 24px; margin-top: 6px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.source-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.source-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  box-shadow: var(--shadow);
}
.source-card p {
  margin-top: 10px;
}
.source-card a {
  display: inline-block;
  margin-top: 12px;
  word-break: break-all;
}
.source-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.source-status {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 4px 8px;
  background: #edf2f7;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}
.source-status.connected {
  background: #e7f8ef;
  color: var(--green);
}
.source-status.limited {
  background: #fff4d6;
  color: #9a6700;
}
.source-status.planned {
  background: #eaf3ff;
  color: var(--blue);
}
.source-status.watching {
  background: #fff4d6;
  color: #9a6700;
}
.button {
  appearance: none;
  border: 0;
  background: var(--green);
  color: #ffffff;
  border-radius: 6px;
  padding: 9px 12px;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.button.secondary { background: var(--panel-soft); color: var(--text); border: 1px solid var(--line); }
.button.small { padding: 6px 8px; font-size: 12px; }
.settings-form {
  display: grid;
  gap: 14px;
}
.scheduler-summary {
  display: grid;
  grid-template-columns: 1.2fr 1.2fr 0.8fr;
  gap: 10px;
  margin-bottom: 14px;
}
.scheduler-item {
  background: #f8fbff;
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 10px 12px;
}
.scheduler-item span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
}
.scheduler-item strong {
  display: block;
  margin-top: 4px;
  color: var(--text);
}
.mode-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(120px, 1fr));
  gap: 10px;
}
.settings-fields {
  display: grid;
  grid-template-columns: minmax(230px, 1.5fr) repeat(3, minmax(140px, 1fr)) 120px;
  gap: 12px;
  align-items: end;
}
.radio,
.check {
  color: var(--text);
  display: flex;
  gap: 8px;
  align-items: center;
}
.radio {
  min-height: 42px;
  padding: 10px 12px;
  background: #f8fbff;
  border: 1px solid var(--line);
  border-radius: 7px;
}
.settings-fields label:not(.check) {
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-weight: 600;
}
.check {
  min-height: 42px;
  padding: 10px 12px;
  background: #f8fbff;
  border: 1px solid var(--line);
  border-radius: 7px;
}
.help-text { margin: 0; font-size: 12px; }
.actions { display: flex; flex-wrap: wrap; gap: 6px; }
.actions form { margin: 0; }
.badge {
  display: inline-block;
  padding: 3px 7px;
  border-radius: 999px;
  background: #edf2f7;
  color: var(--muted);
}
.badge.sent { color: var(--green); }
.badge.approved { color: var(--blue); }
.badge.rejected { color: var(--red); }
.post-body { font-size: 15px; background: #f8fbff; border: 1px solid var(--line); border-radius: 8px; padding: 16px; }
.login { max-width: 360px; margin: 14vh auto 0; }
.login form { display: grid; gap: 12px; margin-top: 16px; }
.error { color: var(--red); }
@media (min-width: 1180px) {
  .dashboard-main {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 340px;
    gap: 18px;
  }
}
@media (max-width: 900px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar {
    position: static;
    height: auto;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .nav {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .nav-item { text-align: center; }
  .sidebar-footer { display: none; }
  .content { padding: 14px; }
  .stats, .grid, .source-grid, .scheduler-summary, .mode-row, .settings-fields { grid-template-columns: 1fr; }
  .topbar { align-items: flex-start; }
}
@media (max-width: 560px) {
  .nav { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
"""


def main() -> None:
    settings = Settings.load()
    server = ThreadingHTTPServer((settings.admin_host, settings.admin_port), AdminHandler)
    server.settings = settings  # type: ignore[attr-defined]
    print(f"admin server: http://{settings.admin_host}:{settings.admin_port}")
    if not settings.admin_password:
        print("warning: ADMIN_PASSWORD is empty; keep ADMIN_HOST=127.0.0.1")
    server.serve_forever()


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("admin_server", main)
