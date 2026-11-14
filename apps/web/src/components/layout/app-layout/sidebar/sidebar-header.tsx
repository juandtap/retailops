import { SidebarHeader } from "@/components/ui/sidebar";
import { Link } from "react-router";

export default function AppSidebarHeader({ showContent }: { showContent: boolean }) {
  return (
    <SidebarHeader className="px-5 py-8">
      <Link to="/" aria-label="RetailOps" className="text-xl font-semibold text-brand-500">
        {showContent ? "RetailOps" : "RO"}
      </Link>
    </SidebarHeader>
  );
}
