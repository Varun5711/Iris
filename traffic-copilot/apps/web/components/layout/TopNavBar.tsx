export default function TopNavBar() {
  return (
    <header className="fixed top-0 right-0 w-[calc(100%-16rem)] h-16 bg-surface flex justify-between items-center px-8 border-b border-surface-container-low z-40">
      <div className="flex items-center gap-6">
        <h2 className="text-lg font-bold text-on-surface">IRIS Intelligence</h2>
        <div className="h-4 w-[1px] bg-outline-variant/30"></div>
        <div className="hidden lg:flex items-center gap-6 font-medium text-sm text-on-surface/60">
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
            Ahmedabad, Gujarat
          </span>
          <span>Status: Online</span>
          <span className="opacity-50 text-xs italic">Updated 2m ago</span>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button className="p-2 text-on-surface/60 hover:text-primary transition-all">
          <span className="material-symbols-outlined">notifications</span>
        </button>
        <button className="p-2 text-on-surface/60 hover:text-primary transition-all">
          <span className="material-symbols-outlined">help_outline</span>
        </button>
        <div className="h-8 w-[1px] bg-outline-variant/30 mx-2"></div>
        <div className="flex items-center gap-3 pl-2 opacity-80 hover:opacity-100 cursor-pointer">
          <span className="text-xs font-semibold text-on-surface">Administrator</span>
          <img
            alt="Administrator"
            className="w-8 h-8 rounded-full border border-outline-variant/20"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuAycNROcX-xhqm62a_5VwPBsKN4z22DWOJUvmTFsLKUm7Pay1Xe01V7BvvzqXwdNIXnUZr6s6YOzerSWbeiDJmEQ1yCb8fAT-jiPyppcx8uC_nCXFc6kWmf9tW8GM4kiE6g4ZKcBq2kSN8WnYPDlEsFfNIRtjmrpaiMBrXXhiuQrhCIhdJ0I9sRrYHn7hYpn_6c0KBFfvCYynJLSJ5ayuFKeTQV9z2-rIdMpW8ixRZma2fyzteCUhTXy7tFafzji_b2CZwepi2IBV7C"
          />
        </div>
      </div>
    </header>
  );
}
