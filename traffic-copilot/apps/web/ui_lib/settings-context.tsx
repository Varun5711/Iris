"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";

export interface AppSettings {
  dataSources: {
    trafficCamera: boolean;
    iotSensors: boolean;
    weatherApi: boolean;
    cctv: boolean;
  };
  apiEndpoint: string;
  aiSensitivity: number;
  autoActions: {
    logMajorIncidents: boolean;
    autoDispatchDrones: boolean;
    smartRerouting: boolean;
    alertAuthorities: boolean;
  };
  mapLayers: {
    traffic: boolean;
    incidents: boolean;
    signals: boolean;
    cameras: boolean;
    diversionRoutes: boolean;
    affectedSegments: boolean;
  };
  alerts: {
    criticalChannels: { email: boolean; sms: boolean; phone: boolean };
    moderateChannels: { email: boolean; sms: boolean; phone: boolean };
  };
}

const DEFAULT: AppSettings = {
  dataSources: { trafficCamera: true, iotSensors: false, weatherApi: true, cctv: true },
  apiEndpoint: "http://localhost:8000",
  aiSensitivity: 74,
  autoActions: { logMajorIncidents: true, autoDispatchDrones: false, smartRerouting: true, alertAuthorities: false },
  mapLayers: { traffic: true, incidents: true, signals: true, cameras: true, diversionRoutes: true, affectedSegments: true },
  alerts: {
    criticalChannels: { email: true, sms: true, phone: true },
    moderateChannels: { email: true, sms: false, phone: false },
  },
};

interface SettingsCtx {
  settings: AppSettings;
  update: (patch: Partial<AppSettings>) => void;
  save: () => void;
  saved: boolean;
}

const Ctx = createContext<SettingsCtx>({
  settings: DEFAULT,
  update: () => {},
  save: () => {},
  saved: false,
});

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("iris-settings-v2");
      if (stored) setSettings(JSON.parse(stored));
    } catch {}
  }, []);

  const update = (patch: Partial<AppSettings>) => {
    setSettings((p) => ({ ...p, ...patch }));
  };

  const save = () => {
    localStorage.setItem("iris-settings-v2", JSON.stringify(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <Ctx.Provider value={{ settings, update, save, saved }}>
      {children}
    </Ctx.Provider>
  );
}

export const useSettings = () => useContext(Ctx);
