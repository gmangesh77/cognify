import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PromptsSettings } from "./prompts-settings";

const save = vi.fn();
const reset = vi.fn();
const showToast = vi.fn();
vi.mock("@/hooks/use-prompts", () => ({
  usePrompts: () => ({
    prompts: [{
      key: "content_outline.user", step: "content_outline", description: "d",
      variables: ["title"], default_template: "D {title}", template: "D {title}",
      is_overridden: false, updated_by: null, updated_at: null,
    }],
    isLoading: false, error: null, save, reset, isSaving: false,
  }),
}));
vi.mock("@/components/ui/toaster", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/lib/auth/role", () => ({ currentRole: () => "admin" }));

describe("PromptsSettings", () => {
  beforeEach(() => { save.mockReset(); reset.mockReset(); showToast.mockReset(); });

  it("saves the edited template and toasts", async () => {
    save.mockResolvedValue({});
    render(<PromptsSettings />);
    fireEvent.click(screen.getByText("content_outline.user"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "E {title}" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith("content_outline.user", "E {title}"));
    expect(showToast).toHaveBeenCalledWith("Prompt saved");
  });

  it("surfaces 422 violations instead of a toast", async () => {
    save.mockRejectedValue({ response: { status: 422, data: { detail: { violations: ["missing required variable {title}"] } } } });
    render(<PromptsSettings />);
    fireEvent.click(screen.getByText("content_outline.user"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "no vars" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("missing required variable {title}")).toBeInTheDocument();
    expect(showToast).not.toHaveBeenCalled();
  });
});
