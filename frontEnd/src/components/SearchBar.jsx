import React from 'react';

const styles = {
  input: {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    fontSize: '14px',
    fontFamily: 'var(--font-body)',
    outline: 'none',
    background: 'var(--color-bg)',
    color: 'var(--color-text)',
  }
};

export default function SearchBar({ value, onChange }) {
  return (
    <input
      style={styles.input}
      type="text"
      placeholder="搜索会话..."
      value={value}
      onChange={e => onChange(e.target.value)}
    />
  );
}
