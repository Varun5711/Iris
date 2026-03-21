export default function AnalyticsPage() {
  return (
    <main className="min-h-screen bg-surface p-8 pt-24">
      {/* Header Section */}
      <div className="flex items-end justify-between mb-8">
        <div>
          <h3 className="text-3xl font-extrabold text-on-surface tracking-tight mb-1">District Analytics</h3>
          <p className="text-on-surface-variant text-sm font-medium">System-wide performance monitoring and traffic flow intelligence.</p>
        </div>
        <div className="flex gap-3">
          <button className="px-5 py-2 text-sm font-semibold text-primary hover:bg-primary/5 rounded-full transition-all">
            Export Report
          </button>
          <button className="px-6 py-2 text-sm font-semibold text-white signature-gradient rounded-full shadow-md hover:brightness-110 active:scale-95 transition-all">
            Live Monitor
          </button>
        </div>
      </div>

      {/* KPI Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <span className="p-2 bg-primary-container/20 text-primary rounded-lg material-symbols-outlined">emergency</span>
            <span className="text-xs font-bold text-primary flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">trending_down</span> 12%
            </span>
          </div>
          <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Total Incidents (Week)</p>
          <h4 className="text-3xl font-bold text-on-surface">142</h4>
          <div className="mt-4 h-1 w-full bg-surface-container rounded-full overflow-hidden">
            <div className="h-full bg-primary rounded-full w-[65%]"></div>
          </div>
        </div>

        <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <span className="p-2 bg-secondary-container text-on-secondary-container rounded-lg material-symbols-outlined">timer</span>
            <span className="text-xs font-bold text-primary flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">arrow_downward</span> 2.4m
            </span>
          </div>
          <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Avg Response Time</p>
          <h4 className="text-3xl font-bold text-on-surface">6.8 <span className="text-sm font-medium opacity-50">min</span></h4>
          <div className="mt-4 flex gap-1 h-1">
            <div className="flex-1 bg-primary rounded-full"></div>
            <div className="flex-1 bg-primary rounded-full"></div>
            <div className="flex-1 bg-primary rounded-full"></div>
            <div className="flex-1 bg-surface-container rounded-full"></div>
            <div className="flex-1 bg-surface-container rounded-full"></div>
          </div>
        </div>

        <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <span className="p-2 bg-tertiary-container/20 text-tertiary rounded-lg material-symbols-outlined">traffic</span>
            <span className="text-xs font-bold text-on-surface-variant flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">remove</span> Stable
            </span>
          </div>
          <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Signal Efficiency</p>
          <h4 className="text-3xl font-bold text-on-surface">94.2%</h4>
          <div className="mt-4 h-1 w-full bg-surface-container rounded-full overflow-hidden">
            <div className="h-full bg-tertiary rounded-full w-[94%]"></div>
          </div>
        </div>
      </div>

      {/* Charts Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Traffic Trends (Large) */}
        <div className="lg:col-span-2 bg-surface-container-lowest rounded-xl shadow-sm p-6">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h5 className="font-bold text-on-surface">Traffic Trends</h5>
              <p className="text-xs text-on-surface-variant">Vehicle counts over last 24 hours</p>
            </div>
            <select className="bg-surface border-0 text-xs font-bold rounded-full px-4 py-2 ring-1 ring-outline-variant/10 focus:outline-none">
              <option>Last 24 Hours</option>
              <option>Last 7 Days</option>
            </select>
          </div>
          <div className="relative h-64 w-full">
            <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 800 250">
              <defs>
                <linearGradient id="chartGradient2" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#2a6c0d" stopOpacity="0.1" />
                  <stop offset="100%" stopColor="#2a6c0d" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d="M0 250 Q 50 200 100 220 T 200 150 T 300 180 T 400 100 T 500 130 T 600 80 T 700 110 T 800 50 L 800 250 L 0 250 Z" fill="url(#chartGradient2)" stroke="none" />
              <path d="M0 250 Q 50 200 100 220 T 200 150 T 300 180 T 400 100 T 500 130 T 600 80 T 700 110 T 800 50" fill="none" stroke="#2a6c0d" strokeWidth="1.5" />
              <circle cx="600" cy="80" fill="#2a6c0d" r="4" />
            </svg>
            <div className="absolute top-[55px] left-[71%] bg-white shadow-xl px-2 py-1 rounded text-[10px] font-bold border border-primary/20">
              18:00 — 4.2k vehicles
            </div>
          </div>
          <div className="flex justify-between mt-4 text-[10px] font-bold text-on-surface-variant tracking-wider uppercase">
            <span>00:00</span>
            <span>06:00</span>
            <span>12:00</span>
            <span>18:00</span>
            <span>23:59</span>
          </div>
        </div>

        {/* Congestion Heatmap */}
        <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col">
          <div className="p-6">
            <h5 className="font-bold text-on-surface">Congestion Heatmap</h5>
            <p className="text-xs text-on-surface-variant">Active intersection density</p>
          </div>
          <div className="flex-1 relative m-4 mt-0 bg-surface rounded-lg overflow-hidden min-h-[200px]">
            <img
              alt="City Traffic Heatmap"
              className="w-full h-full object-cover grayscale opacity-40"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuDdwxJSS0SZ6GWzhh2JYmOwvlDoi8ZsKcvIlYPpUwN5v92fGce3DgXI_pgvVzRExmXV06K892Ww_rCGwVBIDy1f_ACkgB7c9f337f_6TXqNjfF7X3jDTBUfEuXAHO1SbTZl6kNt6PrINGGvsyPLQGnRcuqeim4IBuhRQCtq-J6EIuA4WVCq7pbbtjl8Pi5nbuu-kTQPYQrAF6wwCnKWvuAhtwllkIbgqt_nh4aJzh0hybd5QWTy-I0iIvlhoHH6ODsPiYx9RmDYelMK"
            />
            <div className="absolute top-1/4 left-1/3 w-16 h-16 bg-error/20 rounded-full blur-xl"></div>
            <div className="absolute top-1/2 left-1/2 w-24 h-24 bg-primary/20 rounded-full blur-2xl"></div>
            <div className="absolute bottom-1/4 right-1/4 w-12 h-12 bg-error/30 rounded-full blur-lg"></div>
            <div className="absolute top-1/4 left-1/3 flex flex-col items-center">
              <span className="w-3 h-3 bg-error rounded-full ring-4 ring-error/20"></span>
              <div className="mt-1 bg-white px-2 py-0.5 rounded shadow text-[9px] font-bold whitespace-nowrap">Hills Rd Jct</div>
            </div>
          </div>
          <div className="p-6 pt-0 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-error"></span>
                <span className="text-xs font-medium">Critical (4 Intersections)</span>
              </div>
              <span className="material-symbols-outlined text-sm text-on-surface-variant cursor-pointer">chevron_right</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-primary-container"></span>
                <span className="text-xs font-medium">Fluid (12 Intersections)</span>
              </div>
              <span className="material-symbols-outlined text-sm text-on-surface-variant cursor-pointer">chevron_right</span>
            </div>
          </div>
        </div>

        {/* Avg Speed by District */}
        <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6 lg:col-span-1">
          <h5 className="font-bold text-on-surface mb-1">Avg Speed by District</h5>
          <p className="text-xs text-on-surface-variant mb-6">Kilometers per hour (km/h)</p>
          <div className="space-y-6">
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] font-bold">
                <span className="text-on-surface-variant">CENTRAL HUB</span>
                <span className="text-primary">34 km/h</span>
              </div>
              <div className="h-2 w-full bg-surface rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full w-[45%]"></div>
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] font-bold">
                <span className="text-on-surface-variant">NORTHERN GATEWAY</span>
                <span className="text-primary">52 km/h</span>
              </div>
              <div className="h-2 w-full bg-surface rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full w-[72%]"></div>
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] font-bold">
                <span className="text-on-surface-variant">WEST END TERMINAL</span>
                <span className="text-primary">28 km/h</span>
              </div>
              <div className="h-2 w-full bg-surface rounded-full overflow-hidden">
                <div className="h-full bg-primary-container rounded-full w-[38%]"></div>
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] font-bold">
                <span className="text-on-surface-variant">SOUTH PARKWAY</span>
                <span className="text-primary">48 km/h</span>
              </div>
              <div className="h-2 w-full bg-surface rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full w-[65%]"></div>
              </div>
            </div>
          </div>
          <div className="mt-8 p-4 bg-secondary-container rounded-lg">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-on-secondary-container">lightbulb</span>
              <div>
                <p className="text-xs font-bold text-on-secondary-container leading-tight">Optimization Tip</p>
                <p className="text-[10px] text-on-secondary-container/80 mt-1">Adjusting signal 42 in West End could improve flow by 14%.</p>
              </div>
            </div>
          </div>
        </div>

        {/* AI Copilot Insight */}
        <div className="lg:col-span-2 bg-surface-container-lowest rounded-xl shadow-sm border-b-4 border-secondary-container relative overflow-hidden flex flex-col md:flex-row">
          <div className="p-8 md:w-2/3">
            <div className="flex items-center gap-2 mb-4">
              <span className="material-symbols-outlined text-primary">auto_awesome</span>
              <h5 className="text-sm font-bold text-on-surface uppercase tracking-widest">IRIS Intelligence Insight</h5>
            </div>
            <p className="text-lg font-medium text-on-surface mb-4 leading-relaxed">
              Anomalous traffic pattern detected on{" "}
              <span className="text-primary font-bold underline decoration-primary/30">Kings Highway</span>. Current congestion is 22% higher than seasonal average for a Tuesday afternoon.
            </p>
            <div className="flex gap-4">
              <button className="text-xs font-bold py-2 px-4 rounded-full bg-surface ring-1 ring-outline-variant/20 hover:bg-surface-container-high transition-all">Show Details</button>
              <button className="text-xs font-bold py-2 px-4 rounded-full text-white signature-gradient transition-all">Optimize Route</button>
            </div>
          </div>
          <div className="md:w-1/3 bg-secondary-container/20 flex items-center justify-center p-8">
            <div className="w-32 h-32 rounded-full border-4 border-white shadow-lg bg-white flex items-center justify-center">
              <span className="material-symbols-outlined text-5xl text-primary font-light">psychology</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-12 flex justify-between items-center text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] opacity-50">
        <div>© 2024 IRIS Civil Solutions</div>
        <div className="flex gap-4">
          <a className="hover:text-primary transition-colors" href="#">Documentation</a>
          <a className="hover:text-primary transition-colors" href="#">Privacy</a>
          <a className="hover:text-primary transition-colors" href="#">API Access</a>
        </div>
      </footer>
    </main>
  );
}
