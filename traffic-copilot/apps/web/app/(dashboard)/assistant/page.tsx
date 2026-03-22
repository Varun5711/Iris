"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { BackendIncident } from "@/ui_lib/backend";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

interface ChatSession {
  id: string;
  incidentId?: string;
  title: string;
  time: string;
  messages: Message[];
}

function buildSessions(incidents: BackendIncident[]): ChatSession[] {
  const base: ChatSession[] = [
    {
      id: "sess-init",
      title: "CG Road Congestion Analysis",
      time: "Today, 10:24 AM",
      messages: [
        { id: "m1", role: "user", content: "Can you analyze the current congestion on SG Highway near ISCON Cross Roads?", timestamp: "10:24" },
        { id: "m2", role: "assistant", content: "I've analyzed real-time data from sensors CAM-018 and CAM-042. **Avoid SG Highway Main Route** for your 14:00 dispatch. Current traffic density is 22% higher than seasonal norms due to a minor lane blockage near ISCON.\n\n**Reasoning:** Live telemetry shows average speeds of 18 km/h between Prahladnagar and Bodakdev. Signal phase delays at the ISCON junction are compounding the backup.\n\n**Recommendation:** Use SP Ring Road via Satellite Road junction. ETA improvement: ~8 minutes.", timestamp: "10:24" },
      ],
    },
    { id: "sess-2", title: "Accident Impact: Swastik Cross Roads", time: "Yesterday", messages: [] },
    { id: "sess-3", title: "Weekly Flow Reports — Ahmedabad", time: "2 days ago", messages: [] },
    { id: "sess-4", title: "Camera CAM-031 Malfunction", time: "Oct 24, 2023", messages: [] },
  ];

  // Add real incidents as chat history items
  const incidentSessions: ChatSession[] = incidents.slice(0, 3).map((inc) => ({
    id: `inc-${inc.id}`,
    incidentId: inc.id,
    title: `${String(inc.severity ?? "").toUpperCase()} — ${inc.corridor_id ?? "Incident"} ${String(inc.id).slice(0, 6)}`,
    time: new Date(inc.created_at).toLocaleString(),
    messages: [],
  }));

  return [...incidentSessions, ...base];
}

function renderContent(text: string) {
  return text.split("\n").map((line, i) => {
    const parts = line.split(/\*\*(.*?)\*\*/g);
    return (
      <span key={i}>
        {parts.map((p, j) => j % 2 === 1 ? <strong key={j}>{p}</strong> : <span key={j}>{p}</span>)}
        {i < text.split("\n").length - 1 && <br />}
      </span>
    );
  });
}

