import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const { messages, incidentId, question, officerId = "officer-web" } = await req.json();

  // Incident-specific query — use backend /chat/ with full incident context
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
      // fall through to general
    }
  }

  // General conversation — proxy full message history to backend /chat/general
  // Backend adds live incident context and calls Groq server-side
  try {
    const res = await fetch(`${BACKEND}/chat/general`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: messages ?? [], officer_id: officerId }),
      signal: AbortSignal.timeout(15000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json({ answer: data.answer });
    }
  } catch {}

  return NextResponse.json({ error: "LLM unavailable" }, { status: 500 });
}
