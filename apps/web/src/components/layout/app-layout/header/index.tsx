import ThemeToggleButton from "@/components/shared/header/theme-toggler";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/components/ui/sidebar";
import { useTranslations } from "@/i18n";
import { MenuTwoIcon } from "@/icons";

export default function AppHeader() {
  const t = useTranslations("foundation");
  const { toggleSidebar } = useSidebar();
  return (
    <header className="sticky top-0 z-50 flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center gap-3">
        <Button variant="outline" size="icon" onClick={toggleSidebar} aria-label={t("toggleSidebar")}>
          <MenuTwoIcon />
        </Button>
        <span className="font-medium text-gray-800 dark:text-white/90">{t("local")}</span>
      </div>
      <ThemeToggleButton />
    </header>
  );
}
