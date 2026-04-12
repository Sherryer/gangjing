import React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { formatTime } from '../utils/format';

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  const wrapStyle = {
    display: 'flex',
    justifyContent: isUser ? 'flex-end' : 'flex-start',
    padding: '4px 20px',
  };

  const bubbleStyle = {
    maxWidth: '70%',
    padding: '10px 14px',
    borderRadius: 'var(--radius-lg)',
    background: isUser ? 'var(--color-user-bubble)' : 'var(--color-assistant-bubble)',
    color: isUser ? 'var(--color-user-text)' : 'var(--color-assistant-text)',
    fontSize: 14,
    lineHeight: 1.6,
    wordBreak: 'break-word',
  };

  const timeStyle = {
    fontSize: 11,
    color: 'var(--color-text-secondary)',
    marginTop: 4,
    textAlign: isUser ? 'right' : 'left',
    padding: '0 20px',
  };

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={wrapStyle}>
        <div style={bubbleStyle}>
          {isUser ? (
            <div style={{ whiteSpace: 'pre-wrap' }}>{message.text}</div>
          ) : (
            <Markdown remarkPlugins={[remarkGfm]}>{message.text}</Markdown>
          )}
        </div>
      </div>
      <div style={timeStyle}>{formatTime(message.timestamp)}</div>
    </div>
  );
}
