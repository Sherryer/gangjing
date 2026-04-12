import React from 'react';
import { formatTime } from '../utils/format';

export default function SessionCard({ session, active, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: '10px 14px',
        cursor: 'pointer',
        borderBottom: '1px solid var(--color-border)',
        background: active ? 'var(--color-accent-light)' : 'transparent',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{session.channel}</span>
        <span style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>{formatTime(session.lastTime)}</span>
      </div>
      <div style={{
        fontSize: 14,
        color: 'var(--color-text)',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}>
        {session.preview || '(空会话)'}
      </div>
      <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginTop: 2 }}>
        {session.messageCount} 条消息
        {session.isActive && <span style={{ color: 'var(--color-accent)', marginLeft: 6 }}>● 活跃</span>}
      </div>
    </div>
  );
}
