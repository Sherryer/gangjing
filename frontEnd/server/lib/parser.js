import fs from 'fs';
import os from 'os';
import path from 'path';

const SESSIONS_DIR = process.env.OPENCLAW_SESSIONS_DIR || path.join(os.homedir(), '.openclaw/agents/main/sessions/');

/**
 * Clean user message text, extract metadata
 */
function cleanUserMessage(rawText) {
  let text = rawText;
  let sender = null;
  let attachments = [];

  // 1. Extract & remove Conversation info block
  text = text.replace(/Conversation info \(untrusted metadata\):\n```json\n[\s\S]*?\n```\n\n/g, '');

  // 2. Extract sender & remove Sender block
  const senderMatch = text.match(/Sender \(untrusted metadata\):\n```json\n([\s\S]*?)\n```\n\n/);
  if (senderMatch) {
    try {
      const senderObj = JSON.parse(senderMatch[1]);
      sender = senderObj.name || senderObj.id || senderObj.openId || null;
    } catch {}
    text = text.replace(/Sender \(untrusted metadata\):\n```json\n[\s\S]*?\n```\n\n/g, '');
  }

  // 3. Remove [Feishu ...] lines
  text = text.replace(/\[Feishu [^\]]*timestamp[^\]]*\]\s*\[message_id:[^\]]*\]\n?/g, '');

  // 4. Extract attachments from [media attached: ...]
  const mediaMatches = text.matchAll(/\[media attached:\s*(.*?)\]\n?/g);
  for (const m of mediaMatches) {
    attachments.push(m[1].trim());
  }
  text = text.replace(/\[media attached:.*?\]\n?/g, '');

  // 5. Remove system instruction lines
  text = text.replace(/To send an image back, prefer the message tool[^\n]*\n?/g, '');

  // 6. Remove <file> tags but keep inner content
  text = text.replace(/<file\s+name="[^"]*"\s+mime="[^"]*">([\s\S]*?)<\/file>/g, '$1');

  // 7. Extract feishu file JSON
  const fileJsonRe = /\{"file_key"\s*:\s*"[^"]*"\s*,\s*"file_name"\s*:\s*"([^"]*)"\s*[^}]*\}/g;
  let fjm;
  while ((fjm = fileJsonRe.exec(text)) !== null) {
    attachments.push(fjm[1]);
  }
  text = text.replace(/\{"file_key"\s*:\s*"[^"]*"\s*,\s*"file_name"\s*:\s*"[^"]*"\s*[^}]*\}/g, '');

  text = text.trim();
  return { text, sender, attachments };
}

/**
 * Clean assistant message content array
 */
function cleanAssistantMessage(content) {
  const texts = [];
  for (const block of content) {
    if (block.type === 'text') {
      texts.push(block.text);
    }
  }
  return texts.join('\n').replace(/^\n+/, '').trim();
}

/**
 * Check if a message should be skipped entirely
 */
function shouldSkipMessage(role, text) {
  if (role === 'system') return true;
  if (role === 'user') {
    if (/A new session was started via \/new/.test(text)) return true;
    if (/Read HEARTBEAT\.md if it exists/.test(text)) return true;
    if (!text || text.trim() === '') return true;
  }
  if (role === 'assistant') {
    const t = text.trim();
    if (t === 'NO_REPLY' || t === 'HEARTBEAT_OK') return true;
  }
  return false;
}

/**
 * Get raw text from content array
 */
function getRawText(content) {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content.filter(b => b.type === 'text').map(b => b.text).join('\n');
  }
  return '';
}

/**
 * Parse a single JSONL file into cleaned messages
 */
function parseJsonlFile(filePath) {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const lines = raw.split('\n').filter(l => l.trim());
  const messages = [];
  let sessionMeta = null;

  for (const line of lines) {
    let obj;
    try { obj = JSON.parse(line); } catch { continue; }

    if (obj.type === 'session') {
      sessionMeta = obj;
      continue;
    }
    if (obj.type !== 'message') continue;

    const msg = obj.message;
    if (!msg || !msg.role) continue;
    const role = msg.role;
    const content = msg.content;

    if (role === 'system') continue;

    if (role === 'user') {
      const rawText = getRawText(content);
      const { text, sender, attachments } = cleanUserMessage(rawText);
      if (shouldSkipMessage('user', text)) continue;
      messages.push({
        id: obj.id,
        role: 'user',
        text,
        timestamp: obj.timestamp,
        sender: sender || null,
        attachments
      });
    } else if (role === 'assistant') {
      const text = Array.isArray(content)
        ? cleanAssistantMessage(content)
        : (typeof content === 'string' ? content.replace(/^\n+/, '').trim() : '');
      if (shouldSkipMessage('assistant', text)) continue;
      if (!text) continue;
      messages.push({
        id: obj.id,
        role: 'assistant',
        text,
        timestamp: obj.timestamp,
        sender: null,
        attachments: []
      });
    }
  }

  return { sessionMeta, messages };
}

/**
 * Parse sessions.json index to get channel info per session
 */
function getSessionChannels() {
  const indexPath = path.join(SESSIONS_DIR, 'sessions.json');
  if (!fs.existsSync(indexPath)) return {};
  const data = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
  const map = {};
  for (const [key, val] of Object.entries(data)) {
    if (val.sessionId) {
      map[val.sessionId] = {
        channel: val.lastChannel || val.deliveryContext?.channel || 'unknown',
        chatType: val.chatType || 'direct'
      };
    }
  }
  return map;
}

/**
 * Sync all sessions: parse JSONL files → write to data/
 */
export function syncAll(dataDir) {
  const channelMap = getSessionChannels();
  const files = fs.readdirSync(SESSIONS_DIR).filter(f => f.endsWith('.jsonl') || f.includes('.jsonl.reset.'));
  // exclude .lock files
  const jsonlFiles = files.filter(f => !f.endsWith('.lock'));

  const sessionsIndex = [];
  const messagesDir = path.join(dataDir, 'messages');
  fs.mkdirSync(messagesDir, { recursive: true });

  for (const file of jsonlFiles) {
    const filePath = path.join(SESSIONS_DIR, file);
    const { sessionMeta, messages } = parseJsonlFile(filePath);
    if (messages.length === 0) continue;

    // Extract session ID from filename
    const sessionId = file.split('.')[0];
    const isActive = file.endsWith('.jsonl');
    const isReset = file.includes('.jsonl.reset.');

    // For reset files, use the reset part as a unique suffix
    const fileId = isReset
      ? sessionId + '-' + file.replace(/.*\.jsonl\.reset\./, '').replace(/[:.]/g, '-')
      : sessionId;

    const channel = channelMap[sessionId]?.channel || 'unknown';
    const firstMsg = messages[0];
    const lastMsg = messages[messages.length - 1];

    sessionsIndex.push({
      id: fileId,
      channel,
      startTime: firstMsg.timestamp,
      lastTime: lastMsg.timestamp,
      messageCount: messages.length,
      preview: (messages.find(m => m.role === 'user')?.text || '').slice(0, 60),
      isActive
    });

    fs.writeFileSync(path.join(messagesDir, fileId + '.json'), JSON.stringify(messages, null, 2));
  }

  // Sort by lastTime desc
  sessionsIndex.sort((a, b) => new Date(b.lastTime) - new Date(a.lastTime));
  fs.writeFileSync(path.join(dataDir, 'sessions.json'), JSON.stringify(sessionsIndex, null, 2));

  return { sessionCount: sessionsIndex.length, totalMessages: sessionsIndex.reduce((s, x) => s + x.messageCount, 0) };
}
