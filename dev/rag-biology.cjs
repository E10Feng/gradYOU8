const fs = require('fs');
const https = require('https');

const bulletinPath = 'C:\\Users\\ethan\\.openclaw\\workspace\\builds\\washu-navigator\\data\\bulletin_full.json';
const authPath = 'C:\\Users\\ethan\\.openclaw\\agents\\main\\agent\\auth-profiles.json';

const question = "What are the requirements for the Biology major at WashU?";

// Load data
const bulletin = JSON.parse(fs.readFileSync(bulletinPath, 'utf8'));
const auth = JSON.parse(fs.readFileSync(authPath, 'utf8'));
const token = auth.profiles['minimax-portal:default'].access;

console.log('Loaded bulletin: top-level nodes =', bulletin.length);

// Flatten all nodes via DFS
function flatten(nodes, acc = []) {
  for (const node of nodes) {
    acc.push(node);
    if (node.nodes && Array.isArray(node.nodes)) {
      flatten(node.nodes, acc);
    }
  }
  return acc;
}

const allNodes = flatten(bulletin);
console.log('Total flattened nodes:', allNodes.length);

// Score nodes by relevance
function score(node, q) {
  const ql = q.toLowerCase();
  const title = (node.title || '').toLowerCase();
  const summary = (node.summary || '').toLowerCase();
  const text = (node.text || '').toLowerCase();

  let s = 0;

  // Exact title bonuses
  const exactTitles = ['biology major', 'biology major program requirements'];
  for (const et of exactTitles) {
    if (title === et) s += 100;
  }

  // Keyword bonuses
  const keywords = ['biology', 'major', 'requirements', 'biology major', 'washu', 'washington university', 'program', 'courses', 'credits', 'degree'];
  for (const kw of keywords) {
    if (title.includes(kw)) s += 5;
    if (summary.includes(kw)) s += 2;
    if (text.includes(kw)) s += 1;
  }

  // Specific biology major requirement keywords
  const bioKeywords = ['biology major', 'biological sciences', 'b.s. biology', 'b.a. biology', 'major requirements', 'required courses', 'prerequisites', 'core courses', 'upper level', 'capstone'];
  for (const bk of bioKeywords) {
    if (title.includes(bk)) s += 8;
    if (summary.includes(bk)) s += 3;
    if (text.includes(bk)) s += 1.5;
  }

  return s;
}

const scored = allNodes.map(n => ({ ...n, _score: score(n, question) }));
scored.sort((a, b) => b._score - a._score);

const top5 = scored.slice(0, 5);

console.log('\n=== TOP 5 NODES ===');
for (const n of top5) {
  console.log(`[${n.node_id}] "${n.title}" (score=${n._score.toFixed(1)})`);
  console.log(`  summary: ${(n.summary || '').slice(0, 120)}`);
}

// Build context string from top 4
const contextNodes = scored.slice(0, 4);
const context = contextNodes.map(n => {
  let c = `## Node ${n.node_id}: ${n.title}\n`;
  c += `Summary: ${n.summary || '(no summary)'}\n`;
  c += `Text: ${(n.text || '').slice(0, 2000)}`;
  return c;
}).join('\n\n---\n\n');

console.log('\n=== CONTEXT BUILT ===');
console.log(`Total context chars: ${context.length}`);

// Call MiniMax API
const payload = JSON.stringify({
  model: "MiniMax-M2.7",
  max_tokens: 1024,
  temperature: 0.3,
  messages: [
    {
      role: "user",
      content: `You are a helpful assistant answering questions about Washington University in St. Louis using the WashU Undergraduate Bulletin.\n\nContext from the bulletin:\n${context}\n\nQuestion: ${question}\n\nPlease answer the question based on the provided context. If the context doesn't contain enough information to fully answer, say so.`
    }
  ]
});

const url = new URL('https://api.minimax.io/anthropic/v1/messages');
const reqOptions = {
  hostname: 'api.minimax.io',
  path: '/anthropic/v1/messages',
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload)
  }
};

return new Promise((resolve, reject) => {
  const req = https.request(reqOptions, (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      console.log('\n=== MINIMAX RESPONSE ===');
      console.log('Status:', res.statusCode);
      try {
        const parsed = JSON.parse(data);
        console.log(JSON.stringify(parsed, null, 2));
        resolve(parsed);
      } catch (e) {
        console.log('Raw response:', data);
        reject(e);
      }
    });
  });
  req.on('error', reject);
  req.write(payload);
  req.end();
});
