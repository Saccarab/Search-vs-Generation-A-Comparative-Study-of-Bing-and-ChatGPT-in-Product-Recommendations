import { GoogleGenAI } from '@google/genai';

// Initialize the client (automatically looks for GEMINI_API_KEY if not passed)
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

async function inspectGroundingParameters() {
  const modelId = 'gemini-3-flash-preview'; // 2026 stable research model
  const prompt = "Which app or AI tool can I use to get the transcript of an audio?";

  console.log(`--- Running Inspection for: "${prompt}" ---\n`);

  try {
    const response = await ai.models.generateContent({
      model: modelId,
      contents: prompt,
      config: {
        tools: [{ googleSearch: {} }], // Enable grounding
        thinkingConfig: {
          thinkingLevel: 'minimal', // Options: 'minimal', 'low', 'medium', 'high'
          includeThoughts: true     // Recommended for your thesis audit trail
        },
      },
    });

    // Navigate to the 2026 groundingMetadata structure
    const candidate = response.candidates[0];
    const metadata = candidate.groundingMetadata;

    console.log("=== 1. WEB SEARCH QUERIES ===");
    // These are the queries Gemini actually sent to Google
    console.log(metadata.webSearchQueries || "No queries run.");

    console.log("\n=== 2. GROUNDING CHUNKS (THE MENU) ===");
    // This is the Top results list Google provided to Gemini
    metadata.groundingChunks.forEach((chunk, i) => {
      console.log(`[Source ${i}]`);
      console.log(`Title: ${chunk.web?.title}`);
      console.log(`URL: ${chunk.web?.uri}`);
    });

    console.log("\n=== 3. GROUNDING SUPPORTS (THE FILTER) ===");
    // This shows which parts of the AI text survived from which source
    metadata.groundingSupports.forEach((support, i) => {
      console.log(`Support [${i}]:`);
      console.log(`> Segment: "${support.segment.text}"`);
      console.log(`> Linked to Chunks: [${support.groundingChunkIndices}]`);
      console.log(`> Confidence: ${support.confidenceScores ? support.confidenceScores : 'N/A'}`);
    });

    // The raw final text for reference
    console.log("\n=== FINAL AI RESPONSE ===");
    console.log(candidate.content.parts[0].text);

  } catch (error) {
    console.error("Inspection Failed:", error);
  }
}
inspectGroundingParameters();