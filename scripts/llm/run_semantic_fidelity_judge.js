/**
 * Run the semantic fidelity judge over pre-built prompt jobs (JSONL).
 *
 * Inputs:
 * - data/enrichment/semantic_fidelity_jobs_gpt.jsonl
 * - data/enrichment/semantic_fidelity_jobs_gemini.jsonl
 *
 * Output:
 * - JSONL results file (one line per case_id), resumable.
 *
 * Examples:
 *   OPEN_AI_KEY=... node scripts/llm/run_semantic_fidelity_judge.js --provider openai --model gpt-5-mini --jobs data/enrichment/semantic_fidelity_jobs_gpt.jsonl --out data/enrichment/semantic_fidelity_results_gpt5mini.jsonl
 *
 *   GEMINI_API_KEY=... node scripts/llm/run_semantic_fidelity_judge.js --provider gemini --model gemini-2.5-flash --jobs data/enrichment/semantic_fidelity_jobs_gemini.jsonl --out data/enrichment/semantic_fidelity_results_gemini_flash.jsonl
 */
/* eslint-disable no-console */

const fs = require("fs");
const path = require("path");
const Bottleneck = require("bottleneck");

function utcNowIso() {
  return new Date().toISOString();
}

function safeStr(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  return s.toLowerCase() === "nan" ? "" : s;
}

function parseArgs(argv) {
  const out = {
    provider: "openai", // openai | gemini
    model: "",
    jobs: "data/enrichment/semantic_fidelity_jobs_gpt.jsonl",
    out: "data/enrichment/semantic_fidelity_results.jsonl",
    max: 0,
    concurrency: Number(process.env.CONCURRENCY || "5"),
    minTimeMs: Number(process.env.MIN_TIME_MS || "200"),
    maxAttempts: Number(process.env.MAX_ATTEMPTS || "2"),
    help: false,
    dryRun: false,
    logStarts: false,
    logEvery: Number(process.env.LOG_EVERY || "1") || 1,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") {
      out.help = true;
      continue;
    }
    if (a === "--dry-run") {
      out.dryRun = true;
      continue;
    }
    if (a === "--log-starts") {
      out.logStarts = true;
      continue;
    }
    if (a === "--provider") out.provider = safeStr(argv[++i]) || out.provider;
    else if (a === "--model") out.model = safeStr(argv[++i]) || out.model;
    else if (a === "--jobs") out.jobs = argv[++i] || out.jobs;
    else if (a === "--out") out.out = argv[++i] || out.out;
    else if (a === "--max") out.max = Number(argv[++i] || "0") || 0;
    else if (a === "--concurrency") out.concurrency = Number(argv[++i] || "5") || 5;
    else if (a === "--min-time-ms") out.minTimeMs = Number(argv[++i] || "200") || 200;
    else if (a === "--max-attempts") out.maxAttempts = Number(argv[++i] || "2") || 2;
    else if (a === "--log-every") out.logEvery = Number(argv[++i] || "1") || 1;
  }
  return out;
}

function printHelp() {
  console.log(`
Run semantic fidelity judge over prompt jobs (JSONL) and write JSONL results (resumable).

Usage:
  node scripts/llm/run_semantic_fidelity_judge.js [options]

Options:
  --help, -h               Show this help and exit
  --dry-run                Print counts (total/selected/done/to_run) and exit
  --provider openai|gemini
  --model <model_id>       Default: openai=gpt-5-mini, gemini=gemini-2.5-flash
  --jobs <path>            Default: data/enrichment/semantic_fidelity_jobs_gpt.jsonl
  --out <path>             Default: data/enrichment/semantic_fidelity_results.jsonl
  --max <N>                Only process first N jobs from the jobs file
  --concurrency <N>        Default: env CONCURRENCY or 5
  --min-time-ms <ms>       Default: env MIN_TIME_MS or 200
  --max-attempts <N>       Default: env MAX_ATTEMPTS or 2
  --log-starts             Log when each job starts (can be noisy)
  --log-every <N>          Log every N completions (default 1; env LOG_EVERY)

Env:
  OpenAI: OPEN_AI_KEY (optionally OPENAI_BASE_URL)
  Gemini: GEMINI_API_KEY (or GOOGLE_API_KEY)
`);
}

