export default function MapPage() {
  return (
    <main className="h-screen relative bg-[#E5E7EB] pt-16 overflow-hidden">
      {/* Map Background */}
      <div
        className="absolute inset-0 bg-cover bg-center"
        style={{
          backgroundImage: "url('https://lh3.googleusercontent.com/aida-public/AB6AXuAxSJPaUNh5Fq_kXI0GtPxI_ZFTd6Z0t7VsYRdx0h-nfD-1NPkMzA3E0s_fp9sJztHwxep-lhX3pExAWF66Sm00UfP_dlx8LZL9VI8VVNsEQaP2zTNrcSys6iaEggdmRI2endESipEPmRRfzTV9ZqPFw5OVOAGuowGWBprhh3KSdkebzw0r0r33l3V4oJmMfeaFMxHIB0IygYPklUyHjYPYY7IJCQzdEYpPLssxJQnSs4A1C54LWfG8sNcMojknJ9C1ZE_dPcf8vS1x')",
        }}
      >
        {/* Simulated Map Overlay (SVG Traffic Paths) */}
        <svg className="absolute inset-0 w-full h-full opacity-60 pointer-events-none">
          <path d="M0 200 L400 200 L800 500" fill="transparent" stroke="#2A6C0D" strokeWidth="6" />
          <path d="M200 0 L200 1000" fill="transparent" stroke="#2A6C0D" strokeWidth="4" />
          <path d="M400 200 L400 800" fill="transparent" stroke="#BA1A1A" strokeWidth="8" />
          <path d="M0 600 L1200 600" fill="transparent" stroke="#BA1A1A" strokeWidth="6" />
        </svg>
      </div>

      {/* Floating Search & Filter Bar */}
      <div className="absolute top-6 left-6 w-96 z-10">
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-2 flex items-center gap-2">
          <span className="material-symbols-outlined text-outline ml-2">search</span>
          <input
            className="flex-1 bg-transparent border-none focus:ring-0 text-sm py-2 text-on-surface placeholder:text-on-surface-variant/50 outline-none"
            placeholder="Search segments or addresses..."
            type="text"
          />
          <button className="p-2 hover:bg-surface-container-low rounded-lg transition-colors">
            <span className="material-symbols-outlined text-primary">tune</span>
          </button>
        </div>
      </div>

      {/* Right Side Overlays */}
      <div className="absolute top-6 right-6 flex flex-col gap-4 z-10">
        {/* Navigation Controls */}
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-1 flex flex-col items-center">
          <button className="p-3 hover:bg-surface-container-low rounded-lg transition-colors text-on-surface-variant">
            <span className="material-symbols-outlined">add</span>
          </button>
          <div className="w-8 h-[1px] bg-outline-variant/30"></div>
          <button className="p-3 hover:bg-surface-container-low rounded-lg transition-colors text-on-surface-variant">
            <span className="material-symbols-outlined">remove</span>
          </button>
          <div className="w-8 h-[1px] bg-outline-variant/30"></div>
          <button className="p-3 hover:bg-surface-container-low rounded-lg transition-colors text-on-surface-variant">
            <span className="material-symbols-outlined">my_location</span>
          </button>
        </div>

        {/* Layer Toggles */}
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-2 space-y-1 w-52">
          <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest px-2 py-1">Map Layers</h3>
          <button className="w-full flex items-center justify-between px-2 py-2 hover:bg-primary-container/10 rounded-lg text-sm text-primary font-medium">
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-lg">traffic</span> Traffic Flow
            </span>
            <div className="w-8 h-4 bg-primary rounded-full relative">
              <div className="absolute right-0.5 top-0.5 w-3 h-3 bg-white rounded-full"></div>
            </div>
          </button>
          <button className="w-full flex items-center justify-between px-2 py-2 hover:bg-surface-container-low rounded-lg text-sm text-on-surface-variant">
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-lg">warning</span> Incidents
            </span>
            <div className="w-8 h-4 bg-outline-variant rounded-full relative">
              <div className="absolute left-0.5 top-0.5 w-3 h-3 bg-white rounded-full"></div>
            </div>
          </button>
          <button className="w-full flex items-center justify-between px-2 py-2 hover:bg-surface-container-low rounded-lg text-sm text-on-surface-variant">
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-lg">traffic</span> Signal Status
            </span>
            <div className="w-8 h-4 bg-outline-variant rounded-full relative">
              <div className="absolute left-0.5 top-0.5 w-3 h-3 bg-white rounded-full"></div>
            </div>
          </button>
          <button className="w-full flex items-center justify-between px-2 py-2 hover:bg-surface-container-low rounded-lg text-sm text-on-surface-variant">
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-lg">videocam</span> CCTV Cameras
            </span>
            <div className="w-8 h-4 bg-primary rounded-full relative">
              <div className="absolute right-0.5 top-0.5 w-3 h-3 bg-white rounded-full"></div>
            </div>
          </button>
        </div>

        {/* Legend */}
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-4 w-52">
          <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-3">Traffic Intensity</h3>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="h-1.5 flex-1 rounded-full bg-primary"></div>
              <span className="text-[11px] font-semibold text-on-surface-variant">Smooth</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="h-1.5 flex-1 rounded-full bg-[#EAB308]"></div>
              <span className="text-[11px] font-semibold text-on-surface-variant">Moderate</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="h-1.5 flex-1 rounded-full bg-error"></div>
              <span className="text-[11px] font-semibold text-on-surface-variant">Congested</span>
            </div>
          </div>
        </div>
      </div>

      {/* Camera Pin with Popup */}
      <div className="absolute top-1/2 left-1/3 z-20">
        <div className="relative">
          <button className="w-10 h-10 bg-white rounded-full shadow-lg border-2 border-primary flex items-center justify-center text-primary hover:scale-110 transition-transform">
            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>videocam</span>
          </button>
          {/* Popup Preview */}
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-4 w-64 bg-surface-container-lowest rounded-xl shadow-2xl overflow-hidden border border-primary/20">
            <div className="relative h-36 bg-slate-900">
              <img
                alt="CCTV Feed"
                className="w-full h-full object-cover opacity-80"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDbuoLeNYnnqiAmzOxu8enM5UXNHhQe4EWbzM5FPoQ4jc3MpxRMdTLxoy4HUohnCwqtmoTM3UuFnHIjQZ1pgYkic9IHboqicYJcDD7wTmPhgRq5eP1f4ZPTPSAuinfDeIv1JFAs2WYCrsdCmbkipgUcLO7EJ7tTRUjErLW9aZYWr8GQEIMOBFVJ5sDKAwrz-EghzFxdF7wICxIgW0tXS5RG7emhROOwvJJX5qFCEdBcRKg9k8aOB6scC49Vq0fVovBTaxqnxqCW_1nh"
              />
              <div className="absolute top-2 left-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-600 animate-pulse"></span>
                <span className="text-[10px] font-bold text-white uppercase tracking-tighter">Live • CAM-042</span>
              </div>
            </div>
            <div className="p-3">
              <div className="flex justify-between items-start mb-1">
                <h4 className="text-xs font-bold text-on-surface">5th Ave & Broadway</h4>
                <span className="text-[10px] text-primary font-bold">12.4 MB/s</span>
              </div>
              <p className="text-[10px] text-on-surface-variant mb-3">Status: Normal Flow. No incidents detected.</p>
              <button className="w-full py-2 bg-primary text-white text-[10px] font-bold uppercase tracking-widest rounded-lg hover:shadow-lg transition-all">Full View</button>
            </div>
            <div className="w-0 h-0 border-l-[10px] border-l-transparent border-r-[10px] border-r-transparent border-t-[10px] border-t-white absolute top-full left-1/2 -translate-x-1/2"></div>
          </div>
        </div>
      </div>

      {/* Incident Pin */}
      <div className="absolute top-2/3 right-1/2 z-20">
        <button className="w-10 h-10 bg-error-container rounded-full shadow-lg border-2 border-error flex items-center justify-center text-error hover:scale-110 transition-transform">
          <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>warning</span>
        </button>
      </div>

      {/* AI Assistant Mini-Overlay (Bottom Left) */}
      <div className="absolute bottom-6 left-6 z-10">
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-4 w-72 border-b-4 border-secondary-container">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-secondary-container flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-lg">smart_toy</span>
            </div>
            <div>
              <h4 className="text-xs font-bold text-on-surface">IRIS Intelligence</h4>
              <p className="text-[10px] text-on-surface-variant">Active Monitoring</p>
            </div>
          </div>
          <p className="text-[11px] leading-relaxed text-on-surface-variant bg-surface-container-low p-2 rounded-lg italic">
            &ldquo;I&apos;ve detected a significant slowdown on the I-90 corridor. Would you like me to reroute incoming public transit?&rdquo;
          </p>
          <div className="mt-3 flex gap-2">
            <button className="flex-1 py-1.5 rounded-full bg-primary text-white text-[10px] font-bold">Approve</button>
            <button className="flex-1 py-1.5 rounded-full bg-surface-container-low text-on-surface-variant text-[10px] font-bold">Dismiss</button>
          </div>
        </div>
      </div>

      {/* Map/Satellite Toggle */}
      <div className="absolute bottom-6 right-6 z-10">
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-1 flex gap-1">
          <button className="px-3 py-2 bg-primary text-white rounded-lg text-xs font-bold">Map</button>
          <button className="px-3 py-2 hover:bg-surface-container-low text-on-surface-variant rounded-lg text-xs font-medium transition-colors">Satellite</button>
        </div>
      </div>
    </main>
  );
}
