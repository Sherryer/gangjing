import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import ChatDetail from './pages/ChatDetail';

const styles = {
  container: {
    display: 'flex',
    width: '100%',
    height: '100vh',
  }
};

export default function App() {
  const [activeId, setActiveId] = useState(null);

  return (
    <div style={styles.container}>
      <Sidebar activeId={activeId} onSelect={setActiveId} />
      <ChatDetail sessionId={activeId} />
    </div>
  );
}
