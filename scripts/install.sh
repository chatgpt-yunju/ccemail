#!/usr/bin/env bash
#
# claude-email installer
# Configures Claude Code hooks to send email notifications.
#
# Usage:
# ./install.sh # Interactive
# ./install.sh --hooks-only # Skip credentials, only install hooks

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────
CONFIG_DIR="$HOME/.config/claude-email"
CONFIG_FILE="$CONFIG_DIR/config.json"
SETTINGS_FILE="$HOME/.claude/settings.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
NOTIFY_SCRIPT="$PROJECT_DIR/claude_email_notify.py"

# ── Colors ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

info() { echo -e "${CYAN}[info]${NC} $*"; }
ok() { echo -e "${GREEN} ✓${NC} $*"; }
warn() { echo -e "${YELLOW} ⚠${NC} $*"; }
error() { echo -e "${RED} ✗${NC} $*"; exit 1; }
step() { echo -e "\n${BOLD}$1${NC}"; }

# ── Parse args ────────────────────────────────────────────────────────
HOOKS_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --hooks-only) HOOKS_ONLY=true; shift ;;
        -h|--help)
            echo "Usage: $0 [--hooks-only]"
            echo " --hooks-only # Skip credentials, only install hooks"
            exit 0 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

# ── Banner ────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD} claude-email${NC} ${DIM}v1.0${NC}"
echo -e " Claude Code → 邮件通知"
echo -e " ─────────────────────────────────"
echo ""

# ── Check Python 3 ───────────────────────────────────────────────────
command -v python3 &>/dev/null || error "需要 python3 (3.8+)，请先安装。"
ok "python3 $(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

[[ -f "$NOTIFY_SCRIPT" ]] || error "未找到 claude_email_notify.py: $NOTIFY_SCRIPT"

# ── Helper: read existing config value ────────────────────────────────
_cfg_val() {
    [[ -f "$CONFIG_FILE" ]] || return 1
    python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('$1',''))" 2>/dev/null
}

# ── Install ───────────────────────────────────────────────────────────
if [[ "${HOOKS_ONLY:-false}" == "true" ]]; then
    [[ -f "$CONFIG_FILE" ]] || error "配置文件不存在: $CONFIG_FILE，请先放置配置文件"
    smtp_server=$(_cfg_val smtp_server) || error "配置文件缺少 smtp_server"
    smtp_port=$(_cfg_val smtp_port) || error "配置文件缺少 smtp_port"
    smtp_username=$(_cfg_val smtp_username) || error "配置文件缺少 smtp_username"
    smtp_password=$(_cfg_val smtp_password) || error "配置文件缺少 smtp_password"
    to_email=$(_cfg_val to_email) || error "配置文件缺少 to_email"

    step "Step 1/1 安装 hooks"
else
    # ══════════════════════════════════════════════════════════════════════
    # Step 1: Collect SMTP Credentials
    # ══════════════════════════════════════════════════════════════════════
    step "Step 1/2 SMTP 邮件配置"

    # SMTP Server
    if [[ -z "${smtp_server:-}" ]]; then
        EXISTING=$(_cfg_val smtp_server) || EXISTING=""
        if [[ -n "$EXISTING" ]]; then
            read -rp " SMTP 服务器 [$EXISTING]: " smtp_server
            smtp_server="${smtp_server:-$EXISTING}"
        else
            read -rp " SMTP 服务器 (如 smtp.qq.com): " smtp_server
        fi
    fi
    [[ -z "$smtp_server" ]] && error "SMTP 服务器不能为空"

    # SMTP Port
    if [[ -z "${smtp_port:-}" ]]; then
        EXISTING=$(_cfg_val smtp_port) || EXISTING=""
        if [[ -n "$EXISTING" ]]; then
            read -rp " SMTP 端口 [$EXISTING]: " smtp_port
            smtp_port="${smtp_port:-$EXISTING}"
        else
            read -rp " SMTP 端口 (465 或 587): " smtp_port
            smtp_port="${smtp_port:-465}"
        fi
    fi

    # Username (email)
    if [[ -z "${smtp_username:-}" ]]; then
        EXISTING=$(_cfg_val smtp_username) || EXISTING=""
        if [[ -n "$EXISTING" ]]; then
            read -rp " 发件人邮箱 [$EXISTING]: " smtp_username
            smtp_username="${smtp_username:-$EXISTING}"
        else
            read -rp " 发件人邮箱: " smtp_username
        fi
    fi
    [[ -z "$smtp_username" ]] && error "发件人邮箱不能为空"

    # Password (or auth code)
    if [[ -z "${smtp_password:-}" ]]; then
        EXISTING=$(_cfg_val smtp_password) || EXISTING=""
        if [[ -n "$EXISTING" ]]; then
            read -rsp " 邮箱密码/授权码 [已保存，回车跳过]: " smtp_password; echo ""
            smtp_password="${smtp_password:-$EXISTING}"
        else
            read -rsp " 邮箱密码/授权码: " smtp_password; echo ""
        fi
    fi
    [[ -z "$smtp_password" ]] && error "邮箱密码/授权码不能为空"

    # To Email
    if [[ -z "${to_email:-}" ]]; then
        EXISTING=$(_cfg_val to_email) || EXISTING=""
        if [[ -n "$EXISTING" ]]; then
            read -rp " 收件人邮箱 [$EXISTING]: " to_email
            to_email="${to_email:-$EXISTING}"
        else
            read -rp " 收件人邮箱: " to_email
        fi
    fi
    [[ -z "$to_email" ]] && error "收件人邮箱不能为空"

    # ══════════════════════════════════════════════════════════════════════
    # Write config + install hooks
    # ══════════════════════════════════════════════════════════════════════
    step "Step 2/2 安装"

    # Write config
    mkdir -p "$CONFIG_DIR"
    python3 -c "
