"use client";
import { useState, useEffect } from "react";

export default function TopNavBar() {
  const [time, setTime] = useState("");

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTime(now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header
      className="fixed top-0 right-0 h-16 z-40 flex items-center justify-between px-6"
      style={{
        width: "calc(100% - 16rem)",
        background: "rgba(7,11,20,0.85)",
        borderBottom: "1px solid rgba(255,255,255,0.07)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
      }}
    >
      {/* Left: Brand + Status */}
      <div className="flex items-center gap-5">
        <div className="flex items-center gap-2.5">
          <div
            className="w-7 h-7 rounded-lg iris-gradient flex items-center justify-center flex-shrink-0"
          >
            <span className="material-symbols-outlined text-white text-[15px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              traffic
            </span>
          </div>
          <span className="text-sm font-bold tracking-tight" style={{ color: "#f1f5f9" }}>
            IRIS
            <span className="font-light text-slate-400 ml-1">Intelligence</span>
          </span>
        </div>

        <div className="hidden lg:flex items-center gap-1" style={{ height: "24px", width: "1px", background: "rgba(255,255,255,0.08)" }} />

        <div className="hidden lg:flex items-center gap-5 text-xs">
          <span className="flex items-center gap-2 text-slate-400">
            <span
              className="w-1.5 h-1.5 rounded-full iris-led"
              style={{ color: "#4ade80", background: "#4ade80" }}
            />
            Ahmedabad, Gujarat
          </span>
          <span className="flex items-center gap-1.5 text-slate-500">
            <span className="material-symbols-outlined text-[13px]">sensors</span>
            System Online
          </span>
          <span className="iris-mono text-[11px] text-slate-500 tabular-nums">{time}</span>
        </div>
      </div>

      {/* Right: Actions + Avatar */}
      <div className="flex items-center gap-1">
        <button
          className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-200 transition-colors"
          style={{ background: "transparent" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.06)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
        >
          <span className="material-symbols-outlined text-[18px]">notifications</span>
        </button>
        <button
          className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-200 transition-colors"
          style={{ background: "transparent" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.06)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
        >
          <span className="material-symbols-outlined text-[18px]">help_outline</span>
        </button>

        <div className="w-px h-5 mx-2" style={{ background: "rgba(255,255,255,0.08)" }} />

        <div className="flex items-center gap-2.5 cursor-pointer group">
          <div className="text-right hidden sm:block">
            <p className="text-[11px] font-semibold text-slate-300 leading-none">Administrator</p>
            <p className="text-[10px] text-slate-500 mt-0.5 leading-none">Traffic Control</p>
          </div>
          <div className="relative">
            <img
              alt="Administrator"
              className="w-8 h-8 rounded-full object-cover"
              style={{ border: "1.5px solid rgba(74,222,128,0.3)" }}
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuAycNROcX-xhqm62a_5VwPBsKN4z22DWOJUvmTFsLKUm7Pay1Xe01V7BvvzqXwdNIXnUZr6s6YOzerSWbeiDJmEQ1yCb8fAT-jiPyppcx8uC_nCXFc6kWmf9tW8GM4kiE6g4ZKcBq2kSN8WnYPDlEsFfNIRtjmrpaiMBrXXhiuQrhCIhdJ0I9sRrYHn7hYpn_6c0KBFfvCYynJLSJ5ayuFKeTQV9z2-rIdMpW8ixRZma2fyzteCUhTXy7tFafzji_b2CZwepi2IBV7C"
            />
            <span
              className="absolute bottom-0 right-0 w-2 h-2 rounded-full border border-[#070b14] iris-led"
              style={{ background: "#4ade80", color: "#4ade80" }}
            />
          </div>
        </div>
      </div>
    </header>
  );
}