export default function AssistantPage() {
  const [incidents, setIncidents] = useState<BackendIncident[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>(buildSessions([]));
  const [activeSessionId, setActiveSessionId] = useState("sess-init");
  const [messages, setMessages] = useState<Message[]>(buildSessions([])[0].messages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load real incidents for context
  const loadIncidents = useCallback(async () => {
    try {
      const res = await fetch("/api/incidents");
      const data: BackendIncident[] = await res.json();
      setIncidents(data);
      setSessions(buildSessions(data));
    } catch {}
  }, []);

  useEffect(() => {
    loadIncidents();
  }, [loadIncidents]);

  // Scroll to bottom on new messages
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Switch session
  const switchSession = (sess: ChatSession) => {
    // Save current messages
    setSessions((p) => p.map((s) => s.id === activeSessionId ? { ...s, messages } : s));
    setActiveSessionId(sess.id);
    setMessages(sess.messages);
  };

  const newChat = () => {
    const id = `sess-${Date.now()}`;
    const newSess: ChatSession = { id, title: "New Query", time: "Just now", messages: [] };
    setSessions((p) => [newSess, ...p]);
    setActiveSessionId(id);
    setMessages([]);
  };

  const send = async () => {
    if (!input.trim() || loading) return;
    const q = input.trim();
    setInput("");

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: q, timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) };
    setMessages((p) => [...p, userMsg]);
    setLoading(true);

    // Update session title from first user message
    setSessions((p) => p.map((s) => s.id === activeSessionId && s.messages.length === 0 ? { ...s, title: q.slice(0, 40) } : s));

    const assistantId = (Date.now() + 1).toString();
    setMessages((p) => [...p, { id: assistantId, role: "assistant", content: "", timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }]);

    // Route through backend — it handles Groq API key, incident context, and conversation history.
    const activeSession = sessions.find((s) => s.id === activeSessionId);
    const sessionIncidentId = activeSession?.incidentId;

    try {
      const body = sessionIncidentId
        ? { incidentId: sessionIncidentId, question: q, officerId: "officer-web" }
        : {
            messages: [
              ...messages.map((m) => ({ role: m.role, content: m.content })),
              { role: "user", content: q },
            ],
            officerId: "officer-web",
          };

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await res.json();
      const answer = d.answer ?? d.copilot_response?.conversational_answer ?? "I was unable to process your request.";
      setMessages((p) => p.map((m) => m.id === assistantId ? { ...m, content: answer } : m));
    } catch {
      setMessages((p) => p.map((m) => m.id === assistantId ? { ...m, content: "Connection error. Please try again." } : m));
    } finally {
      setLoading(false);
    }
  };

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  return (
    <div className="h-screen flex flex-col overflow-hidden pt-16">
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT: Chat History Sidebar */}
        <section className="w-80 flex flex-col bg-surface-container-low border-r border-outline-variant/10 shrink-0">
          <div className="p-4">
            <button onClick={newChat} className="w-full py-2.5 px-4 bg-white hover:bg-surface-container-lowest transition-all rounded-xl border border-outline-variant/20 flex items-center justify-center gap-2 text-primary font-semibold text-sm shadow-sm group">
              <span className="material-symbols-outlined text-lg transition-transform group-hover:rotate-90">add</span>
              New Intelligence Query
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 space-y-1 chat-scroll">
            {/* Recent incidents from backend */}
            {incidents.length > 0 && (
              <>
                <div className="px-2 py-2 text-[10px] font-bold text-primary uppercase tracking-widest flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-error animate-pulse"></span>
                  Active Incidents
                </div>
                {incidents.slice(0, 3).map((inc) => {
                  const sess = sessions.find((s) => s.id === `inc-${inc.id}`);
                  return (
                    <button
                      key={inc.id}
                      onClick={() => sess && switchSession(sess)}
                      className={`w-full text-left p-3 rounded-xl transition-all ${activeSessionId === `inc-${inc.id}` ? "bg-white border border-outline-variant/10 shadow-sm" : "hover:bg-white/50"}`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`w-1.5 h-1.5 rounded-full ${inc.severity === "critical" || inc.severity === "high" ? "bg-error" : "bg-primary"}`}></span>
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase">{String(inc.severity ?? "").toUpperCase()}</span>
                      </div>
                      <p className="text-xs font-medium text-on-surface truncate">{inc.description ?? inc.corridor_id ?? "Incident"}</p>
                      <p className="text-[10px] text-on-surface-variant mt-0.5">{new Date(inc.created_at).toLocaleTimeString()}</p>
                    </button>
                  );
                })}
              </>
            )}

            <div className="px-2 py-2 text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Recent Sessions</div>
            {sessions.filter((s) => !s.id.startsWith("inc-")).map((sess) => (
              <button
                key={sess.id}
                onClick={() => switchSession(sess)}
                className={`w-full text-left p-3 rounded-xl transition-all group ${activeSessionId === sess.id ? "bg-white border border-outline-variant/10 shadow-sm" : "hover:bg-white/50"}`}
              >
                <p className={`text-sm font-medium truncate transition-colors ${activeSessionId === sess.id ? "text-primary" : "text-on-surface group-hover:text-primary"}`}>
                  {sess.title}
                </p>
                <p className="text-[10px] text-on-surface-variant mt-1">{sess.time}</p>
              </button>
            ))}
          </div>

          {/* Context pills */}
          <div className="p-4 border-t border-outline-variant/10">
            <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-2">Active Context</p>
            <div className="flex flex-wrap gap-1">
              {incidents.slice(0, 2).map((i) => (
                <span key={i.id} className="text-[9px] font-bold px-2 py-0.5 bg-error/10 text-error rounded-full">{String(i.id).slice(0, 8).toUpperCase()}</span>
              ))}
              {["OSM Graph", "Groq LLM"].map((t) => (
                <span key={t} className="text-[9px] font-bold px-2 py-0.5 bg-primary-container/20 text-primary rounded-full">{t}</span>
              ))}
            </div>
          </div>
        </section>

        {/* CENTER: Conversation */}
        <section className="flex-1 flex flex-col bg-surface relative min-w-0">
          {/* Title bar */}
          {activeSession && (
            <div className="px-6 py-3 border-b border-outline-variant/10 shrink-0 flex items-center gap-3">
              <span className="material-symbols-outlined text-primary text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
              <div>
                <p className="text-sm font-bold text-on-surface">{activeSession.title}</p>
                <p className="text-[10px] text-on-surface-variant">{messages.length} messages · {loading ? "Thinking..." : "Ready"}</p>
              </div>
            </div>
          )}

          <div ref={scrollRef} className="flex-1 overflow-y-auto p-8 chat-scroll">
            <div className="max-w-3xl mx-auto space-y-8">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-48 gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-secondary-container flex items-center justify-center">
                    <span className="material-symbols-outlined text-3xl text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
                  </div>
                  <div className="text-center">
                    <p className="font-bold text-on-surface">IRIS Assistant Ready</p>
                    <p className="text-sm text-on-surface-variant mt-1">
                      {incidents.length > 0 ? `${incidents.length} active incident(s) loaded as context.` : "Ask about traffic, incidents, or route optimization."}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {[
                      "Analyze current congestion",
                      "Optimal route to Central Hospital",
                      "Signal re-timing recommendations",
                    ].map((s) => (
                      <button key={s} onClick={() => { setInput(s); textareaRef.current?.focus(); }} className="text-xs px-3 py-1.5 bg-surface-container-lowest rounded-full border border-outline-variant/20 text-primary hover:bg-primary/5 transition-colors">
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg) => (
                <div key={msg.id}>
                  {msg.role === "user" ? (
                    <div className="flex flex-col items-end">
                      <div className="max-w-[80%] bg-surface-container-highest px-5 py-3.5 rounded-2xl rounded-tr-none text-on-surface text-sm leading-relaxed">
                        {msg.content}
                      </div>
                      <span className="text-[10px] text-on-surface-variant mt-2 font-medium px-1">{msg.timestamp} • Delivered</span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-start">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-6 h-6 rounded bg-secondary-container flex items-center justify-center">
                          <span className="material-symbols-outlined text-[16px] text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
                        </div>
                        <span className="text-xs font-bold text-on-surface tracking-wide uppercase">IRIS Assistant</span>
                      </div>
                      <div className="w-full bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/10 relative overflow-hidden">
                        <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-secondary-container to-transparent opacity-50"></div>
                        <div className="text-on-surface leading-relaxed text-sm">
                          {msg.content
                            ? renderContent(msg.content)
                            : <span className="inline-flex gap-1">
                                {[0, 150, 300].map((d) => <span key={d} className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: `${d}ms` }}></span>)}
                              </span>}
                        </div>
                      </div>
                      <span className="text-[10px] text-on-surface-variant mt-2 font-medium px-1">IRIS • {msg.timestamp}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Input */}
          <div className="p-6 pt-0">
            <div className="max-w-3xl mx-auto">
              <div className="relative group">
                <div className="absolute inset-0 bg-primary/5 rounded-2xl blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity"></div>
                <div className="relative bg-surface-container-lowest rounded-2xl shadow-lg border border-outline-variant/20 p-2 flex items-end gap-2">
                  <button className="p-2 text-on-surface-variant hover:text-primary transition-colors">
                    <span className="material-symbols-outlined">add_circle</span>
                  </button>
                  <textarea
                    ref={textareaRef}
                    className="flex-1 bg-transparent border-none focus:ring-0 text-sm py-2 px-2 resize-none placeholder:text-on-surface-variant/50 outline-none"
                    placeholder="Ask IRIS about traffic or incidents..."
                    rows={1}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                  />
                  <div className="flex items-center gap-2 pb-1 pr-1">
                    <button className="p-2 text-on-surface-variant hover:text-primary transition-colors">
                      <span className="material-symbols-outlined">mic</span>
                    </button>
                    <button onClick={send} disabled={loading || !input.trim()} className="w-10 h-10 rounded-xl signature-gradient text-white flex items-center justify-center shadow-md hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50">
                      <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>send</span>
                    </button>
                  </div>
                </div>
              </div>
              <p className="text-center text-[10px] text-on-surface-variant/60 mt-3">
                IRIS uses live sensor data, camera feeds, and OSM graph for context. Backend: {incidents.length > 0 ? `${incidents.length} active incidents` : "simulation mode"}
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
