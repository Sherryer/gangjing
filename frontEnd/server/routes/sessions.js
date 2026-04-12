import { Router } from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { syncAll } from '../lib/parser.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(__dirname, '..', '..', 'data');
const router = Router();

router.get('/sessions', (req, res) => {
  const file = path.join(dataDir, 'sessions.json');
  if (!fs.existsSync(file)) return res.json([]);
  res.json(JSON.parse(fs.readFileSync(file, 'utf-8')));
});

router.get('/sessions/:id', (req, res) => {
  const file = path.join(dataDir, 'messages', req.params.id + '.json');
  if (!fs.existsSync(file)) return res.status(404).json({ error: 'Not found' });
  res.json(JSON.parse(fs.readFileSync(file, 'utf-8')));
});

router.post('/sync', (req, res) => {
  try {
    const result = syncAll(dataDir);
    res.json({ ok: true, ...result });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

export default router;
