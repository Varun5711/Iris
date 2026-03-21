export default function SettingsPage() {
  return (
    <main className="min-h-screen bg-surface pt-24">
      <div className="p-10 max-w-7xl mx-auto">
        <div className="mb-10">
          <h2 className="text-3xl font-extrabold text-on-surface tracking-tight">Settings</h2>
          <p className="text-on-surface-variant mt-1">Configure system intelligence and operational parameters.</p>
        </div>

        <div className="grid grid-cols-12 gap-8">
          {/* Navigation Tabs (Internal) */}
          <div className="col-span-12 md:col-span-3 flex flex-col gap-2">
            <button className="flex items-center gap-3 px-4 py-3 bg-primary-container text-on-primary-container font-semibold rounded-xl text-left transition-all text-sm">
              <span className="material-symbols-outlined">database</span>
              System Settings
            </button>
            <button className="flex items-center gap-3 px-4 py-3 text-on-surface-variant hover:bg-surface-container-low rounded-xl text-left transition-all text-sm">
              <span className="material-symbols-outlined">notifications_active</span>
              Alert Config
            </button>
            <button className="flex items-center gap-3 px-4 py-3 text-on-surface-variant hover:bg-surface-container-low rounded-xl text-left transition-all text-sm">
              <span className="material-symbols-outlined">person_search</span>
              User Management
            </button>
            <button className="flex items-center gap-3 px-4 py-3 text-on-surface-variant hover:bg-surface-container-low rounded-xl text-left transition-all text-sm">
              <span className="material-symbols-outlined">psychology</span>
              AI Sensitivity
            </button>
          </div>

          {/* Settings Content */}
          <div className="col-span-12 md:col-span-9 flex flex-col gap-8">
            {/* Section: Data Sources & Integration */}
            <section className="bg-surface-container-lowest rounded-xl p-8 shadow-sm">
              <div className="mb-6">
                <h3 className="text-lg font-bold text-on-surface">Data Sources & Integration</h3>
                <p className="text-sm text-on-surface-variant">Manage external telemetry and camera feed integrations.</p>
              </div>
              <div className="space-y-6">
                <div className="flex items-center justify-between py-4 border-b border-surface-container-low">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-secondary-container rounded-lg">
                      <span className="material-symbols-outlined text-on-secondary-container">videocam</span>
                    </div>
                    <div>
                      <p className="font-bold text-on-surface">Traffic Camera Hub</p>
                      <p className="text-xs text-on-surface-variant">RTMP stream from Central District nodes</p>
                    </div>
                  </div>
                  <div className="relative inline-block w-12 h-6 bg-primary rounded-full cursor-pointer transition-colors">
                    <span className="absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform translate-x-6"></span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-4 border-b border-surface-container-low">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-secondary-container rounded-lg">
                      <span className="material-symbols-outlined text-on-secondary-container">sensors</span>
                    </div>
                    <div>
                      <p className="font-bold text-on-surface">IoT Pavement Sensors</p>
                      <p className="text-xs text-on-surface-variant">Lidar-based surface analysis data</p>
                    </div>
                  </div>
                  <div className="relative inline-block w-12 h-6 bg-surface-container-high rounded-full cursor-pointer transition-colors">
                    <span className="absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform"></span>
                  </div>
                </div>
              </div>
              <div className="mt-8">
                <label className="block text-sm font-bold text-on-surface mb-2">Primary API Endpoint</label>
                <div className="flex gap-2">
                  <input
                    className="flex-1 bg-surface border-none rounded-lg text-sm px-4 py-3 focus:ring-2 focus:ring-primary-container outline-none text-on-surface-variant"
                    type="text"
                    defaultValue="https://api.iris-intel.gov/v2/telemetry"
                  />
                  <button className="px-6 py-2 bg-primary text-white rounded-full font-bold text-sm hover:opacity-90 transition-opacity">Update</button>
                </div>
              </div>
            </section>

            {/* Section: AI Sensitivity */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-surface-container-lowest rounded-xl p-8 shadow-sm border-b-4 border-secondary-container">
                <div className="flex items-center gap-2 mb-6">
                  <span className="material-symbols-outlined text-primary">auto_awesome</span>
                  <h3 className="text-lg font-bold text-on-surface">AI Recommendation Engine</h3>
                </div>
                <p className="text-sm text-on-surface-variant mb-6 leading-relaxed">
                  Adjust the confidence threshold for automated incident reporting. Lowering this increases noise but captures subtle anomalies.
                </p>
                <div className="space-y-4">
                  <div className="flex justify-between text-xs font-bold text-on-surface-variant">
                    <span>CONSERVATIVE</span>
                    <span>BALANCED</span>
                    <span>AGGRESSIVE</span>
                  </div>
                  <input
                    className="w-full h-2 bg-surface-container-low rounded-lg appearance-none cursor-pointer accent-primary"
                    type="range"
                    defaultValue="74"
                  />
                  <div className="p-4 bg-secondary-container/20 rounded-lg flex items-start gap-3">
                    <span className="material-symbols-outlined text-primary text-sm">info</span>
                    <p className="text-xs text-on-secondary-container italic">
                      Setting to &ldquo;Balanced&rdquo; (74%) is recommended for the current traffic load in Central District.
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-surface-container-lowest rounded-xl p-8 shadow-sm">
                <div className="flex items-center gap-2 mb-6">
                  <span className="material-symbols-outlined text-on-tertiary-container">bolt</span>
                  <h3 className="text-lg font-bold text-on-surface">Auto-Action Triggers</h3>
                </div>
                <div className="space-y-4">
                  <label className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-container-low cursor-pointer transition-colors">
                    <span className="text-sm font-medium text-on-surface">Log Major Incidents</span>
                    <input defaultChecked className="rounded text-primary focus:ring-primary accent-primary" type="checkbox" />
                  </label>
                  <label className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-container-low cursor-pointer transition-colors">
                    <span className="text-sm font-medium text-on-surface">Auto-dispatch Drones</span>
                    <input className="rounded text-primary focus:ring-primary accent-primary" type="checkbox" />
                  </label>
                  <label className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-container-low cursor-pointer transition-colors">
                    <span className="text-sm font-medium text-on-surface">Smart Traffic Rerouting</span>
                    <input defaultChecked className="rounded text-primary focus:ring-primary accent-primary" type="checkbox" />
                  </label>
                </div>
              </div>
            </section>

            {/* Section: Alert Configuration */}
            <section className="bg-surface-container-lowest rounded-xl p-8 shadow-sm">
              <div className="flex justify-between items-start mb-8">
                <div>
                  <h3 className="text-lg font-bold text-on-surface">Alert Configuration</h3>
                  <p className="text-sm text-on-surface-variant">Set severity thresholds and notification routes.</p>
                </div>
                <button className="flex items-center gap-2 text-primary font-bold text-sm">
                  <span className="material-symbols-outlined text-sm">add</span>
                  Add Route
                </button>
              </div>
              <div className="overflow-hidden">
                <table className="w-full text-left">
                  <thead className="border-b border-surface-container-low">
                    <tr>
                      <th className="pb-4 text-xs font-bold text-on-surface-variant uppercase tracking-widest">Severity</th>
                      <th className="pb-4 text-xs font-bold text-on-surface-variant uppercase tracking-widest">Channels</th>
                      <th className="pb-4 text-xs font-bold text-on-surface-variant uppercase tracking-widest text-right">Escalation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-container-low">
                    <tr>
                      <td className="py-5">
                        <span className="px-3 py-1 bg-error-container text-on-error-container text-[10px] font-extrabold rounded-full">CRITICAL</span>
                      </td>
                      <td className="py-5">
                        <div className="flex gap-2">
                          <span className="material-symbols-outlined text-primary text-lg">mail</span>
                          <span className="material-symbols-outlined text-primary text-lg">sms</span>
                          <span className="material-symbols-outlined text-primary text-lg">phone_in_talk</span>
                        </div>
                      </td>
                      <td className="py-5 text-right text-xs font-medium text-on-surface-variant">Immediate (0m)</td>
                    </tr>
                    <tr>
                      <td className="py-5">
                        <span className="px-3 py-1 bg-tertiary-container/20 text-tertiary text-[10px] font-extrabold rounded-full">MODERATE</span>
                      </td>
                      <td className="py-5">
                        <div className="flex gap-2">
                          <span className="material-symbols-outlined text-primary text-lg">mail</span>
                          <span className="material-symbols-outlined text-on-surface-variant/30 text-lg">sms</span>
                        </div>
                      </td>
                      <td className="py-5 text-right text-xs font-medium text-on-surface-variant">5m Delay</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            {/* Section: User Management */}
            <section className="bg-surface-container-lowest rounded-xl p-8 shadow-sm">
              <div className="mb-8 flex items-center justify-between">
                <h3 className="text-lg font-bold text-on-surface">User Roles & Access</h3>
                <div className="flex bg-surface-container-low p-1 rounded-full">
                  <button className="px-4 py-1.5 bg-white shadow-sm rounded-full text-xs font-bold text-on-surface">Active</button>
                  <button className="px-4 py-1.5 text-xs font-bold text-on-surface-variant">Pending</button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 border border-outline-variant/20 rounded-xl flex items-center justify-between hover:bg-surface-container-low transition-colors group">
                  <div className="flex items-center gap-4">
                    <img
                      alt="Marcus Thorne"
                      className="w-10 h-10 rounded-full grayscale group-hover:grayscale-0 transition-all"
                      src="https://lh3.googleusercontent.com/aida-public/AB6AXuCtJB-EoDKd7V6K0rMmKrTrewIoACi_erQ1r0BxxU8G-MDUGgV6RWRHqvY7yEMJU_SM8HOr4O2tq2LoAUPZcR-aF2OpBLr_vTZ_YXYyHPiyMqnVI7hJMH9b8VZ0DKQ9QqkNwxwkf1dWJ4ZulRQqepSAL1N8skbBAA4fwhpldCL15P1YbvRzXbkfbx0xsepf39wK90bacbAfOFr7aE5NhpJXk1FGrOBnq5dIn-9CDPHtD4SoNatZ7__vTuu3KjRFJf-8tD5L6xy5Uqsx"
                    />
                    <div>
                      <p className="font-bold text-sm text-on-surface">Marcus Thorne</p>
                      <p className="text-xs text-on-surface-variant">Senior Admin • Level 5</p>
                    </div>
                  </div>
                  <span className="material-symbols-outlined text-on-surface-variant opacity-40">more_vert</span>
                </div>
                <div className="p-4 border border-outline-variant/20 rounded-xl flex items-center justify-between hover:bg-surface-container-low transition-colors group">
                  <div className="flex items-center gap-4">
                    <img
                      alt="Elena Rodriguez"
                      className="w-10 h-10 rounded-full grayscale group-hover:grayscale-0 transition-all"
                      src="https://lh3.googleusercontent.com/aida-public/AB6AXuDxb0g6A2PMSrhKa2z_wWduxege6jJj26YKu0ITgs7yK0WuKXuzYwrdpUchKdELG8FfjiuqcIGyLYWigdexo45_XSY84bsdYbRpw1BGHTc9AoeJVXF99NvdFCj2L5ah2eeOJLNp3cRz8ydSuJqLaH11KBSpCw2R4ZrOjRB1kdIIqRg6b86cQQwgGVDBZNyJ2nz0xS2Nw0xend9_H5utX9IguoohX9-knSoksCwSleWSzpoONo7p_LtyDHPlfucFHBd83Xxg33b7FPNE"
                    />
                    <div>
                      <p className="font-bold text-sm text-on-surface">Elena Rodriguez</p>
                      <p className="text-xs text-on-surface-variant">Field Operator • Level 2</p>
                    </div>
                  </div>
                  <span className="material-symbols-outlined text-on-surface-variant opacity-40">more_vert</span>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </main>
  );
}
