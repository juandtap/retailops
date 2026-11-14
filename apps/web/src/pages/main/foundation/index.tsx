import { ComponentCard } from "@/components/shared/component-card";
import { PageMeta } from "@/components/shared/page-meta";
import { useTranslations } from "@/i18n";

export default function FoundationPage() {
  const t = useTranslations("foundation");
  return (
    <div className="space-y-6">
      <PageMeta title={t("title")} description={t("description")} />
      <div>
        <p className="text-sm font-medium text-brand-500">RetailOps</p>
        <h1 className="mt-2 text-2xl font-semibold text-gray-800 dark:text-white/90">{t("heading")}</h1>
        <p className="mt-2 text-gray-500 dark:text-gray-400">{t("description")}</p>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <ComponentCard title={t("platformTitle")}>
          <p className="text-gray-600 dark:text-gray-300">{t("platformBody")}</p>
        </ComponentCard>
        <ComponentCard title={t("dataTitle")}>
          <p className="text-gray-600 dark:text-gray-300">{t("dataBody")}</p>
        </ComponentCard>
      </div>
      <ComponentCard title={t("nextTitle")}>
        <p className="text-gray-600 dark:text-gray-300">{t("nextBody")}</p>
      </ComponentCard>
      <p className="text-sm text-gray-500 dark:text-gray-400">{t("attribution")}</p>
    </div>
  );
}
