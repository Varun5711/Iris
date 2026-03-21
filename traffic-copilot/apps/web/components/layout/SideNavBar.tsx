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
  { name: "Logs", href: "/logs", icon: "history" },
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

      <div className="mt-auto p-2 bg-white/40 rounded-xl flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-surface-container overflow-hidden shrink-0">
          <img
            alt="User Profile"
            className="w-full h-full object-cover"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuB3vqjucqqRc2VXueHkV-YsA2dWryk0rpV38pD91nzzfUORXTqtymed376E3EnduIeQAqpXPcE1V1088XXtZ68dFUYM5uuVWQWRotcoxDc2oGYi1LqkaNG5l7K5k2B_89Frj0QW79mRvGLxD0XXNtk9f1Cr6T0O4-dBAqGbw-lA9c0aPh5-gyQBOAvImXJPKdwC0uAQYX8mx_-YeAYsgGeUoQFSexKY6hhkgvjnXMycbntndf3w8xTQ_9TQATLy_Wu6KbUmq9xZiz7M"
          />
        </div>
        <div className="flex-1 overflow-hidden">
          <p className="text-sm font-bold text-on-surface truncate">Admin User</p>
          <p className="text-[10px] text-on-surface-variant truncate">District Supervisor</p>
        </div>
      </div>
    </aside>
  );
}
