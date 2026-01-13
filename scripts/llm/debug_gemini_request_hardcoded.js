/**
 * Debug Gemini request (hardcoded URL + content).
 *
 * What this does:
 * - Loads the structured prompt template from prompts/page_label_prompt_v1.txt
 * - Loads extracted text from a local .txt file (hardcoded path below)
 * - Fills {URL}/{URL_DOMAIN}/{TITLE}/{SNIPPET_OR_META_DESCRIPTION}/{EXTRACTED_TEXT}
 * - Calls Gemini generateContent endpoint and prints:
 *   - HTTP status
 *   - Response body snippet
 *   - Parsed JSON keys (if valid)
 *
 * IMPORTANT:
 * - Do NOT hardcode API keys in this file.
 * - Provide GEMINI_API_KEY via environment variables.
 *
 * Run (Git Bash / PowerShell):
 *   node scripts/llm/debug_gemini_request_hardcoded.js
 *
 * Env:
 *   GEMINI_API_KEY=...   (preferred)
 *   GOOGLE_API_KEY=...
 *   GOOGLE_GENERATIVE_AI_API_KEY=...
 */

/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");

function getApiKey() {
  return (
    (process.env.GEMINI_API_KEY || "").trim() ||
    (process.env.GOOGLE_API_KEY || "").trim() ||
    (process.env.GOOGLE_GENERATIVE_AI_API_KEY || "").trim()
  );
}

function modelPath(model) {
  const m = (model || "").trim();
  if (!m) return "models/gemini-flash-latest";
  return m.startsWith("models/") ? m : `models/${m}`;
}

function urlDomain(u) {
  try {
    const url = new URL(u.includes("://") ? u : `https://${u}`);
    const host = (url.hostname || "").toLowerCase();
    return host.startsWith("www.") ? host.slice(4) : host;
  } catch {
    return "";
  }
}

function fillPrompt(template, { url, title, snippet, extractedText }) {
  const dom = urlDomain(url);
  return template
    .replaceAll("{URL}", url)
    .replaceAll("{URL_DOMAIN}", dom)
    .replaceAll("{TITLE}", title || "")
    .replaceAll("{SNIPPET_OR_META_DESCRIPTION}", snippet || "")
    .replaceAll("{EXTRACTED_TEXT}", extractedText || "");
}

async function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } finally {
    clearTimeout(t);
  }
}

async function main() {
  const apiKey = getApiKey();
  if (!apiKey) {
    console.error("Missing API key env var. Set GEMINI_API_KEY (preferred).");
    process.exit(2);
  }

  // -------------------------
  // Hardcoded debug inputs
  // -------------------------
  const MODEL = process.env.GEMINI_MODEL || "gemini-3-flash-preview";
  const TIMEOUT_MS = Number(process.env.GEMINI_TIMEOUT_MS || "90000"); // 90s
  const TEXT_MAX_CHARS = Number(process.env.TEXT_MAX_CHARS || "2000"); // shrink payload for debugging

  const URL_TO_TEST = "https://www.aiphone.ai/blog/best-real-time-translation-apps/";
  const TITLE = ""; // optional
  const SNIPPET = ""; // optional

  // Extracted text file (from your thesis folder). Adjust if needed.
  const CONTENT_TXT_PATH =
    "C:\\\\Users\\\\User\\\\Documents\\\\thesis\\\\bing_content\\\\bing_results_2026-01-08T15-14-19\\\\956a05a583e73cb8.txt";

  const promptPath = path.join(process.cwd(), "prompts", "page_label_prompt_v1.txt");
  const promptTemplate = fs.readFileSync(promptPath, "utf8");

  if (!fs.existsSync(CONTENT_TXT_PATH)) {
    console.error("Content file does not exist:", CONTENT_TXT_PATH);
    process.exit(2);
  }
  const extractedTextFull = fs.readFileSync(CONTENT_TXT_PATH, "utf8");
  const extractedText = extractedTextFull.slice(0, Math.max(0, TEXT_MAX_CHARS));

  const filled = fillPrompt(promptTemplate, {
    url: URL_TO_TEST,
    title: TITLE,
    snippet: SNIPPET,
    extractedText,
  });

  console.log("=== request summary ===");
  console.log("model:", modelPath(MODEL));
  console.log("timeout_ms:", TIMEOUT_MS);
  console.log("url:", URL_TO_TEST);
  console.log("text_sent_chars:", extractedText.length);
  console.log("prompt_chars:", filled.length);

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/${modelPath(MODEL)}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const payload = {
    contents: [{ role: "user", parts: [{ text: filled }] }],
    generationConfig: { temperature: 0.0 },
  };

  const t0 = Date.now();
  let res;
  try {
    res = await fetchWithTimeout(
      endpoint,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      TIMEOUT_MS,
    );
  } catch (e) {
    console.error("Request error:", e?.name || "Error", String(e?.message || e));
    process.exit(1);
  }

  const dtMs = Date.now() - t0;
  const body = await res.text();
  console.log("\n=== response ===");
  console.log("http_status:", res.status, res.statusText, `(${dtMs}ms)`);
  console.log("body_snippet:", (body || "").slice(0, 1200));

  if (!res.ok) process.exit(1);

  // Try parse expected structure
  try {
    const data = JSON.parse(body);
    const outText = data?.candidates?.[0]?.content?.parts?.[0]?.text || "";
    const cleaned = outText.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
    const parsed = JSON.parse(cleaned);
    console.log("\n=== parsed ===");
    console.log("top_level_keys:", Object.keys(parsed || {}));
  } catch (e) {
    console.error("\nParse error:", e?.name || "Error", String(e?.message || e));
    process.exit(1);
  }
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

