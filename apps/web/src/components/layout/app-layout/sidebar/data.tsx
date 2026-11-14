import { LayoutGridIcon } from "@/icons";
import type { NavItem } from "./types";
export const navItems: NavItem[] = [
 { icon: <LayoutGridIcon className="size-6" />, key: "retailopsDashboard", path: "/" },
 { icon: <LayoutGridIcon className="size-6" />, key: "retailopsSales", path: "/sales" },
 { icon: <LayoutGridIcon className="size-6" />, key: "retailopsForecast", path: "/forecasts" },
 { icon: <LayoutGridIcon className="size-6" />, key: "retailopsModel", path: "/model" },
 { icon: <LayoutGridIcon className="size-6" />, key: "retailopsPipelines", path: "/pipelines" },
];
export const othersItems: NavItem[] = [];
export const supportItems: NavItem[] = [];
