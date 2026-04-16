# claude-email

**Claude Code → 邮件通知**

Claude Code 完成任务或需要你确认时，自动发送邮件提醒——让你可以放心离开终端，回来时不会错过任何事。

---

## 特性

- **简单易用** — 基于 Node.js + nodemailer
- **无需服务** — 本地 hook 脚本直接调 SMTP 发邮件
- **轻量快速** — 每次通知仅 ~100ms
- **静默失败** — 任何异常都不会阻塞 Claude Code
- **丰富内容** — 项目、设备、git 信息、Claude 回复
- **多事件支持** — 任务完成、权限确认、等待输入等不同场景

---

## 工作原理

```
Claude Code 事件 (Stop / Notification)
→ 触发本地 hook 脚本
→ 读取配置文件中的 SMTP 配置
→ 发送邮件到指定邮箱
→ 你在邮箱收到通知
```

---

## 配置

配置文件位于 `~/.config/claude-email/config.json`

### QQ 邮箱配置示例

```json
{
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465,
    "smtp_username": "your_email@qq.com",
    "smtp_password": "your_auth_code",
    "to_email": "your_email@qq.com",
    "events": ["Stop", "Notification"]
}
```

> **注意**: QQ 邮箱需要使用授权码而不是登录密码。登录 QQ 邮箱 → 设置 → 账户 → 开启 POP3/SMTP 服务 → 获取授权码

### 常用 SMTP 服务器

| 邮箱 | SMTP 服务器 | 端口 |
|------|------------|------|
| QQ 邮箱 | smtp.qq.com | 465 (SSL) |
| 163 邮箱 | smtp.163.com | 465 (SSL) |
| 126 邮箱 | smtp.126.com | 465 (SSL) |
| Gmail | smtp.gmail.com | 587 (TLS) |
| Outlook | smtp.office365.com | 587 (TLS) |
| Foxmail | smtp.qq.com | 465 (SSL) |

### 字段说明

| 字段 | 说明 | 必需 |
|------|------|------|
| `smtp_server` | SMTP 服务器地址 | 是 |
| `smtp_port` | SMTP 端口 (465/587) | 是 |
| `smtp_username` | 发件人邮箱 | 是 |
| `smtp_password` | 邮箱密码或授权码 | 是 |
| `to_email` | 收件人邮箱 | 是 |
| `events` | 通知哪些事件 | 否 |

### 事件过滤

通过 `events` 字段控制通知哪些事件：

```json
{
    "events": ["Stop"]
}
```

| 值 | 含义 |
|----|------|
| `Stop` | Claude Code 完成回复时通知 |
| `Notification` | Claude Code 需要确认/输入时通知 |

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CLAUDE_EMAIL_TZ_OFFSET` | 时区偏移（相对 UTC 的小时数） | `8`（Asia/Shanghai） |
| `CLAUDE_EMAIL_DEBUG` | 开启调试日志 | 关闭 |

---

## 安装

### 1. 安装 nodemailer

```bash
npm install nodemailer
```

### 2. 创建配置文件

```bash
mkdir -p ~/.config/claude-email
cp config.example.json ~/.config/claude-email/config.json
# 编辑配置文件，填入你的 SMTP 配置
```

### 3. 配置 Claude Code Hooks

在 `~/.claude/settings.json` 的 `hooks` 中添加：

```json
{
    "hooks": {
        "Stop": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "node /absolute/path/to/claude_email_notify.js",
                        "timeout": 30
                    }
                ]
            }
        ],
        "Notification": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "node /absolute/path/to/claude_email_notify.js",
                        "timeout": 30
                    }
                ]
            }
        ]
    }
}
```

### 4. 测试

```bash
echo '{"hook_event_name":"Stop","cwd":"/tmp/test","session_id":"test","last_assistant_message":"Hello!"}' \
    | node /path/to/claude_email_notify.js
```

---

## 项目结构

```
claude-email/
├── claude_email_notify.js   # Hook 脚本
├── config.example.json       # 配置示例
├── README.md                 # 中文文档
├── README_en.md              # English docs
├── LICENSE                   # MIT
└── scripts/
    └── install.sh            # 安装脚本
```

## 系统要求

- Node.js 16+
- [Claude Code](https://claude.ai/claude-code) CLI
- 支持 SMTP 的邮箱账户

## License

MIT