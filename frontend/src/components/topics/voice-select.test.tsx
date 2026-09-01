import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VoiceSelect } from "./voice-select";
import type { PersonaSummary } from "@/types/persona";

const usePersonasMock = vi.fn();
vi.mock("@/hooks/use-personas", () => ({
  usePersonas: () => usePersonasMock(),
}));

const personas: PersonaSummary[] = [
  {
    id: "p1",
    name: "Ready Voice",
    description: null,
    sample_count: 6,
    ready: true,
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "p2",
    name: "Not Ready Voice",
    description: null,
    sample_count: 1,
    ready: false,
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("VoiceSelect", () => {
  it("renders None first plus only ready personas", () => {
    usePersonasMock.mockReturnValue({ personas, isLoading: false });
    render(<VoiceSelect value={null} onChange={vi.fn()} />);
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent("None");
    expect(options[1]).toHaveTextContent("Ready Voice");
    expect(screen.queryByText("Not Ready Voice")).not.toBeInTheDocument();
  });

  it("emits the selected persona id", () => {
    usePersonasMock.mockReturnValue({ personas, isLoading: false });
    const onChange = vi.fn();
    render(<VoiceSelect value={null} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Voice"), { target: { value: "p1" } });
    expect(onChange).toHaveBeenCalledWith("p1");
  });

  it("emits null when None is selected", () => {
    usePersonasMock.mockReturnValue({ personas, isLoading: false });
    const onChange = vi.fn();
    render(<VoiceSelect value="p1" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Voice"), { target: { value: "" } });
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("renders only None when no personas are ready", () => {
    usePersonasMock.mockReturnValue({
      personas: [personas[1]],
      isLoading: false,
    });
    render(<VoiceSelect value={null} onChange={vi.fn()} />);
    expect(screen.getAllByRole("option")).toHaveLength(1);
  });
});
