import { NextRequest } from "next/server";

const GROQ_API_KEY = process.env.GROQ_API_KEY!;
const GROQ_MODEL = process.env.GROQ_MODEL || "llama-3.3-70b-versatile";

const SYSTEM_PROMPT = `You are IRIS (Intelligent Road Infrastructure System), an advanced AI traffic management assistant for the Central District traffic control center.

You have access to real-time traffic data, camera feeds, sensor networks, and historical patterns. You speak concisely and professionally, like an expert traffic analyst.

Current system status:
- Active incidents: 4 (1 critical on HWY 101)
- Vehicle count: ~137 vehicles/min
- Avg speed: 35 MPH (below normal due to congestion)
- Signal efficiency: 94.2%
- Weather: Light rain, reducing visibility by 15%

Provide specific, actionable traffic management recommendations. Keep responses focused and under 150 words unless detailed analysis is requested.`;

export async function POST(req: NextRequest) {
  const { messages } = await req.json();

  const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${GROQ_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: GROQ_MODEL,
      messages: [{ role: "system", content: SYSTEM_PROMPT }, ...messages],
      stream: true,
      temperature: 0.3,
      max_tokens: 512,
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    return new Response(JSON.stringify({ error: err }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Stream the response back
  return new Response(response.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
