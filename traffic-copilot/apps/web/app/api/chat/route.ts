import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const GROQ_API_KEY = process.env.GROQ_API_KEY!;
const GROQ_MODEL = process.env.GROQ_MODEL || "llama-3.3-70b-versatile";

const SYSTEM_PROMPT = `You are IRIS (Intelligent Road Infrastructure System), an advanced AI traffic management assistant.

You have access to real-time traffic data, camera feeds, sensor networks, and historical patterns.
Speak concisely and professionally like an expert traffic analyst.

Current system: Central District, Manhattan. Active incidents on HWY 101 (critical congestion).
Provide specific, actionable traffic management recommendations. Keep responses under 200 words unless detailed analysis is requested.`;

export async function POST(req: NextRequest) {
  const { messages, incidentId, question, officerId = "officer-web" } = await req.json();

  // Try backend first (has full incident context, OSM graph data, etc)
  if (incidentId && question) {
    try {
      const res = await fetch(`${BACKEND}/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_id: incidentId, question, officer_id: officerId }),
        signal: AbortSignal.timeout(15000),
      });
      if (res.ok) {
        const rec = await res.json();
        const answer =
          rec.copilot_response?.conversational_answer ||
          rec.copilot_response?.narrative ||
          rec.action ||
          "I've processed your query.";
        return NextResponse.json({ answer, recommendation: rec });
      }
    } catch {
      // fall through to Groq
    }
  }

  // Fallback: direct Groq streaming
  const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${GROQ_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: GROQ_MODEL,
      messages: [{ role: "system", content: SYSTEM_PROMPT }, ...(messages ?? [])],
      stream: true,
      temperature: 0.3,
      max_tokens: 512,
    }),
  });

  if (!response.ok) {
    return NextResponse.json({ error: "LLM unavailable" }, { status: 500 });
  }

  return new Response(response.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
