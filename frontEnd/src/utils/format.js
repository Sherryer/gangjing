export function formatTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

export function formatDate(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today - 86400000);
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());

  if (target >= today) return '今天';
  if (target >= yesterday) return '昨天';
  return d.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
}

export function groupByDate(sessions) {
  const groups = {};
  for (const s of sessions) {
    const label = formatDate(s.lastTime);
    if (!groups[label]) groups[label] = [];
    groups[label].push(s);
  }
  return groups;
}
