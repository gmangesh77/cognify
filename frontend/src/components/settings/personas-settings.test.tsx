import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PersonasSettings } from "./personas-settings";

const create = vi.fn();
const update = vi.fn();
const remove = vi.fn();
const addSample = vi.fn();
const removeSample = vi.fn();
const showToast = vi.fn();

const summary = {
  id: "p1",
  name: "House Style",
  description: "Editorial voice",
  sample_count: 5,
  ready: true,
  updated_at: "2026-09-01T00:00:00Z",
};

const detail = {
  ...summary,
  fingerprint: { dims: {}, sample_count: 5 },
  samples: [{ id: "s1", word_count: 200, preview: "prose…", created_at: "2026-09-01T00:00:00Z" }],
};

vi.mock("@/hooks/use-personas", () => ({
  usePersonas: () => ({ personas: [summary], isLoading: false, error: null, create, update, remove }),
  usePersona: (id: string | null) => ({
    persona: id ? detail : null,
    isLoading: false,
    addSample,
    removeSample,
    isMutating: false,
  }),
}));
vi.mock("@/components/ui/toaster", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/lib/auth/role", () => ({ currentRole: () => "editor" }));

describe("PersonasSettings", () => {
  beforeEach(() => {
    create.mockReset();
    update.mockReset();
    remove.mockReset();
    addSample.mockReset();
    removeSample.mockReset();
    showToast.mockReset();
  });

  it("selects a persona and shows its editor + samples", () => {
    render(<PersonasSettings />);
    fireEvent.click(screen.getByText("House Style"));
    expect(screen.getByTestId("persona-editor")).toBeInTheDocument();
    expect(screen.getByTestId("persona-samples")).toBeInTheDocument();
  });

  it("creates a persona and toasts", async () => {
    create.mockResolvedValue(summary);
    render(<PersonasSettings />);
    fireEvent.change(screen.getByPlaceholderText("New persona name"), { target: { value: "Brand Voice" } });
    fireEvent.click(screen.getByRole("button", { name: "New persona" }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ name: "Brand Voice" }));
    expect(showToast).toHaveBeenCalledWith("Persona created");
  });

  it("saves an edited persona and toasts", async () => {
    update.mockResolvedValue(summary);
    render(<PersonasSettings />);
    fireEvent.click(screen.getByText("House Style"));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "New Name" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(update).toHaveBeenCalledWith("p1", { name: "New Name", description: "Editorial voice" }));
    expect(showToast).toHaveBeenCalledWith("Persona saved");
  });

  it("adds a sample and surfaces 422 violations instead of a toast", async () => {
    addSample.mockRejectedValue({ response: { status: 422, data: { detail: { violations: ["need 5 samples of 150+ words, have 1"] } } } });
    render(<PersonasSettings />);
    fireEvent.click(screen.getByText("House Style"));
    const longText = Array.from({ length: 150 }, (_, i) => `word${i}`).join(" ");
    fireEvent.change(screen.getByPlaceholderText(/Paste a writing sample/), { target: { value: longText } });
    fireEvent.click(screen.getByRole("button", { name: "Add sample" }));
    expect(await screen.findByText("need 5 samples of 150+ words, have 1")).toBeInTheDocument();
    expect(showToast).not.toHaveBeenCalledWith("Sample added");
  });

  it("removes a sample and toasts", async () => {
    removeSample.mockResolvedValue(detail);
    render(<PersonasSettings />);
    fireEvent.click(screen.getByText("House Style"));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(removeSample).toHaveBeenCalledWith("s1"));
    expect(showToast).toHaveBeenCalledWith("Sample removed");
  });

  it("deletes the selected persona and clears selection", async () => {
    remove.mockResolvedValue(undefined);
    render(<PersonasSettings />);
    fireEvent.click(screen.getByText("House Style"));
    fireEvent.click(screen.getByRole("button", { name: "Delete persona" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith("p1"));
    expect(showToast).toHaveBeenCalledWith("Persona deleted");
  });

  it("shows a placeholder when nothing is selected", () => {
    render(<PersonasSettings />);
    expect(screen.getByText("Select a persona to view or edit it.")).toBeInTheDocument();
  });
});
