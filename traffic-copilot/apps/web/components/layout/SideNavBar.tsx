"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const navItems = [
  { name: "Dashboard", href: "/dashboard", icon: "dashboard" },
  { name: "Incidents", href: "/incidents", icon: "warning" },
  { name: "Live Map", href: "/map", icon: "map" },
  { name: "Analytics", href: "/analytics", icon: "analytics" },
  { name: "IRIS Assistant", href: "/assistant", icon: "smart_toy" },
  { name: "Logs", href: "/ui_logs", icon: "history" },
  { name: "Camera Feeds", href: "/camera", icon: "videocam" },
  { name: "Settings", href: "/settings", icon: "settings" },
];

export default function SideNavBar() {
  const pathname = usePathname();

  return (
    <aside className="h-screen w-64 fixed left-0 top-0 bg-surface-container-low flex flex-col p-4 z-50">
      <div className="mb-8 px-2 flex items-center gap-3">
        <div className="w-8 h-8 primary-gradient rounded-lg flex items-center justify-center text-white">
          <span
            className="material-symbols-outlined text-lg"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            visibility
          </span>
        </div>
        <div>
          <h1 className="text-xl font-bold text-on-surface leading-none">IRIS</h1>
          <p className="text-[10px] uppercase tracking-widest text-primary font-bold mt-0.5">
            Road Intelligence
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 transition-colors rounded-lg text-sm font-medium tracking-tight",
                isActive
                  ? "bg-surface-container-lowest text-primary shadow-sm font-semibold"
                  : "text-on-surface/70 hover:bg-white/50"
              )}
            >
              <span
                className="material-symbols-outlined"
                style={{
                  fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0",
                }}
              >
                {item.icon}
              </span>
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>
      
      
    </aside>
  );
}
