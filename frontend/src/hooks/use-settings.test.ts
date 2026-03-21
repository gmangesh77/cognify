import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSettings } from "./use-settings";

describe("useSettings", () => {
  it("initializes with mock domains", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.domains).toHaveLength(2);
    expect(result.current.domains[0].name).toBe("Cybersecurity");
  });

  it("initializes with mock LLM config", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.llmConfig.primaryModel).toBe("claude-opus-4");
  });

  it("initializes with mock API keys", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.apiKeys).toHaveLength(4);
  });

  it("initializes with mock SEO defaults", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.seoDefaults.autoMetaTags).toBe(true);
  });

  it("initializes with mock general config", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.generalConfig.contentTone).toBe("professional");
  });

  it("adds a domain", () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.addDomain({
        name: "Cloud Computing",
        status: "active",
        trendSources: ["hackernews"],
        keywords: ["AWS", "Azure"],
      });
    });
    expect(result.current.domains).toHaveLength(3);
    expect(result.current.domains[2].name).toBe("Cloud Computing");
    expect(result.current.domains[2].articleCount).toBe(0);
  });

  it("updates a domain", () => {
    const { result } = renderHook(() => useSettings());
    const id = result.current.domains[0].id;
    act(() => {
      result.current.updateDomain(id, { name: "InfoSec" });
    });
    expect(result.current.domains[0].name).toBe("InfoSec");
  });

  it("deletes a domain", () => {
    const { result } = renderHook(() => useSettings());
    const id = result.current.domains[1].id;
    act(() => {
      result.current.deleteDomain(id);
    });
    expect(result.current.domains).toHaveLength(1);
  });

  it("updates LLM config", () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.updateLlmConfig({ primaryModel: "claude-sonnet-4" });
    });
    expect(result.current.llmConfig.primaryModel).toBe("claude-sonnet-4");
  });

  it("adds an API key", () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.addApiKey("arxiv", "arxiv-key-123");
    });
    expect(result.current.apiKeys).toHaveLength(5);
    expect(result.current.apiKeys[4].service).toBe("arxiv");
    expect(result.current.apiKeys[4].maskedKey).toContain("••••");
  });

  it("rotates an API key", () => {
    const { result } = renderHook(() => useSettings());
    const id = result.current.apiKeys[0].id;
    act(() => {
      result.current.rotateApiKey(id, "new-key-456");
    });
    expect(result.current.apiKeys[0].maskedKey).toContain("••••");
    expect(result.current.apiKeys[0].maskedKey).not.toBe("sk-ant-••••••••7f3a");
  });

  it("toggles a SEO default", () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.toggleSeoDefault("autoMetaTags");
    });
    expect(result.current.seoDefaults.autoMetaTags).toBe(false);
  });

  it("updates general config", () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.updateGeneralConfig({ contentTone: "casual" });
    });
    expect(result.current.generalConfig.contentTone).toBe("casual");
  });
});
