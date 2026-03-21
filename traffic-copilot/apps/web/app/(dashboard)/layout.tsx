import SideNavBar from "@/components/layout/SideNavBar";
import TopNavBar from "@/components/layout/TopNavBar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <SideNavBar />
      <div className="flex-1 ml-64">
        <TopNavBar />
        {children}
      </div>
    </div>
  );
}