import json
import os

cfg = {
    'smtp_server': '$smtp_server',
    'smtp_port': $smtp_port,
    'smtp_username': '$smtp_username',
    'smtp_password': '$smtp_password',
    'to_email': '$to_email',
    'events': ['Stop', 'Notification']
}
with open('$CONFIG_FILE', 'w') as f:
    json.dump(cfg, f, indent=4, ensure_ascii=False)
"
    chmod 600 "$CONFIG_FILE"
    ok "配置已保存 $CONFIG_FILE"

    echo ""
    echo "  注意: QQ 邮箱需要使用授权码，而不是登录密码。"
    echo "  获取方式: 邮箱设置 → 账户 → 开启 POP3/SMTP 服务 → 获取授权码"
    echo ""
fi # end of interactive vs hooks-only

# Install Claude Code hooks
HOOK_CMD="python3 $NOTIFY_SCRIPT"
mkdir -p "$HOME/.claude"

if [[ -f "$SETTINGS_FILE" ]]; then
    python3 << PYEOF
import json

with open("$SETTINGS_FILE", "r") as f:
    settings = json.load(f)

hooks = settings.setdefault("hooks", {})
hook_cmd = "$HOOK_CMD"
entry = {"matcher": "", "hooks": [{"type": "command", "command": hook_cmd, "timeout": 30}]}

for ev in ("Stop", "Notification"):
    entries = hooks.setdefault(ev, [])
    already = any("claude_email_notify" in h.get("command", "") for e in entries for h in e.get("hooks", []))
    if not already:
        entries.append(entry)

with open("$SETTINGS_FILE", "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
PYEOF
else
    python3 -c "
import json
hook_cmd = '$HOOK_CMD'
entry = {'matcher': '', 'hooks': [{'type': 'command', 'command': hook_cmd, 'timeout': 30}]}
settings = {'hooks': {'Stop': [entry], 'Notification': [entry]}}
with open('$SETTINGS_FILE', 'w') as f:
    json.dump(settings, f, indent=2)
"
fi
ok "Claude Code hooks 已配置"

# ── Test notification ─────────────────────────────────────────────────
echo ""
read -rp " 发送测试邮件？[Y/n] " SEND_TEST
if [[ "${SEND_TEST:-Y}" =~ ^[Yy]$ ]]; then
    echo '{"hook_event_name":"Stop","cwd":"'"$SCRIPT_DIR"'","session_id":"install-test","last_assistant_message":"🎉 claude-email 安装成功！\n\n你现在可以收到 Claude Code 的邮件通知了。去邮箱看看测试邮件吧。"}' \
        | python3 "$NOTIFY_SCRIPT"
    ok "测试邮件已发送，请查看邮箱"
fi

# ── Done ──────────────────────────────────────────────────────────────
echo ""
echo -e " ${GREEN}${BOLD}安装完成 ✓${NC}"
echo ""
echo -e " ${DIM}配置${NC} $CONFIG_FILE"
echo -e " ${DIM}脚本${NC} $NOTIFY_SCRIPT"
echo ""
echo " Claude Code 每次完成任务，你都会收到邮件通知。"
echo ""