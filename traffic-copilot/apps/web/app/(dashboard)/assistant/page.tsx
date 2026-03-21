"use client";

import { useEffect, useRef, useState } from "react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

const INITIAL_MESSAGES: Message[] = [
  {
    id: "init-1",
    role: "user",
    content: "Can you analyze the current congestion levels on the North Circular near the Central Hospital? We have a high-priority ambulance dispatch scheduled for 14:00.",
    timestamp: "13:42",
  },
  {
    id: "init-2",
    role: "assistant",
    content: "I've analyzed real-time data from sensors 12-B and 14-A. **Avoid the North Circular Main Route** for your 14:00 dispatch. Current traffic density is 22% higher than seasonal norms due to a minor lane closure.\n\n**Reasoning Engine:**\n- Live telemetry shows average speeds of 18mph between J4 and J5.\n- Weather impact (light rain) is increasing braking distances by 15%.\n\n**Recommendation:** Use the Eastern Bypass via Route 7. ETA improvement: ~8 minutes.",
    timestamp: "13:42",
  },
];

const CHAT_HISTORY = [
  { title: "M4 Congestion Analysis", time: "Today, 10:24 AM", active: true },
  { title: "Accident Impact: Exit 12", time: "Yesterday" },
  { title: "Weekly Flow Reports", time: "2 days ago" },
  { title: "Camera 404 Malfunction", time: "Oct 24, 2023" },
];

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeChat, setActiveChat] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const userText = input.trim();
    setInput("");

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((p) => [...p, userMsg]);
    setLoading(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages((p) => [
      ...p,
      { id: assistantId, role: "assistant", content: "", timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) },
    ]);

    try {
      const apiMessages = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }));
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: apiMessages }),
      });

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let full = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          const lines = chunk.split("\n").filter((l) => l.startsWith("data: "));
          for (const line of lines) {
            const data = line.slice(6);
            if (data === "[DONE]") continue;
            try {
              const parsed = JSON.parse(data);
              const delta = parsed.choices?.[0]?.delta?.content || "";
              full += delta;
              setMessages((p) =>
                p.map((m) => (m.id === assistantId ? { ...m, content: full } : m))
              );
            } catch {
              // skip
            }
          }
        }
      }
    } catch {
      setMessages((p) =>
        p.map((m) =>
          m.id === assistantId ? { ...m, content: "Connection error. Please try again." } : m
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const newChat = () => {
    setMessages([]);
    setActiveChat(-1);
  };

  const renderContent = (text: string) => {
    // Simple bold formatting
    return text.split("\n").map((line, i) => {
      const parts = line.split(/\*\*(.*?)\*\*/g);
      return (
        <span key={i}>
          {parts.map((part, j) =>
            j % 2 === 1 ? <strong key={j}>{part}</strong> : <span key={j}>{part}</span>
          )}
          {i < text.split("\n").length - 1 && <br />}
        </span>
      );
    });
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden pt-16">
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT: Chat History Sidebar */}
        <section className="w-80 flex flex-col bg-surface-container-low border-r border-outline-variant/10 shrink-0">
          <div className="p-6">
            <button
              onClick={newChat}
              className="w-full py-3 px-4 bg-white hover:bg-surface-container-lowest transition-all rounded-xl border border-outline-variant/20 flex items-center justify-center gap-2 text-primary font-semibold text-sm shadow-sm group"
            >
              <span className="material-symbols-outlined text-lg transition-transform group-hover:rotate-90">add</span>
              New Intelligence Query
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-4 space-y-2 chat-scroll">
            <div className="px-2 pb-2 text-[11px] font-bold text-on-surface-variant uppercase tracking-widest">Recent Activity</div>
            {CHAT_HISTORY.map((chat, i) => (
              <button
                key={i}
                onClick={() => setActiveChat(i)}
                className={`w-full text-left p-3 rounded-xl transition-all ${
                  activeChat === i
                    ? "bg-white border border-outline-variant/10 shadow-sm"
                    : "hover:bg-white/50"
                }`}
              >
                <p className={`text-sm font-medium truncate transition-colors ${activeChat === i ? "text-primary" : "text-on-surface group-hover:text-primary"}`}>
                  {chat.title}
                </p>
                <p className="text-[11px] text-on-surface-variant mt-1">{chat.time}</p>
              </button>
            ))}
          </div>

          {/* Context Pills */}
          <div className="p-4 border-t border-outline-variant/10">
            <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-2">Active Context</p>
            <div className="flex flex-wrap gap-1">
              {["HWY 101", "CAM-042", "Sector 4B"].map((tag) => (
                <span key={tag} className="text-[10px] font-bold px-2 py-0.5 bg-primary-container/20 text-primary rounded-full">{tag}</span>
              ))}
            </div>
          </div>
        </section>

        {/* CENTER: Conversation */}
        <section className="flex-1 flex flex-col bg-surface relative min-w-0">
          {/* Conversation Area */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-8 chat-scroll">
            <div className="max-w-3xl mx-auto space-y-10">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-48 gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-secondary-container flex items-center justify-center">
                    <span className="material-symbols-outlined text-3xl text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
                  </div>
                  <div className="text-center">
                    <p className="font-bold text-on-surface">IRIS Assistant Ready</p>
                    <p className="text-sm text-on-surface-variant mt-1">Ask me about traffic, incidents, or route optimization.</p>
                  </div>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {["Analyze current congestion", "Optimal ambulance route to Central Hospital", "Traffic forecast for next 2 hours"].map((s) => (
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
                          {msg.content ? renderContent(msg.content) : (
                            <span className="inline-flex gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "0ms" }}></span>
                              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "150ms" }}></span>
                              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "300ms" }}></span>
                            </span>
                          )}
                        </div>
                      </div>
                      <span className="text-[10px] text-on-surface-variant mt-2 font-medium px-1">IRIS • {msg.timestamp}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Input Area */}
          <div className="p-8 pt-0">
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
                    onKeyDown={handleKeyDown}
                  />
                  <div className="flex items-center gap-2 pb-1 pr-1">
                    <button className="p-2 text-on-surface-variant hover:text-primary transition-colors">
                      <span className="material-symbols-outlined">mic</span>
                    </button>
                    <button
                      onClick={send}
                      disabled={loading || !input.trim()}
                      className="w-10 h-10 rounded-xl signature-gradient text-white flex items-center justify-center shadow-md hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50"
                    >
                      <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>send</span>
                    </button>
                  </div>
                </div>
              </div>
              <p className="text-center text-[10px] text-on-surface-variant/60 mt-4 tracking-tight">
                IRIS processes live sensor data, camera feeds, and historical patterns to assist decision making.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
