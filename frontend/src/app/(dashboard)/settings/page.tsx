"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { SettingsNav } from "@/components/settings/settings-nav";
import { DomainsTab } from "@/components/settings/domains-tab";
import { LlmConfigTab } from "@/components/settings/llm-config-tab";
import { VisualsTab } from "@/components/settings/visuals-tab";
import { ApiKeysTab } from "@/components/settings/api-keys-tab";
import { SeoDefaultsTab } from "@/components/settings/seo-defaults-tab";
import { GeneralTab } from "@/components/settings/general-tab";
import { PromptsSettings } from "@/components/settings/prompts-settings";
import { useToast } from "@/components/ui/toaster";
import { useSettings } from "@/hooks/use-settings";
import type { SettingsTab } from "@/types/settings";

const OAUTH_MESSAGES: Record<string, string> = {
  success: "LinkedIn connected successfully",
  expired: "OAuth session expired — please try again",
  token_exchange_failed: "Failed to connect with LinkedIn — token exchange error",
  storage_failed: "LinkedIn authorized but failed to save token — please retry",
};

function getOAuthToast(params: URLSearchParams): string | null {
  const oauth = params.get("oauth");
  if (!oauth) return null;
  const message = params.get("message");
  return oauth === "success"
    ? OAUTH_MESSAGES.success
    : OAUTH_MESSAGES[message ?? ""] ?? "OAuth error — please try again";
}

function SettingsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const oauthToast = getOAuthToast(searchParams);
  const [activeTab, setActiveTab] = useState<SettingsTab>(oauthToast ? "api-keys" : "domains");
  const { showToast } = useToast();

  const settings = useSettings();

  useEffect(() => {
    if (!oauthToast) return;
    showToast(oauthToast);
    router.replace("/settings", { scroll: false });
  }, [oauthToast, router, showToast]);

  return (
    <div className="space-y-8">
      <Header
        title="Settings"
        subtitle="Configure domains, LLM models, API keys, and publishing defaults"
      />

      <div className="flex min-h-[480px] overflow-hidden rounded-lg border border-neutral-200">
        <SettingsNav activeTab={activeTab} onTabChange={setActiveTab} />

        <div className="flex-1 p-8">
          {activeTab === "domains" && (
            <DomainsTab
              domains={settings.domains}
              actions={{
                add: (data) => { settings.addDomain(data); showToast("Domain saved"); },
                update: (id, u) => { settings.updateDomain(id, u); showToast("Domain updated"); },
                delete: (id) => { settings.deleteDomain(id); showToast("Domain deleted"); },
              }}
            />
          )}

          {activeTab === "llm" && (
            <LlmConfigTab
              config={settings.llmConfig}
              onUpdate={(u) => { settings.updateLlmConfig(u); showToast("LLM config updated"); }}
            />
          )}

          {activeTab === "prompts" && <PromptsSettings />}

          {activeTab === "visuals" && (
            <VisualsTab
              config={settings.llmConfig}
              onUpdate={(u) => { settings.updateLlmConfig(u); showToast("Image settings updated"); }}
            />
          )}

          {activeTab === "api-keys" && (
            <ApiKeysTab
              apiKeys={settings.apiKeys}
              actions={{
                add: (s, k) => { settings.addApiKey(s, k); showToast("API key added"); },
                rotate: (id, k) => { settings.rotateApiKey(id, k); showToast("API key rotated"); },
                delete: (id) => { settings.deleteApiKey(id); showToast("API key deleted"); },
              }}
            />
          )}

          {activeTab === "seo" && (
            <SeoDefaultsTab
              defaults={settings.seoDefaults}
              onToggle={(key) => { settings.toggleSeoDefault(key); showToast("SEO setting updated"); }}
            />
          )}

          {activeTab === "general" && (
            <GeneralTab
              config={settings.generalConfig}
              onUpdate={(u) => { settings.updateGeneralConfig(u); showToast("Settings updated"); }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={null}>
      <SettingsContent />
    </Suspense>
  );
}
