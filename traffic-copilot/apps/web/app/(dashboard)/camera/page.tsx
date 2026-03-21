export default function CameraFeedsPage() {
  return (
    <main className="min-h-screen bg-surface p-8 pt-24 space-y-8">
      {/* Header Section */}
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-on-surface">Camera Feeds</h2>
          <p className="text-on-surface-variant mt-1">Real-time surveillance monitoring for Central District traffic flow.</p>
        </div>
        <div className="flex gap-2">
          <button className="bg-surface-container-lowest text-primary px-4 py-2 rounded-full text-sm font-semibold transition-all hover:bg-surface-container-low flex items-center gap-1">
            <span className="material-symbols-outlined text-sm">grid_view</span>
            Multiview
          </button>
          <button className="signature-gradient text-white px-6 py-2 rounded-full text-sm font-semibold shadow-sm hover:brightness-105 transition-all flex items-center gap-1">
            <span className="material-symbols-outlined text-sm">add_circle</span>
            Link New Camera
          </button>
        </div>
      </div>

      {/* Main Layout: Asymmetric Bento Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Primary Video Feed (Large) */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          <div className="relative aspect-video rounded-xl overflow-hidden bg-surface-container-highest shadow-sm group">
            <img
              alt="Camera Feed Live"
              className="w-full h-full object-cover"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuCyh_XEwyiA4d7CocMTyXl_y9JZXXLkH_NwOtvSnXTnGOtIuV4q-NecVZykJQdKARUxjtKCDAuxTwtoL3rrWQx6pdGAT22nfFHBgD3v4PM8g6utsT0-jmnFfsBVcFy3jiqXeHO-KjA3rFoRh7W5dcMX0xltsDFTt7_lSmEgQjP1t7YcAOWsWOwJaeXS1xpnPltZl-VlncSsH8dR9UDVzP_xkiOKPAS4VawYIScLt9h-d5hh4Oii9QZCJunBM6vXGwz093w5kwbmbMh_"
            />
            {/* Overlay: Top Bar */}
            <div className="absolute top-0 left-0 right-0 p-6 flex justify-between items-start bg-gradient-to-b from-black/50 to-transparent">
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span className="bg-red-600 w-2 h-2 rounded-full animate-pulse"></span>
                  <span className="text-white font-bold text-lg tracking-tight">CAM-0428-NW</span>
                  <span className="bg-white/20 backdrop-blur-md px-2 py-0.5 rounded text-[10px] text-white font-bold uppercase tracking-widest">LIVE</span>
                </div>
                <span className="text-white/80 text-sm">Northwest Interchange • Central District</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="bg-black/30 backdrop-blur-md px-3 py-1.5 rounded-lg text-white text-xs font-mono">
                  2023-11-24 14:32:08 UTC
                </div>
                <button className="bg-white/20 backdrop-blur-md p-2 rounded-lg text-white hover:bg-white/40 transition-colors">
                  <span className="material-symbols-outlined">fullscreen</span>
                </button>
              </div>
            </div>
            {/* Overlay: Telemetry Bottom */}
            <div className="absolute bottom-6 left-6 right-6 flex justify-between items-end">
              <div className="flex gap-4">
                <div className="bg-black/40 backdrop-blur-xl p-3 rounded-xl border border-white/10 text-white min-w-[120px]">
                  <p className="text-[10px] uppercase text-white/60 mb-1">Bitrate</p>
                  <p className="text-sm font-bold font-mono">4.2 Mbps</p>
                </div>
                <div className="bg-black/40 backdrop-blur-xl p-3 rounded-xl border border-white/10 text-white min-w-[120px]">
                  <p className="text-[10px] uppercase text-white/60 mb-1">Frame Rate</p>
                  <p className="text-sm font-bold font-mono">60 FPS</p>
                </div>
                <div className="bg-black/40 backdrop-blur-xl p-3 rounded-xl border border-white/10 text-white min-w-[120px]">
                  <p className="text-[10px] uppercase text-white/60 mb-1">Latency</p>
                  <p className="text-sm font-bold font-mono">18ms</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button className="bg-white p-3 rounded-full text-primary shadow-lg hover:scale-105 transition-transform">
                  <span className="material-symbols-outlined">videocam</span>
                </button>
                <button className="bg-white p-3 rounded-full text-primary shadow-lg hover:scale-105 transition-transform">
                  <span className="material-symbols-outlined">mic</span>
                </button>
                <button className="bg-error p-3 rounded-full text-white shadow-lg hover:scale-105 transition-transform">
                  <span className="material-symbols-outlined">emergency</span>
                </button>
              </div>
            </div>
          </div>

          {/* Telemetry Cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-lg bg-secondary-container text-primary">
                  <span className="material-symbols-outlined text-lg">radar</span>
                </div>
                <span className="font-bold text-sm text-on-surface">Object Detection</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-on-surface-variant">Vehicles</span>
                  <span className="font-bold text-on-surface">42</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-on-surface-variant">Pedestrians</span>
                  <span className="font-bold text-on-surface">12</span>
                </div>
                <div className="w-full bg-surface-container h-1 rounded-full mt-2">
                  <div className="bg-primary w-[65%] h-full rounded-full"></div>
                </div>
              </div>
            </div>

            <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-lg bg-secondary-container text-primary">
                  <span className="material-symbols-outlined text-lg">thermostat</span>
                </div>
                <span className="font-bold text-sm text-on-surface">Hardware Health</span>
              </div>
              <div className="flex items-end justify-between">
                <span className="text-2xl font-bold text-on-surface">42°C</span>
                <span className="text-[10px] text-primary font-bold bg-secondary-container px-2 py-0.5 rounded">OPTIMAL</span>
              </div>
              <p className="text-[10px] text-on-surface-variant mt-2">CPU Usage: 14% • RAM: 2.1GB</p>
            </div>

            <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-lg bg-secondary-container text-primary">
                  <span className="material-symbols-outlined text-lg">history</span>
                </div>
                <span className="font-bold text-sm text-on-surface">Uptime</span>
              </div>
              <span className="text-2xl font-bold text-on-surface">142d 12h</span>
              <p className="text-[10px] text-on-surface-variant mt-2">Last restart: 4 months ago</p>
            </div>
          </div>
        </div>

        {/* Sidebar: Selector & Map */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          {/* Mini Map Card */}
          <div className="bg-surface-container-lowest rounded-xl p-2 shadow-sm relative overflow-hidden h-48">
            <img
              alt="Map Location"
              className="w-full h-full object-cover rounded-lg"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuCxV1oWNYeng0W0vpv3qhTBfwiGklmkVvtIbHMvLbzz7vm1tQVLY-vQGcR6d3jI3ZsDKSxZasD12D6qdN4h55UJ0ZaYLHBwRfLeGc2Ft4AC1wfEbEvvtFrTbgpyGNRRqevZgbvTQkfyhc0bx1fe5xy5d1_7gxVxHhiCXNfQnsZhX2v_LxcLJ31mv2hM-gau1TwSl-evdn2-XmLgFUNVQEpkUolXPr-jX9cSSmK-0U2QIsBs2HkHuCAessYaEoGvP42QKKim52tqicfq"
            />
            <div className="absolute inset-0 bg-primary/5 pointer-events-none rounded-lg"></div>
            <div className="absolute top-4 left-4 bg-white/90 backdrop-blur-md px-3 py-1.5 rounded-lg shadow-sm">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-sm text-primary">location_on</span>
                <span className="text-xs font-bold text-on-surface">47.6062° N, 122.3321° W</span>
              </div>
            </div>
          </div>

          {/* Camera Selector List */}
          <div className="bg-surface-container-lowest rounded-xl shadow-sm flex flex-col overflow-hidden">
            <div className="p-5 border-b border-surface-container flex justify-between items-center">
              <h3 className="font-bold text-sm text-on-surface">Nearby Cameras</h3>
              <button className="text-primary text-xs font-semibold">View All</button>
            </div>
            <div className="p-2 space-y-1">
              {/* Active Item */}
              <div className="flex items-center gap-3 p-3 bg-secondary-container/30 rounded-lg border-l-4 border-primary">
                <div className="w-16 h-10 rounded bg-surface-container overflow-hidden shrink-0">
                  <img
                    alt="CAM-0428"
                    className="w-full h-full object-cover"
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuBuALudZnI7Bw3U8rh7Ln_1StbBx_0EEGgCy8a2qcIEsxoNJMVPdvfjyxA7nvDRIV6OJOEhaAPTlA2d2Ka9RgSXtFXVVH0G-JYbWxEUed3m-_zphceVoIkHuj3MpfEGcuQJS8cxbPCwX8AA6_TV4TVbdxrGhOanCceEPABIwaYDGr4lL5-YxPDNUTbWdkTsj51TjaUpN31BPR7uvhE5-Rvl2q7o2i9MPVZcI4-2Z7AQ8tZQuJOXoqvuwHWwZzkZf-rfY0O5bhxqlPx7"
                  />
                </div>
                <div className="flex-1 overflow-hidden">
                  <p className="text-xs font-bold truncate text-primary">CAM-0428-NW (Active)</p>
                  <p className="text-[10px] text-on-surface-variant truncate">Northwest Interchange</p>
                </div>
                <span className="material-symbols-outlined text-primary text-sm">radio_button_checked</span>
              </div>

              <div className="flex items-center gap-3 p-3 hover:bg-surface-container-low rounded-lg transition-colors cursor-pointer group">
                <div className="w-16 h-10 rounded bg-surface-container overflow-hidden shrink-0">
                  <img alt="CAM-0912" className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" src="https://lh3.googleusercontent.com/aida-public/AB6AXuAtXBx50Kmi_1HdooPkwqGhqP2PBRnZ9qllAkHfguOllPa3mm3QltBVJsHXEJ-EAn72LnP9sIhEDNQJTI1esu0NhZ1pc-yTC2Dh40660owKxTRq2qDA-Ymr78qDYmQ6tRP6QdxiyJO1oNPTDv2oVQvQbzU8jqDUBPjq5fG_HYfaoW3XzKlUA6RGbtCvL8in9dWQwFkAr27NCvfwdrlJOJUKG2FEOFByzPNsp4E1-db3gn6dTZ-SOft3NFwMtUMZx44HjkrnS2XGpwYx" />
                </div>
                <div className="flex-1 overflow-hidden">
                  <p className="text-xs font-bold truncate text-on-surface">CAM-0912-ST</p>
                  <p className="text-[10px] text-on-surface-variant truncate">South Station Crossing</p>
                </div>
                <span className="material-symbols-outlined text-on-surface-variant/30 text-sm group-hover:text-primary transition-colors">play_circle</span>
              </div>

              <div className="flex items-center gap-3 p-3 hover:bg-surface-container-low rounded-lg transition-colors cursor-pointer group">
                <div className="w-16 h-10 rounded bg-surface-container overflow-hidden shrink-0">
                  <img alt="CAM-0115" className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCruXZJLSXPc1rgquYO8M3tMrjPRxChlz3Uraq7nq4fz3Gid04O2fBfjyFVKYkXndcgtjJqBDs8rscPhZUU2y75DG30h_K6CGautF8qqud0y1xU1DG0UFMSVQKhea_rqCOCYoyZuqmKZiYtbUT0YohVnD8Ytx3PmERE39XigetnqUXvkq7NJMp2PsGlSRJYq5-e_0H_olqg4K4ivmQ0-8i9Kp7v7DGYFNPjGxtLfbwQPIEB4EXDWsh59Ms1BG5YB9ieg2vcfNOlr8kq" />
                </div>
                <div className="flex-1 overflow-hidden">
                  <p className="text-xs font-bold truncate text-on-surface">CAM-0115-BR</p>
                  <p className="text-[10px] text-on-surface-variant truncate">Harbor Bridge East</p>
                </div>
                <div className="px-2 py-0.5 rounded bg-error-container text-on-error-container text-[8px] font-bold">ALARM</div>
              </div>

              <div className="flex items-center gap-3 p-3 hover:bg-surface-container-low rounded-lg transition-colors cursor-pointer group">
                <div className="w-16 h-10 rounded bg-surface-container overflow-hidden shrink-0">
                  <img alt="CAM-0722" className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBE7GnvH1iFGyyfxQQ994G603e9C_WTJmm36u1gIz9vw9aoavVObGU9Iy6D0n3AD4YYYW5zl4ObwOVLJrpxsEwxu44TefU9QondRxw4xmbEv5WpzbKKKCZzt3rY3mGNkrIyW554eUHuOEmmEnqTsdlucaK0BXLMHtpY24XLBY8OwfAygxniDFAltnp5BWlIpjOSMlOoXZL2QDoUbWu6Jcyb9W-vdvRdLgbcjuCLV_fe417vhsIzlcse4yA2mrwl7lGT2nCPtdQye_bt" />
                </div>
                <div className="flex-1 overflow-hidden">
                  <p className="text-xs font-bold truncate text-on-surface">CAM-0722-TN</p>
                  <p className="text-[10px] text-on-surface-variant truncate">West Metro Tunnel</p>
                </div>
                <span className="material-symbols-outlined text-on-surface-variant/30 text-sm group-hover:text-primary transition-colors">play_circle</span>
              </div>
            </div>
          </div>

          {/* IRIS Assistant Suggestion */}
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm border-b-4 border-secondary-container">
            <div className="flex items-center gap-3 mb-4">
              <span className="material-symbols-outlined text-primary">smart_toy</span>
              <h3 className="font-bold text-sm text-on-surface">IRIS Insight</h3>
            </div>
            <p className="text-xs text-on-surface-variant leading-relaxed mb-4">
              Based on current traffic volume at{" "}
              <span className="text-primary font-bold">CAM-0428-NW</span>, I recommend adjusting signal timing at the next intersection to prevent bottlenecking.
            </p>
            <button className="w-full py-2 bg-secondary-container text-on-secondary-container rounded-lg text-xs font-bold hover:bg-primary-container hover:text-white transition-colors">
              Apply Optimized Signal
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
