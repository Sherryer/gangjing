import path from 'path';
import { fileURLToPath } from 'url';
import { syncAll } from '../server/lib/parser.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(__dirname, '..', 'data');

console.log('Syncing sessions...');
const result = syncAll(dataDir);
console.log(`Done: ${result.sessionCount} sessions, ${result.totalMessages} messages`);
