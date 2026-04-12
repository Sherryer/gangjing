import React, { useEffect, useRef } from 'react';
import { useMessages } from '../hooks/useSessions';
import MessageBubble from '../components/MessageBubble';

export default function ChatDetail({ sessionId }) {
  const { messages, loading } = useMessages(sessionId);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!sessionId) {
    return (
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--color-text-secondary)',
        fontSize: 15,
      }}>
        选择一个会话查看聊天记录
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div style={{
        padding: '12px 20px',
        borderBottom: '1px solid var(--color-border)',
        fontSize: 14,
        fontWeight: 600,
        color: 'var(--color-text)',
      }}>
        {sessionId}
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 0' }}>
        {loading && <div style={{ textAlign: 'center', padding: 20, color: 'var(--color-text-secondary)' }}>加载中...</div>}
        {messages.map(m => <MessageBubble key={m.id} message={m} />)}
        <div ref={endRef} />
      </div>
    </div>
  );
}