function readJsonl(pathLike) {
  if (!fs.existsSync(pathLike)) return [];
  const raw = fs.readFileSync(pathLike, "utf8");
  const out = [];
  for (const line of raw.split(/\r?\n/)) {
    const t = line.trim();
    if (!t) continue;
    try {
      out.push(JSON.parse(t));
    } catch {
      // ignore bad lines
    }
  }
  return out;
}

function appendJsonlLine(jsonlPath, obj) {
  fs.mkdirSync(path.dirname(jsonlPath), { recursive: true });
  fs.appendFileSync(jsonlPath, JSON.stringify({ ts: utcNowIso(), ...obj }) + "\n");
}

function extractFirstJsonObject(text) {
  const s = String(text || "").trim();
  if (!s) throw new Error("Empty model output");
  // strip code fences
  let cleaned = s.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    throw new Error("Could not locate JSON object in model output");
  }
  cleaned = cleaned.slice(start, end + 1);
  return JSON.parse(cleaned);
}

// -------------------- OpenAI --------------------

function getOpenAiKey() {
  return (process.env.OPEN_AI_KEY || "").trim();
}

function extractTextFromOpenAiResponse(data) {
  if (!data) return "";
  if (typeof data.output_text === "string") return data.output_text;
  if (Array.isArray(data.output)) {
    for (const o of data.output) {
      const content = o?.content;
      if (!Array.isArray(content)) continue;
      for (const p of content) {
        if (typeof p?.text === "string") return p.text;
        if (typeof p?.output_text === "string") return p.output_text;
      }
    }
  }
  const cc = data?.choices?.[0]?.message?.content;
  if (typeof cc === "string") return cc;
  return "";
}

async function openAiJudgeJson({ apiKey, model, prompt }) {
  const OpenAI = require("openai");
  const baseURL = (process.env.OPENAI_BASE_URL || "").trim() || undefined;
  const client = new OpenAI({ apiKey, baseURL });

  const response = await client.responses.create({
    model,
    input: [
      {
        role: "system",
        content: [{ type: "input_text", text: "Return ONLY valid JSON. No markdown. No commentary." }],
      },
      {
        role: "user",
        content: [{ type: "input_text", text: prompt }],
      },
    ],
  });

  const outText = extractTextFromOpenAiResponse(response);
  return extractFirstJsonObject(outText);
}

// -------------------- Gemini --------------------

async function getGenAiClient(apiKey) {
  const mod = await import("@google/genai");
  const GoogleGenAI = mod.GoogleGenAI || mod.default?.GoogleGenAI;
  if (!GoogleGenAI) throw new Error("Failed to load GoogleGenAI from @google/genai");
  return new GoogleGenAI({ apiKey });
}

async function geminiJudgeJson({ apiKey, model, prompt }) {
  const client = await getGenAiClient(apiKey);
  const result = await client.models.generateContent({
    model,
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    config: {
      temperature: 0.0,
      responseMimeType: "application/json",
      // leave maxOutputTokens unset unless user configures externally; schema should keep it bounded
    },
  });
  const outText = result?.text || "";
  return extractFirstJsonObject(outText);
}

