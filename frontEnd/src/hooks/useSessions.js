import { useState, useEffect, useCallback } from 'react';

export function useSessions() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchSessions = useCallback(() => {
    setLoading(true);
    fetch('/api/sessions')
      .then(r => r.json())
      .then(data => { setSessions(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const sync = useCallback(() => {
    return fetch('/api/sync', { method: 'POST' })
      .then(r => r.json())
      .then(() => fetchSessions());
  }, [fetchSessions]);

  return { sessions, loading, sync };
}

export function useMessages(sessionId) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sessionId) { setMessages([]); return; }
    setLoading(true);
    fetch(`/api/sessions/${sessionId}`)
      .then(r => r.json())
      .then(data => { setMessages(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [sessionId]);

  return { messages, loading };
}
