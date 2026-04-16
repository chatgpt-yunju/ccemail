#!/usr/bin/env node
/**
 * Claude Code → Email notification hook
 * Sends email notifications when Claude Code completes tasks or needs confirmation.
 *
 * Config: ~/.config/claude-email/config.json
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync, spawn } = require('child_process');
const nodemailer = require('nodemailer');

// ── Paths ────────────────────────────────────────────────────────────
const CONFIG_DIR = path.join(os.homedir(), '.config', 'claude-email');
const CONFIG_PATH = path.join(CONFIG_DIR, 'config.json');
const DEBUG_LOG_PATH = path.join(CONFIG_DIR, 'debug.log');

// ── Debug logging ────────────────────────────────────────────────────
const DEBUG = process.env.CLAUDE_EMAIL_DEBUG === '1';

function debugLog(msg) {
    if (!DEBUG) return;
    try {
        if (!fs.existsSync(CONFIG_DIR)) fs.mkdirSync(CONFIG_DIR, { recursive: true });
        const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
        fs.appendFileSync(DEBUG_LOG_PATH, `[${ts}] ${msg}\n`);
    } catch (e) { }
}

// ── Load config ──────────────────────────────────────────────────────
function loadConfig() {
    try {
        const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
        const required = ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password', 'to_email'];
        const missing = required.filter(k => !config[k]);
        if (missing.length > 0) {
            debugLog(`Config incomplete: missing ${missing.join(', ')}`);
            return null;
        }
        debugLog(`Config loaded: smtp_server=${config.smtp_server}, to_email=${config.to_email}`);
        return config;
    } catch (e) {
        debugLog(`Config load failed: ${e.message}`);
        return null;
    }
}

// ── Read stdin ────────────────────────────────────────────────────────
function readStdin() {
    return new Promise((resolve) => {
        let data = '';
        process.stdin.setEncoding('utf-8');
        process.stdin.on('data', chunk => data += chunk);
        process.stdin.on('end', () => {
            try {
                const event = data.trim() ? JSON.parse(data) : {};
                debugLog(`Event received: ${event.hook_event_name || '?'}, cwd=${event.cwd || '?'}`);
                resolve(event);
            } catch (e) {
                debugLog(`stdin parse failed: ${e.message}`);
                resolve({});
            }
        });
    });
}

// ── Git info ──────────────────────────────────────────────────────────
function getGitInfo(cwd) {
    const info = { branch: '', last_commit: '', dirty: false };
    if (!cwd) return info;

    try {
        const branch = execSync(`git -C "${cwd}" branch --show-current`, { encoding: 'utf-8', timeout: 5000 }).trim();
        if (branch) info.branch = branch;
    } catch (e) { }

    try {
        const lastCommit = execSync(`git -C "${cwd}" log --oneline -1 --format="%h %s"`, { encoding: 'utf-8', timeout: 5000 }).trim();
        if (lastCommit) info.last_commit = lastCommit.slice(0, 60);
    } catch (e) { }

    try {
        const status = execSync(`git -C "${cwd}" status --porcelain`, { encoding: 'utf-8', timeout: 5000 }).trim();
        info.dirty = !!status;
    } catch (e) { }

    return info;
}

// ── Helpers ──────────────────────────────────────────────────────────
function projectName(cwd) {
    if (!cwd) return 'unknown';
    try {
        const gitDir = execSync(`git -C "${cwd}" rev-parse --path-format=absolute --git-common-dir`, { encoding: 'utf-8', timeout: 3000 }).trim();
        if (gitDir.endsWith('/.git') || gitDir.endsWith('\\.git')) {
            return path.basename(path.dirname(gitDir));
        }
    } catch (e) { }
    return path.basename(cwd);
}

function hostname() {
    return os.hostname().split('.')[0];
}

function truncate(text, maxLen = 200) {
    if (!text) return '';
    text = text.trim();
    return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
}

function formatTokens(n) {
    if (n < 1000) return n.toString();
    if (n < 1000000) return (n / 1000).toFixed(1) + 'k';
    return (n / 1000000).toFixed(1) + 'M';
}

function nowStr() {
    const offset = parseInt(process.env.CLAUDE_EMAIL_TZ_OFFSET || '8');
    const now = new Date(Date.now() + offset * 3600000);
    return now.toISOString().replace('T', ' ').slice(0, 19);
}

// ── Email builders ───────────────────────────────────────────────────
function buildStopEmail(event, git) {
    const cwd = event.cwd || '';
    const project = projectName(cwd);
    const lastMsg = event.last_assistant_message || '';
    const host = hostname();
    const now = nowStr();
    const branch = git.branch || '';
    const sessionId = event.session_id || '';

    // Subject
    const subject = `[Claude Code] 任务完成 - ${project}`;

    // HTML body
    let html = `<h2>✅ 任务完成</h2>`;
    html += `<p><strong>📁 项目:</strong> ${project} | <strong>💻 设备:</strong> ${host}</p>`;

    if (branch) {
        const dirtyMark = git.dirty ? ' ●' : '';
        html += `<p><strong>🌿 分支:</strong> ${branch}${dirtyMark}</p>`;
    }

    if (lastMsg) {
        const snippet = truncate(lastMsg, 4000).replace(/</g, '&lt;').replace(/>/g, '&gt;');
        html += `<hr/><h3>💬 Claude 的回复</h3><pre style="background:#f5f5f5;padding:10px;overflow:auto;max-height:300px;">${snippet}</pre>`;
    }

    // Footer
    let footer = [];
    if (cwd) footer.push(`📂 ${cwd}`);
    if (sessionId) footer.push(`🔑 ${sessionId.slice(0, 12)}`);
    footer.push(`🕐 ${now}`);
    html += `<hr/><p style="color:#666;font-size:12px;">${footer.join(' | ')}</p>`;

    return { subject, html };
}

function buildNotificationEmail(event, git) {
    const cwd = event.cwd || '';
    const project = projectName(cwd);
    const message = event.message || '';
    const titleText = event.title || '';
    const notifType = event.notification_type || '';
    const host = hostname();
    const now = nowStr();
    const branch = git.branch || '';

    const headerMap = {
        'permission_prompt': '⚠️ 需要确认',
        'idle_prompt': '⏳ 等待输入',
        'auth_success': '✅ 认证成功',
        'elicitation_dialog': '📝 需要信息',
    };
    const headerTitle = headerMap[notifType] || '🔔 通知';

    const subject = `[Claude Code] ${headerTitle.replace(/[^a-zA-Z0-9]/g, '')} - ${project}`;

    let html = `<h2>${headerTitle}</h2>`;
    html += `<p><strong>📁 项目:</strong> ${project} | <strong>💻 设备:</strong> ${host}</p>`;

    if (titleText) html += `<p><strong>${titleText}</strong></p>`;
    if (message) html += `<p>${truncate(message, 4000)}</p>`;
    if (branch) html += `<p><strong>🌿 分支:</strong> ${branch}</p>`;

    let footer = [];
    if (cwd) footer.push(`📂 ${cwd}`);
    footer.push(`🕐 ${now}`);
    html += `<hr/><p style="color:#666;font-size:12px;">${footer.join(' | ')}</p>`;

    return { subject, html };
}

// ── Send email ───────────────────────────────────────────────────────
async function sendEmail(config, subject, htmlBody) {
    const { smtp_server, smtp_port, smtp_username, smtp_password, to_email } = config;

    // Create transporter
    const transporter = nodemailer.createTransport({
        host: smtp_server,
        port: parseInt(smtp_port),
        secure: smtp_port === 465,
        auth: {
            user: smtp_username,
            pass: smtp_password
        },
        connectionTimeout: 30000
    });

    // Send
    const info = await transporter.sendMail({
        from: smtp_username,
        to: to_email,
        subject: subject,
        html: htmlBody
    });

    debugLog(`Email sent: ${info.messageId}`);
    return true;
}

// ── Main ─────────────────────────────────────────────────────────────
async function main() {
    debugLog('=== claude-email notify start ===');

    const config = loadConfig();
    if (!config) {
        debugLog('No config, exiting');
        return;
    }

    const event = await readStdin();
    if (!event || Object.keys(event).length === 0) {
        debugLog('No event data, exiting');
        return;
    }

    // Event filtering
    const eventName = event.hook_event_name || '';
    const allowed = config.events || ['Stop', 'Notification'];
    if (eventName && !allowed.includes(eventName)) {
        debugLog(`Event '${eventName}' not in allowed list ${allowed}, skipping`);
        return;
    }

    // Get git info
    const cwd = event.cwd || '';
    const git = getGitInfo(cwd);

    // Build email
    let subject, htmlBody;
    if (eventName === 'Stop') {
        ({ subject, html: htmlBody } = buildStopEmail(event, git));
    } else {
        ({ subject, html: htmlBody } = buildNotificationEmail(event, git));
    }

    // Send email
    try {
        await sendEmail(config, subject, htmlBody);
        debugLog('Email sent successfully');
    } catch (e) {
        debugLog(`Email send error: ${e.message}`);
    }

    debugLog('=== claude-email notify end ===');
}

main().catch(e => {
    debugLog(`Main error: ${e.message}`);
    process.exit(1);
});