function getGeminiKey() {
  return (process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY || "").trim();
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    printHelp();
    return;
  }
  const provider = safeStr(args.provider);
  if (!["openai", "gemini"].includes(provider)) {
    console.error(`Unsupported --provider "${args.provider}". Use openai|gemini.`);
    process.exit(2);
  }
  if (!fs.existsSync(args.jobs)) {
    console.error(`Jobs file not found: ${args.jobs}`);
    process.exit(2);
  }

  const model = args.model || (provider === "openai" ? "gpt-5-mini" : "gemini-2.5-flash");
  const jobs = readJsonl(args.jobs);
  const max = args.max > 0 ? args.max : jobs.length;
  const selected = jobs.slice(0, max);

  const existing = readJsonl(args.out);
  const done = new Set(existing.map((r) => safeStr(r.case_id)).filter(Boolean));

  const toRun = selected.filter((j) => !done.has(safeStr(j.case_id)));

  console.log(`[judge] provider=${provider} model=${model}`);
  console.log(`[judge] jobs=${args.jobs}`);
  console.log(`[judge] out=${args.out}`);
  console.log(`[judge] total=${jobs.length} selected=${selected.length} already_done=${done.size} to_run=${toRun.length}`);

  if (args.dryRun) {
    console.log("[judge] dry-run: exiting before any model calls.");
    return;
  }

  if (provider === "openai" && !getOpenAiKey()) {
    console.error("Missing OPEN_AI_KEY env var for OpenAI provider.");
    process.exit(2);
  }
  if (provider === "gemini" && !getGeminiKey()) {
    console.error("Missing GEMINI_API_KEY (or GOOGLE_API_KEY) env var for Gemini provider.");
    process.exit(2);
  }

  const limiter = new Bottleneck({ maxConcurrent: args.concurrency, minTime: args.minTimeMs });

  let ok = 0;
  let fail = 0;

  const tasks = toRun.map((job, idx) =>
    limiter.schedule(async () => {
      const caseId = safeStr(job.case_id);
      const prompt = safeStr(job.prompt);
      if (!caseId || !prompt) {
        appendJsonlLine(args.out, { case_id: caseId || null, ok: false, error: "Missing case_id or prompt" });
        fail++;
        if ((ok + fail) % args.logEvery === 0) {
          console.log(`[fail] ${ok + fail}/${toRun.length} case_id=${caseId || "null"} error=missing_case_id_or_prompt`);
        }
        return;
      }

      if (args.logStarts) {
        console.log(`[start] ${idx + 1}/${toRun.length} case_id=${caseId}`);
      }

      const meta = {
        case_id: caseId,
        study: job.study || null,
        run_id: job.run_id || null,
        account_type: job.account_type || null,
        cited_listicle_url: job.cited_listicle_url || null,
        host_domain: job.host_domain || null,
        provider,
        model,
      };

      for (let attempt = 1; attempt <= args.maxAttempts; attempt++) {
        try {
          let parsed;
          if (provider === "openai") {
            parsed = await openAiJudgeJson({ apiKey: getOpenAiKey(), model, prompt });
          } else {
            parsed = await geminiJudgeJson({ apiKey: getGeminiKey(), model, prompt });
          }

          appendJsonlLine(args.out, { ...meta, ok: true, response: parsed });
          ok++;
          if ((ok + fail) % args.logEvery === 0) {
            console.log(`[ok] ${ok + fail}/${toRun.length} case_id=${caseId}`);
          }
          return;
        } catch (e) {
          const msg = String(e?.message || e);
          const willRetry = attempt < args.maxAttempts;
          if (!willRetry) {
            appendJsonlLine(args.out, { ...meta, ok: false, error: msg, attempt });
            fail++;
            if ((ok + fail) % args.logEvery === 0) {
              console.log(`[fail] ${ok + fail}/${toRun.length} case_id=${caseId} attempt=${attempt} error=${msg.slice(0, 180)}`);
            }
            return;
          }
          // simple backoff
          await new Promise((r) => setTimeout(r, 500 * attempt));
        }
      }
    })
  );

  await Promise.allSettled(tasks);

  console.log(`[judge] done ok=${ok} fail=${fail} wrote=${ok + fail} to ${args.out}`);
}

main().catch((e) => {
  console.error(`[judge] fatal: ${e?.message || e}`);
  process.exit(1);
});

