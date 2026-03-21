"use client";

import { useSettings } from "@/ui_lib/settings-context";

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!on)}
      className={`relative inline-block w-12 h-6 rounded-full cursor-pointer transition-colors ${on ? "bg-primary" : "bg-surface-container-high"}`}
    >
      <span className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${on ? "translate-x-7" : "translate-x-1"}`}></span>
    </button>
  );
}

const TABS = [
  { key: "system", icon: "database", label: "System Settings" },
  { key: "maplayers", icon: "layers", label: "Map Layers" },
  { key: "alerts", icon: "notifications_active", label: "Alert Config" },
  { key: "users", icon: "person_search", label: "User Management" },
  { key: "ai", icon: "psychology", label: "AI Sensitivity" },
];

const USERS = [
  { name: "Marcus Thorne", role: "Senior Admin", level: "Level 5", img: "https://lh3.googleusercontent.com/aida-public/AB6AXuCtJB-EoDKd7V6K0rMmKrTrewIoACi_erQ1r0BxxU8G-MDUGgV6RWRHqvY7yEMJU_SM8HOr4O2tq2LoAUPZcR-aF2OpBLr_vTZ_YXYyHPiyMqnVI7hJMH9b8VZ0DKQ9QqkNwxwkf1dWJ4ZulRQqepSAL1N8skbBAA4fwhpldCL15P1YbvRzXbkfbx0xsepf39wK90bacbAfOFr7aE5NhpJXk1FGrOBnq5dIn-9CDPHtD4SoNatZ7__vTuu3KjRFJf-8tD5L6xy5Uqsx" },
  { name: "Elena Rodriguez", role: "Field Operator", level: "Level 2", img: "https://lh3.googleusercontent.com/aida-public/AB6AXuDxb0g6A2PMSrhKa2z_wWduxege6jJj26YKu0ITgs7yK0WuKXuzYwrdpUchKdELG8FfjiuqcIGyLYWigdexo45_XSY84bsdYbRpw1BGHTc9AoeJVXF99NvdFCj2L5ah2eeOJLNp3cRz8ydSuJqLaH11KBSpCw2R4ZrOjRB1kdIIqRg6b86cQQwgGVDBZNyJ2nz0xS2Nw0xend9_H5utX9IguoohX9-knSoksCwSleWSzpoONo7p_LtyDHPlfucFHBd83Xxg33b7FPNE" },
  { name: "James Okafor", role: "Traffic Analyst", level: "Level 3", img: "https://lh3.googleusercontent.com/aida-public/AB6AXuCtJB-EoDKd7V6K0rMmKrTrewIoACi_erQ1r0BxxU8G-MDUGgV6RWRHqvY7yEMJU_SM8HOr4O2tq2LoAUPZcR-aF2OpBLr_vTZ_YXYyHPiyMqnVI7hJMH9b8VZ0DKQ9QqkNwxwkf1dWJ4ZulRQqepSAL1N8skbBAA4fwhpldCL15P1YbvRzXbkfbx0xsepf39wK90bacbAfOFr7aE5NhpJXk1FGrOBnq5dIn-9CDPHtD4SoNatZ7__vTuu3KjRFJf-8tD5L6xy5Uqsx" },
  { name: "Sofia Park", role: "Supervisor", level: "Level 4", img: "https://lh3.googleusercontent.com/aida-public/AB6AXuDxb0g6A2PMSrhKa2z_wWduxege6jJj26YKu0ITgs7yK0WuKXuzYwrdpUchKdELG8FfjiuqcIGyLYWigdexo45_XSY84bsdYbRpw1BGHTc9AoeJVXF99NvdFCj2L5ah2eeOJLNp3cRz8ydSuJqLaH11KBSpCw2R4ZrOjRB1kdIIqRg6b86cQQwgGVDBZNyJ2nz0xS2Nw0xend9_H5utX9IguoohX9-knSoksCwSleWSzpoONo7p_LtyDHPlfucFHBd83Xxg33b7FPNE" },
];

import { useState } from "react";

export default function SettingsPage() {
  const { settings, update, save, saved } = useSettings();
  const [activeTab, setActiveTab] = useState("system");

  const sensitivityLabel =
    settings.aiSensitivity < 40
      ? "Conservative"
      : settings.aiSensitivity < 70
      ? "Balanced"
      : settings.aiSensitivity < 90
      ? "Aggressive"
      : "Maximum";

  return (
    <main className="min-h-screen bg-surface pt-24">
      <div className="p-10 max-w-7xl mx-auto">
        <div className="mb-10 flex items-end justify-between">
          <div>
            <h2 className="text-3xl font-extrabold text-on-surface tracking-tight">Settings</h2>
            <p className="text-on-surface-variant mt-1">Configure system intelligence and operational parameters.</p>
          </div>
          <button
            onClick={save}
            className={`px-6 py-2.5 rounded-full font-bold text-sm transition-all ${
              saved
                ? "bg-primary/10 text-primary"
                : "signature-gradient text-white shadow-md hover:brightness-110 active:scale-95"
            }`}
          >
            {saved ? (
              <span className="flex items-center gap-2">
                <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                Saved
              </span>
            ) : (
              "Save Changes"
            )}
          </button>
        </div>

        <div className="grid grid-cols-12 gap-8">
          {/* Nav Tabs */}
          <div className="col-span-12 md:col-span-3 flex flex-col gap-2">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all text-sm ${
                  activeTab === tab.key
                    ? "bg-primary-container text-on-primary-container font-semibold"
                    : "text-on-surface-variant hover:bg-surface-container-low font-medium"
                }`}
              >
                <span className="material-symbols-outlined">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="col-span-12 md:col-span-9 flex flex-col gap-8">

            {/* SYSTEM SETTINGS */}
            {activeTab === "system" && (
              <>
                <section className="bg-surface-container-lowest rounded-xl p-8 shadow-sm">
                  <div className="mb-6">
                    <h3 className="text-lg font-bold text-on-surface">Data Sources & Integration</h3>
                    <p className="text-sm text-on-surface-variant">Manage external telemetry and camera feed integrations.</p>
                  </div>
                  <div className="space-y-4">
                    {[
                      { key: "trafficCamera" as const, icon: "videocam", label: "Traffic Camera Hub", desc: "RTMP stream from Central District nodes" },
                      { key: "iotSensors" as const, icon: "sensors", label: "IoT Pavement Sensors", desc: "Lidar-based surface analysis data" },
                      { key: "weatherApi" as const, icon: "cloud", label: "Weather API", desc: "Real-time meteorological data feed" },
                      { key: "cctv" as const, icon: "camera_outdoor", label: "CCTV Network", desc: "48 active cameras across 6 districts" },
                    ].map(({ key, icon, label, desc }) => (
                      <div key={key} className="flex items-center justify-between py-4 border-b border-surface-container-low last:border-0">
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-secondary-container rounded-lg">
                            <span className="material-symbols-outlined text-on-secondary-container">{icon}</span>
                          </div>
                          <div>
                            <p className="font-bold text-on-surface">{label}</p>
                            <p className="text-xs text-on-surface-variant">{desc}</p>
                          </div>
                        </div>
                        <Toggle
                          on={settings.dataSources[key]}
                          onChange={(v) => update({ dataSources: { ...settings.dataSources, [key]: v } })}
                        />
                      </div>
                    ))}
                  </div>
                  <div className="mt-8">
                    <label className="block text-sm font-bold text-on-surface mb-2">Primary API Endpoint</label>
                    <div className="flex gap-2">
                      <input
                        className="flex-1 bg-surface border-none rounded-lg text-sm px-4 py-3 focus:ring-2 focus:ring-primary-container outline-none text-on-surface"
                        type="text"
                        value={settings.apiEndpoint}
                        onChange={(e) => update({ apiEndpoint: e.target.value })}
                      />
                      <button onClick={save} className="px-6 py-2 bg-primary text-white rounded-full font-bold text-sm hover:opacity-90 transition-opacity">
                        Update
                      </button>
                    </div>
                    <p className="text-xs text-on-surface-variant mt-2">Changes take effect on next polling cycle (≤30s).</p>
                  </div>
                </section>

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
                        min="10"
                        max="99"
                        value={settings.aiSensitivity}
                        onChange={(e) => update({ aiSensitivity: parseInt(e.target.value) })}
                      />
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-bold text-on-surface">{settings.aiSensitivity}%</span>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${settings.aiSensitivity > 80 ? "bg-error-container text-on-error-container" : "bg-primary-container/20 text-primary"}`}>
                          {sensitivityLabel}
                        </span>
                      </div>
                      <div className="p-4 bg-secondary-container/20 rounded-lg flex items-start gap-3">
                        <span className="material-symbols-outlined text-primary text-sm">info</span>
                        <p className="text-xs text-on-secondary-container italic">
                          Setting to &ldquo;Balanced&rdquo; (74%) is recommended for the current traffic load.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-surface-container-lowest rounded-xl p-8 shadow-sm">
                    <div className="flex items-center gap-2 mb-6">
                      <span className="material-symbols-outlined text-on-tertiary-container">bolt</span>
                      <h3 className="text-lg font-bold text-on-surface">Auto-Action Triggers</h3>
                    </div>
                    <div className="space-y-2">
                      {[
                        { key: "logMajorIncidents" as const, label: "Log Major Incidents" },
                        { key: "autoDispatchDrones" as const, label: "Auto-dispatch Drones" },
                        { key: "smartRerouting" as const, label: "Smart Traffic Rerouting" },
                        { key: "alertAuthorities" as const, label: "Alert Authorities" },
                      ].map(({ key, label }) => (
                        <label key={key} className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-container-low cursor-pointer transition-colors">
                          <span className="text-sm font-medium text-on-surface">{label}</span>
                          <Toggle
                            on={settings.autoActions[key]}
                            onChange={(v) => update({ autoActions: { ...settings.autoActions, [key]: v } })}
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                </section>
              </>
            )}

            {/* MAP LAYERS */}
            {activeTab === "maplayers" && (
              <section className="bg-surface-container-lowest rounded-xl p-8 shadow-sm">
                <div className="mb-6">
                  <h3 className="text-lg font-bold text-on-surface">Map Layer Visibility</h3>
                  <p className="text-sm text-on-surface-variant">Toggle which layers appear on the live traffic map. Changes apply instantly across all map views.</p>
                </div>
                <div className="space-y-4">
                  {[
                    { key: "traffic" as const, icon: "traffic", label: "Traffic Flow Layer", desc: "Congestion heatmap and speed overlays" },
                    { key: "incidents" as const, icon: "warning", label: "Incident Markers", desc: "Active incidents plotted on the map" },
                    { key: "signals" as const, icon: "traffic_jam", label: "Signal Actions", desc: "Re-timing recommendations at intersections" },
                    { key: "cameras" as const, icon: "videocam", label: "Camera Feeds", desc: "CCTV camera positions and coverage zones" },
                    { key: "diversionRoutes" as const, icon: "alt_route", label: "Diversion Routes", desc: "Optimised alternate routes from LLM output" },
                    { key: "affectedSegments" as const, icon: "route", label: "Affected Segments", desc: "Road segments impacted by active incidents" },
                  ].map(({ key, icon, label, desc }) => (
                    <div key={key} className="flex items-center justify-between py-4 border-b border-surface-container-low last:border-0">
                      <div className="flex items-center gap-4">
                        <div className={`p-3 rounded-lg ${settings.mapLayers[key] ? "bg-primary-container" : "bg-surface-container-low"}`}>
                          <span className={`material-symbols-outlined ${settings.mapLayers[key] ? "text-primary" : "text-on-surface-variant"}`} style={{ fontVariationSettings: "'FILL' 1" }}>{icon}</span>
                        </div>
                        <div>
                          <p className="font-bold text-on-surface">{label}</p>
                          <p className="text-xs text-on-surface-variant">{desc}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${settings.mapLayers[key] ? "bg-primary/10 text-primary" : "bg-surface-container text-on-surface-variant"}`}>
                          {settings.mapLayers[key] ? "VISIBLE" : "HIDDEN"}
                        </span>
                        <Toggle
                          on={settings.mapLayers[key]}
                          onChange={(v) => update({ mapLayers: { ...settings.mapLayers, [key]: v } })}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-6 p-4 bg-primary/5 rounded-lg flex items-start gap-3">
                  <span className="material-symbols-outlined text-primary text-sm">info</span>
                  <p className="text-xs text-on-surface-variant">
                    Layer visibility syncs instantly with the Map, Dashboard, and Incidents pages — no page refresh needed.
                  </p>
                </div>
              </section>
            )}

            {/* ALERT CONFIG */}
            {activeTab === "alerts" && (
              <section className="bg-surface-container-lowest rounded-xl p-8 shadow-sm">
                <div className="flex justify-between items-start mb-8">
                  <div>
                    <h3 className="text-lg font-bold text-on-surface">Alert Configuration</h3>
                    <p className="text-sm text-on-surface-variant">Set severity thresholds and notification routes.</p>
                  </div>
                  <button className="flex items-center gap-2 text-primary font-bold text-sm hover:bg-primary/5 px-3 py-1.5 rounded-full transition-colors">
                    <span className="material-symbols-outlined text-sm">add</span> Add Route
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
                      {(
                        [
                          { label: "CRITICAL", key: "criticalChannels" as const, escalation: "Immediate (0m)", badgeCls: "bg-error-container text-on-error-container" },
                          { label: "MODERATE", key: "moderateChannels" as const, escalation: "5m Delay", badgeCls: "bg-tertiary-container/20 text-tertiary" },
                        ] as const
                      ).map(({ label, key, escalation, badgeCls }) => (
                        <tr key={key}>
                          <td className="py-5">
                            <span className={`px-3 py-1 ${badgeCls} text-[10px] font-extrabold rounded-full`}>{label}</span>
                          </td>
                          <td className="py-5">
                            <div className="flex gap-3">
                              {(["email", "sms", "phone"] as const).map((ch) => {
                                const icons: Record<string, string> = { email: "mail", sms: "sms", phone: "phone_in_talk" };
                                return (
                                  <button
                                    key={ch}
                                    onClick={() =>
                                      update({
                                        alerts: {
                                          ...settings.alerts,
                                          [key]: { ...settings.alerts[key], [ch]: !settings.alerts[key][ch] },
                                        },
                                      })
                                    }
                                    className={`transition-colors ${settings.alerts[key][ch] ? "text-primary" : "text-on-surface-variant/30"}`}
                                    title={ch}
                                  >
                                    <span className="material-symbols-outlined text-lg">{icons[ch]}</span>
                                  </button>
                                );
                              })}
                            </div>
                          </td>
                          <td className="py-5 text-right text-xs font-medium text-on-surface-variant">{escalation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-8 p-4 bg-secondary-container/20 rounded-lg flex items-start gap-3">
                  <span className="material-symbols-outlined text-primary">info</span>
                  <p className="text-xs text-on-secondary-container">Channel changes take effect immediately. Twilio credentials are pre-configured in the environment.</p>
                </div>
              </section>
            )}

            {/* USER MANAGEMENT */}
            {activeTab === "users" && (
              <section className="bg-surface-container-lowest rounded-xl p-8 shadow-sm">
                <div className="mb-8 flex items-center justify-between">
                  <h3 className="text-lg font-bold text-on-surface">User Roles & Access</h3>
                  <div className="flex bg-surface-container-low p-1 rounded-full gap-1">
                    <button className="px-4 py-1.5 bg-white shadow-sm rounded-full text-xs font-bold text-on-surface">Active</button>
                    <button className="px-4 py-1.5 text-xs font-bold text-on-surface-variant hover:bg-white/50 rounded-full transition-colors">Pending</button>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {USERS.map((user) => (
                    <div key={user.name} className="p-4 border border-outline-variant/20 rounded-xl flex items-center justify-between hover:bg-surface-container-low transition-colors group">
                      <div className="flex items-center gap-4">
                        <img alt={user.name} className="w-10 h-10 rounded-full grayscale group-hover:grayscale-0 transition-all" src={user.img} />
                        <div>
                          <p className="font-bold text-sm text-on-surface">{user.name}</p>
                          <p className="text-xs text-on-surface-variant">{user.role} · {user.level}</p>
                        </div>
                      </div>
                      <button className="text-on-surface-variant opacity-40 hover:opacity-100 transition-opacity">
                        <span className="material-symbols-outlined">more_vert</span>
                      </button>
                    </div>
                  ))}
                </div>
                <button className="mt-6 flex items-center gap-2 text-primary font-bold text-sm hover:bg-primary/5 px-4 py-2 rounded-full transition-colors">
                  <span className="material-symbols-outlined text-sm">person_add</span> Invite New User
                </button>
              </section>
            )}

            {/* AI SENSITIVITY */}
            {activeTab === "ai" && (
              <section className="bg-surface-container-lowest rounded-xl p-8 shadow-sm">
                <div className="flex items-center gap-2 mb-6">
                  <span className="material-symbols-outlined text-primary">psychology</span>
                  <h3 className="text-lg font-bold text-on-surface">AI Sensitivity & Behavior</h3>
                </div>
                <p className="text-sm text-on-surface-variant mb-8 leading-relaxed max-w-2xl">
                  Fine-tune the IRIS AI engine&apos;s confidence thresholds, autonomy level, and inference behavior. Lower sensitivity results in fewer but higher-confidence recommendations.
                </p>
                <div className="space-y-8">
                  <div>
                    <div className="flex justify-between items-center mb-3">
                      <label className="text-sm font-bold text-on-surface">Confidence Threshold</label>
                      <span className="text-sm font-bold text-primary">{settings.aiSensitivity}% — {sensitivityLabel}</span>
                    </div>
                    <div className="flex justify-between text-xs font-bold text-on-surface-variant mb-2">
                      <span>Conservative (10%)</span>
                      <span>Balanced (74%)</span>
                      <span>Maximum (99%)</span>
                    </div>
                    <input
                      className="w-full h-3 bg-surface-container-low rounded-lg appearance-none cursor-pointer accent-primary"
                      type="range"
                      min="10"
                      max="99"
                      value={settings.aiSensitivity}
                      onChange={(e) => update({ aiSensitivity: parseInt(e.target.value) })}
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                      { label: "Conservative", value: 30, desc: "High precision, fewer alerts" },
                      { label: "Balanced", value: 74, desc: "Recommended for normal ops" },
                      { label: "Aggressive", value: 90, desc: "High recall, more noise" },
                    ].map(({ label, value, desc }) => (
                      <button
                        key={label}
                        onClick={() => update({ aiSensitivity: value })}
                        className={`p-4 rounded-xl border-2 text-left transition-all ${
                          settings.aiSensitivity === value
                            ? "border-primary bg-primary/5"
                            : "border-outline-variant/20 hover:border-primary/30"
                        }`}
                      >
                        <p className="font-bold text-sm text-on-surface">{label}</p>
                        <p className="text-xs text-on-surface-variant mt-1">{desc}</p>
                        <p className="text-primary font-bold text-sm mt-2">{value}%</p>
                      </button>
                    ))}
                  </div>

                  <div className="bg-secondary-container/20 rounded-xl p-6">
                    <h4 className="font-bold text-on-surface mb-4 flex items-center gap-2">
                      <span className="material-symbols-outlined text-primary text-sm">auto_awesome</span>
                      Current Model Configuration
                    </h4>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      {[
                        { label: "Model", value: "llama-3.3-70b-versatile" },
                        { label: "Provider", value: "Groq Cloud" },
                        { label: "Max Tokens", value: "2048" },
                        { label: "Temperature", value: "0.1" },
                      ].map(({ label, value }) => (
                        <div key={label}>
                          <p className="text-[10px] font-bold text-on-surface-variant uppercase">{label}</p>
                          <p className="font-semibold text-on-surface">{value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </section>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
