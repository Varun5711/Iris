export default function IncidentsPage() {
  return (
    <main className="min-h-screen bg-surface p-8 pt-24 pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
        <div>
          <nav className="flex items-center gap-2 text-xs font-medium text-on-surface-variant mb-3">
            <span className="hover:text-primary cursor-pointer transition-colors">Incidents</span>
            <span className="material-symbols-outlined text-[14px]">chevron_right</span>
            <span className="text-primary font-semibold">INC-8821</span>
          </nav>
          <h1 className="text-4xl font-extrabold tracking-tight text-on-surface mb-2">Major Traffic Congestion: HWY 101 North</h1>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <span className="flex items-center gap-1.5 font-semibold text-on-surface">
              <span className="material-symbols-outlined text-sm text-primary">location_on</span>
              Central District, Sector 4B
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-outline-variant"></span>
            <span className="flex items-center gap-1.5 text-on-surface-variant">
              <span className="material-symbols-outlined text-sm">schedule</span>
              Detected 14m ago (08:42 AM)
            </span>
            <span className="px-3 py-1 bg-error-container text-on-error-container font-bold rounded-full text-[10px] uppercase tracking-wider">High Severity</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button className="px-6 py-2.5 rounded-full font-bold text-sm text-primary hover:bg-primary/5 transition-colors">
            Export Report
          </button>
          <button className="px-8 py-2.5 rounded-full signature-gradient text-white font-bold text-sm shadow-md active:scale-95 transition-all">
            Initiate Protocol
          </button>
        </div>
      </div>

      {/* Bento Grid Layout */}
      <div className="grid grid-cols-12 gap-6">
        {/* LEFT: Incident Details & Timeline */}
        <div className="col-span-12 lg:col-span-3 space-y-6">
          {/* Description Card */}
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-widest text-primary mb-4">Description</h3>
            <p className="text-sm text-on-surface leading-relaxed mb-6">
              An unexpected 45% increase in traffic volume detected at the HWY 101 Northbound exit. Secondary congestion forming on Oak St and 5th Ave due to spill-back.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-surface p-3 rounded-lg">
                <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">Impact Radius</p>
                <p className="text-lg font-bold text-on-surface">1.2 km</p>
              </div>
              <div className="bg-surface p-3 rounded-lg">
                <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">Delay Est.</p>
                <p className="text-lg font-bold text-on-surface">+18m</p>
              </div>
            </div>
          </div>

          {/* Timeline Card */}
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-widest text-primary mb-6">Timeline of Events</h3>
            <div className="space-y-6 relative before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-[2px] before:bg-surface-container">
              <div className="relative pl-8">
                <div className="absolute left-0 top-1 w-[24px] h-[24px] bg-white border-4 border-primary rounded-full z-10"></div>
                <p className="text-[11px] font-bold text-primary uppercase">08:56 AM (Now)</p>
                <p className="text-sm font-semibold text-on-surface">Queue length exceeded 800m</p>
              </div>
              <div className="relative pl-8">
                <div className="absolute left-[6px] top-1.5 w-3 h-3 bg-surface-container rounded-full z-10"></div>
                <p className="text-[11px] font-bold text-on-surface-variant uppercase">08:48 AM</p>
                <p className="text-sm text-on-surface-variant">Congestion spillback to Oak Street</p>
              </div>
              <div className="relative pl-8">
                <div className="absolute left-[6px] top-1.5 w-3 h-3 bg-surface-container rounded-full z-10"></div>
                <p className="text-[11px] font-bold text-on-surface-variant uppercase">08:42 AM</p>
                <p className="text-sm text-on-surface-variant">Initial surge detected at Exit 22</p>
              </div>
            </div>
          </div>
        </div>

        {/* CENTER: Live Map */}
        <div className="col-span-12 lg:col-span-6 h-[600px] relative rounded-xl overflow-hidden bg-surface-container-low group">
          <div
            className="absolute inset-0 bg-cover bg-center transition-transform duration-700 group-hover:scale-105"
            style={{
              backgroundImage: "url('https://lh3.googleusercontent.com/aida-public/AB6AXuBjrcWz1ciK19wjz9z9v4nIDZzJM4ED-US14E2LXyaqRsViP8YFm6kfHoHwTQZn_qvzV9VhEiGizU5xRzC3tXaC_43Y2O_WlFodK1XzE-ydKEVj82gSZmdZEBJ5ClHkJ-IBpC5sMZaabZ7P9G8KzKRoRAxpFJyQmL7Xate_XxQoGlxWOjLStCJavLt5XFptHxZWii87GixVMq3GJcP0t3EXjjBX7Qa86JjvWE_Kt9hZCoPK2ghxZIKFVYuBXe_r2_8mTyom00AofP6C')",
            }}
          ></div>
          <div className="absolute inset-0 bg-black/10"></div>

          {/* Map Overlays */}
          <div className="absolute top-4 left-4 flex flex-col gap-2">
            <div className="bg-white/90 backdrop-blur-md p-3 rounded-lg shadow-xl">
              <p className="text-[10px] font-bold uppercase text-on-surface-variant mb-2">Map Layers</p>
              <div className="flex gap-2">
                <button className="w-8 h-8 rounded bg-primary text-white flex items-center justify-center shadow-sm">
                  <span className="material-symbols-outlined text-sm">traffic</span>
                </button>
                <button className="w-8 h-8 rounded bg-white text-on-surface flex items-center justify-center border border-outline-variant/20">
                  <span className="material-symbols-outlined text-sm">videocam</span>
                </button>
                <button className="w-8 h-8 rounded bg-white text-on-surface flex items-center justify-center border border-outline-variant/20">
                  <span className="material-symbols-outlined text-sm">sensors</span>
                </button>
              </div>
            </div>
          </div>

          <div className="absolute bottom-4 left-4 right-4 bg-white/90 backdrop-blur-md p-4 rounded-xl shadow-2xl flex items-center justify-between border border-white">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-error-container/20 flex items-center justify-center">
                <span className="material-symbols-outlined text-error" style={{ fontVariationSettings: "'FILL' 1" }}>emergency_share</span>
              </div>
              <div>
                <p className="text-xs font-bold text-on-surface">Traffic Center HWY 101</p>
                <p className="text-xs text-on-surface-variant">Intersection Status: <span className="text-error font-bold">Critical Delay</span></p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-on-surface-variant bg-surface-container px-2 py-1 rounded">ZOOM: 18x</span>
              <span className="text-[10px] font-bold text-on-surface-variant bg-surface-container px-2 py-1 rounded">LAT: 34.0522</span>
            </div>
          </div>
        </div>

        {/* RIGHT: AI Recommendations */}
        <div className="col-span-12 lg:col-span-3 space-y-6">
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm border-b-4 border-secondary-container">
            <div className="flex items-center gap-2 mb-6">
              <div className="w-8 h-8 bg-secondary-container rounded-full flex items-center justify-center">
                <span className="material-symbols-outlined text-primary text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
              </div>
              <h3 className="text-sm font-bold text-on-surface">IRIS AI Recommendations</h3>
            </div>
            <div className="space-y-6">
              {/* Recommendation 1 */}
              <div className="p-4 bg-surface rounded-xl border-l-4 border-primary">
                <p className="text-[10px] font-bold text-primary uppercase mb-1">Signal Strategy</p>
                <p className="text-sm font-semibold text-on-surface mb-2">Adjust Cycle Pattern A-42</p>
                <p className="text-xs text-on-surface-variant mb-3">Increase green-time for Northbound flow by 15s to flush the exit queue.</p>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] bg-primary-fixed text-on-primary-fixed px-2 py-0.5 rounded font-bold">High Impact</span>
                  <span className="text-[10px] text-on-surface-variant">Est. recovery: 12m</span>
                </div>
              </div>
              {/* Recommendation 2 */}
              <div className="p-4 bg-surface rounded-xl border-l-4 border-primary">
                <p className="text-[10px] font-bold text-primary uppercase mb-1">Diversion Route</p>
                <p className="text-sm font-semibold text-on-surface mb-2">Activate VMS Signs Sector 4</p>
                <p className="text-xs text-on-surface-variant mb-3">Redirect non-essential traffic to alternate Route 7 bypass.</p>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-bold">Moderate</span>
                  <span className="text-[10px] text-on-surface-variant">Impact: -20% Vol.</span>
                </div>
              </div>
              {/* Confidence Score */}
              <div className="pt-4 border-t border-surface-container">
                <div className="flex justify-between items-end mb-2">
                  <p className="text-[10px] font-bold text-on-surface-variant uppercase">Confidence Score</p>
                  <p className="text-lg font-bold text-primary">94%</p>
                </div>
                <div className="w-full h-1.5 bg-surface-container rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full w-[94%]"></div>
                </div>
              </div>
            </div>
            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-3 mt-8">
              <button className="py-3 rounded-full bg-white border border-outline-variant/30 text-error font-bold text-sm hover:bg-error/5 transition-colors">
                Reject
              </button>
              <button className="py-3 rounded-full signature-gradient text-white font-bold text-sm shadow-lg active:scale-95 transition-all">
                Approve
              </button>
            </div>
          </div>

          {/* Affected Assets */}
          <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
            <h4 className="text-[10px] font-bold uppercase text-on-surface-variant mb-4">Affected Assets</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-lg text-on-surface-variant">traffic</span>
                  <span className="text-xs font-medium text-on-surface">Signals 101-A, 101-B</span>
                </div>
                <span className="w-2 h-2 rounded-full bg-primary"></span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-lg text-on-surface-variant">screenshot_monitor</span>
                  <span className="text-xs font-medium text-on-surface">VMS Panel 04, 05</span>
                </div>
                <span className="w-2 h-2 rounded-full bg-primary"></span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-lg text-on-surface-variant">camera_outdoor</span>
                  <span className="text-xs font-medium text-on-surface">CCTV Cam 22-North</span>
                </div>
                <span className="w-2 h-2 rounded-full bg-primary"></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
