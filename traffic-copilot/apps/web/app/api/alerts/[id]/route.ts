import { NextRequest, NextResponse } from "next/server";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await req.json();
  const { action } = body;

  if (!["approve", "reject"].includes(action)) {
    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  }

  // In production this would write to the DB and trigger workflows
  console.log(`Alert action: ${action} on incident ${id}`);

  return NextResponse.json({
    success: true,
    incidentId: id,
    action,
    processedAt: new Date().toISOString(),
    message:
      action === "approve"
        ? "AI recommendations approved. Protocols initiated."
        : "Recommendations rejected. Manual review flagged.",
  });
}
