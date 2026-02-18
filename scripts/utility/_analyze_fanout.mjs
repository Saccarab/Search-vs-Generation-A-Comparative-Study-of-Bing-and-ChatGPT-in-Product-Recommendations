import { readFileSync } from 'fs';

function analyze(file, label) {
  const d = JSON.parse(readFileSync(file, 'utf8'));
  const calls = [];
  for (const entry of d) {
    const msg = entry?.v?.message;
    if (msg == null) continue;
    if (msg.author?.name === 'web.run' && msg.metadata?.search_model_queries) {
      calls.push({
        turn: msg.metadata.search_turns_count,
        queries: msg.metadata.search_model_queries.queries,
        time: msg.create_time,
        parent: msg.metadata.parent_id,
        id: msg.id
      });
    }
  }
  console.log(`=== ${label} ===`);
  console.log(`  web.run calls: ${calls.length}`);
  console.log(`  search_turns_count: [${calls.map(c => c.turn).join(', ')}]`);
  console.log(`  total queries: ${calls.reduce((s, c) => s + c.queries.length, 0)}`);
  for (let i = 1; i < calls.length; i++) {
    const chained = calls[i].parent === calls[i - 1].id;
    const delta = ((calls[i].time - calls[i - 1].time) * 1000).toFixed(0);
    console.log(`  Call #${i + 1}: chained=${chained}, delta=${delta}ms`);
  }
  console.log('');
}

const base = './datapass/raw_network_responses/';
analyze(base + 'P053_r1.json', 'P053_r1 enterprise (4q)');
analyze(base + 'P053_r2_enterprise.json', 'P053_r2 enterprise (4q)');
analyze(base + 'P050_r3.json', 'P050_r3 enterprise (4q)');
analyze(base + 'P063_r1.json', 'P063_r1 enterprise (4q)');
