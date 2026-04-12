import React, { useState } from 'react';
import { useSessions } from '../hooks/useSessions';
import SearchBar from './SearchBar';
import SessionCard from './SessionCard';
import { groupByDate } from '../utils/format';

export default function Sidebar({ activeId, onSelect }) {
  const { sessions, loading, sync } = useSessions();
  const [search, setSearch] = useState('');
  const [syncing, setSyncing] = useState(false);

  const filtered = search
    ? sessions.filter(s => s.preview?.toLowerCase().includes(search.toLowerCase()))
    : sessions;

  const groups = groupByDate(filtered);

  const handleSync = () => {
    setSyncing(true);
    sync().finally(() => setSyncing(false));
  };

  return (
    <div style={{
      width: 320,
      minWidth: 320,
      height: '100vh',
      borderRight: '1px solid var(--color-border)',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--color-bg)',
    }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--color-border)' }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <div style={{ flex: 1 }}><SearchBar value={search} onChange={setSearch} /></div>
          <button
            onClick={handleSync}
            disabled={syncing}
            style={{
              padding: '8px 14px',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              background: 'var(--color-bg)',
              color: 'var(--color-text)',
              cursor: 'pointer',
              fontSize: 13,
              whiteSpace: 'nowrap',
            }}
          >
            {syncing ? '同步中...' : '同步'}
          </button>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading && <div style={{ padding: 20, textAlign: 'center', color: 'var(--color-text-secondary)' }}>加载中...</div>}
        {Object.entries(groups).map(([date, items]) => (
          <div key={date}>
            <div style={{
              padding: '8px 14px 4px',
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--color-text-secondary)',
              background: 'var(--color-bg-subtle)',
            }}>{date}</div>
            {items.map(s => (
              <SessionCard
                key={s.id}
                session={s}
                active={s.id === activeId}
                onClick={() => onSelect(s.id)}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
