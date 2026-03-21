export default function AssistantPage() {
  return (
    <div className="h-screen flex flex-col overflow-hidden pt-16">
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT: Chat History Sidebar */}
        <section className="w-80 flex flex-col bg-surface-container-low border-r border-outline-variant/10 shrink-0">
          <div className="p-6">
            <button className="w-full py-3 px-4 bg-white hover:bg-surface-container-lowest transition-all rounded-xl border border-outline-variant/20 flex items-center justify-center gap-2 text-primary font-semibold text-sm shadow-sm group">
              <span className="material-symbols-outlined text-lg transition-transform group-hover:rotate-90">add</span>
              New Intelligence Query
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-4 space-y-2 chat-scroll">
            <div className="px-2 pb-2 text-[11px] font-bold text-on-surface-variant uppercase tracking-widest">Recent Activity</div>
            <button className="w-full text-left p-3 rounded-xl bg-white border border-outline-variant/10 shadow-sm transition-all">
              <p className="text-sm font-medium text-on-surface truncate">M4 Congestion Analysis</p>
              <p className="text-[11px] text-on-surface-variant mt-1">Today, 10:24 AM</p>
            </button>
            <button className="w-full text-left p-3 rounded-xl hover:bg-white/50 transition-all group">
              <p className="text-sm font-medium text-on-surface truncate group-hover:text-primary transition-colors">Accident Impact: Exit 12</p>
              <p className="text-[11px] text-on-surface-variant mt-1">Yesterday</p>
            </button>
            <button className="w-full text-left p-3 rounded-xl hover:bg-white/50 transition-all group">
              <p className="text-sm font-medium text-on-surface truncate group-hover:text-primary transition-colors">Weekly Flow Reports</p>
              <p className="text-[11px] text-on-surface-variant mt-1">2 days ago</p>
            </button>
            <button className="w-full text-left p-3 rounded-xl hover:bg-white/50 transition-all group">
              <p className="text-sm font-medium text-on-surface truncate group-hover:text-primary transition-colors">Camera 404 Malfunction</p>
              <p className="text-[11px] text-on-surface-variant mt-1">Oct 24, 2023</p>
            </button>
          </div>
        </section>

        {/* CENTER: Conversation Thread */}
        <section className="flex-1 flex flex-col bg-surface relative min-w-0">
          {/* Conversation Area */}
          <div className="flex-1 overflow-y-auto p-8 chat-scroll">
            <div className="max-w-3xl mx-auto space-y-10">
              {/* User Message */}
              <div className="flex flex-col items-end">
                <div className="max-w-[80%] bg-surface-container-highest px-5 py-3.5 rounded-2xl rounded-tr-none text-on-surface text-sm leading-relaxed">
                  Can you analyze the current congestion levels on the North Circular near the Central Hospital? We have a high-priority ambulance dispatch scheduled for 14:00.
                </div>
                <span className="text-[10px] text-on-surface-variant mt-2 font-medium px-1">13:42 • Delivered</span>
              </div>

              {/* IRIS Response */}
              <div className="flex flex-col items-start">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-6 h-6 rounded bg-secondary-container flex items-center justify-center">
                    <span className="material-symbols-outlined text-[16px] text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
                  </div>
                  <span className="text-xs font-bold text-on-surface tracking-wide uppercase">IRIS Assistant</span>
                </div>
                {/* Main Answer Card */}
                <div className="w-full bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/10 relative overflow-hidden">
                  {/* AI Identity Glow */}
                  <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-secondary-container to-transparent opacity-50"></div>
                  <div className="space-y-4">
                    <p className="text-on-surface leading-relaxed">
                      I&apos;ve analyzed real-time data from sensors 12-B and 14-A.{" "}
                      <span className="text-primary font-semibold">Avoid the North Circular Main Route</span> for your 14:00 dispatch. Current traffic density is 22% higher than seasonal norms due to a minor lane closure.
                    </p>
                    {/* Reasoning Block */}
                    <div className="bg-surface-container-low/50 rounded-xl p-4 border-l-4 border-primary/20">
                      <h4 className="text-[11px] font-bold text-primary uppercase mb-2">Reasoning Engine</h4>
                      <ul className="text-xs text-on-surface-variant space-y-2">
                        <li className="flex items-start gap-2">
                          <span className="w-1 h-1 rounded-full bg-primary-container mt-1.5 shrink-0"></span>
                          Live telemetry shows average speeds of 18mph between J4 and J5.
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="w-1 h-1 rounded-full bg-primary-container mt-1.5 shrink-0"></span>
                          Weather impact (light rain) is increasing braking distances by 15%.
                        </li>
                      </ul>
                    </div>
                    {/* Data References */}
                    <div className="grid grid-cols-2 gap-3 pt-2">
                      <div className="bg-surface-container-low rounded-lg p-3 flex items-center gap-3">
                        <span className="material-symbols-outlined text-on-surface-variant text-lg">videocam</span>
                        <div>
                          <p className="text-[10px] font-bold text-on-surface-variant uppercase">Feed NC-12</p>
                          <p className="text-xs text-primary font-medium">Clear Visibility</p>
                        </div>
                      </div>
                      <div className="bg-surface-container-low rounded-lg p-3 flex items-center gap-3">
                        <span className="material-symbols-outlined text-on-surface-variant text-lg">query_stats</span>
                        <div>
                          <p className="text-[10px] font-bold text-on-surface-variant uppercase">Flow Index</p>
                          <p className="text-xs text-error font-medium">Critical (0.84)</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <span className="text-[10px] text-on-surface-variant mt-2 font-medium px-1">IRIS • Just Now</span>
              </div>
            </div>
          </div>

          {/* BOTTOM: Input Area */}
          <div className="p-8 pt-0">
            <div className="max-w-3xl mx-auto">
              <div className="relative group">
                <div className="absolute inset-0 bg-primary/5 rounded-2xl blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity"></div>
                <div className="relative bg-surface-container-lowest rounded-2xl shadow-lg border border-outline-variant/20 p-2 flex items-end gap-2">
                  <button className="p-2 text-on-surface-variant hover:text-primary transition-colors">
                    <span className="material-symbols-outlined">add_circle</span>
                  </button>
                  <textarea
                    className="flex-1 bg-transparent border-none focus:ring-0 text-sm py-2 px-2 resize-none placeholder:text-on-surface-variant/50 outline-none"
                    placeholder="Ask IRIS about traffic or incidents..."
                    rows={1}
                  ></textarea>
                  <div className="flex items-center gap-2 pb-1 pr-1">
                    <button className="p-2 text-on-surface-variant hover:text-primary transition-colors">
                      <span className="material-symbols-outlined">mic</span>
                    </button>
                    <button className="w-10 h-10 rounded-xl signature-gradient text-white flex items-center justify-center shadow-md hover:shadow-primary/20 transition-all active:scale-95">
                      <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>send</span>
                    </button>
                  </div>
                </div>
              </div>
              <p className="text-center text-[10px] text-on-surface-variant/60 mt-4 tracking-tight">
                IRIS can process live sensor data, camera feeds, and historical patterns to assist your decision making.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
