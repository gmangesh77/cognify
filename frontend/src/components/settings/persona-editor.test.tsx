import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { confidenceWidthClass, PersonaEditor } from "./persona-editor";
import { DIM_LABELS } from "@/types/persona";
import type { PersonaDetail } from "@/types/persona";

const dims = Object.fromEntries(
  Object.keys(DIM_LABELS).map((key, i) => [key, { mean: i + 1.23, stddev: 0.5, confidence: 0.9 }]),
);

const readyPersona: PersonaDetail = {
  id: "p1",
  name: "House Style",
  description: "Editorial voice",
  sample_count: 5,
  ready: true,
  updated_at: "2026-09-01T00:00:00Z",
  fingerprint: { dims, sample_count: 5 },
  samples: [],
};

const notReadyPersona: PersonaDetail = {
  ...readyPersona,
  ready: false,
  sample_count: 2,
  fingerprint: null,
};

describe("confidenceWidthClass", () => {
  it("buckets confidence into five Tailwind width classes", () => {
    expect(confidenceWidthClass(0)).toBe("w-1/5");
    expect(confidenceWidthClass(0.2)).toBe("w-1/5");
    expect(confidenceWidthClass(0.21)).toBe("w-2/5");
    expect(confidenceWidthClass(0.4)).toBe("w-2/5");
    expect(confidenceWidthClass(0.41)).toBe("w-3/5");
    expect(confidenceWidthClass(0.6)).toBe("w-3/5");
    expect(confidenceWidthClass(0.61)).toBe("w-4/5");
    expect(confidenceWidthClass(0.8)).toBe("w-4/5");
    expect(confidenceWidthClass(0.81)).toBe("w-full");
    expect(confidenceWidthClass(1)).toBe("w-full");
  });

  it("clamps out-of-range values", () => {
    expect(confidenceWidthClass(-1)).toBe("w-1/5");
    expect(confidenceWidthClass(2)).toBe("w-full");
  });
});

describe("PersonaEditor", () => {
  it("renders all 13 fingerprint dim rows with labels and confidence bars", () => {
    render(<PersonaEditor persona={readyPersona} canEdit onSave={vi.fn()} />);
    const rows = screen.getByTestId("fingerprint-card").querySelectorAll("li");
    expect(rows).toHaveLength(13);
    expect(screen.getByText("average sentence length (words)")).toBeInTheDocument();
    expect(screen.getByText("first-person words per 100 words")).toBeInTheDocument();
    // one dim's mean/stddev rendered to 2 decimals
    expect(screen.getByText("1.23 ± 0.50")).toBeInTheDocument();
  });

  it("shows a needs-N-more message when there is no fingerprint yet", () => {
    render(<PersonaEditor persona={notReadyPersona} canEdit onSave={vi.fn()} />);
    expect(screen.queryByTestId("fingerprint-card")).toBeNull();
    expect(screen.getByText(/needs 3 more samples/)).toBeInTheDocument();
  });

  it("disables Save until the form is dirty, then saves the trimmed patch", () => {
    const onSave = vi.fn();
    render(<PersonaEditor persona={readyPersona} canEdit onSave={onSave} />);
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "New Name" } });
    expect(save).not.toBeDisabled();
    fireEvent.click(save);
    expect(onSave).toHaveBeenCalledWith({ name: "New Name", description: "Editorial voice" });
  });

  it("is read-only when canEdit is false", () => {
    render(<PersonaEditor persona={readyPersona} canEdit={false} onSave={vi.fn()} />);
    expect(screen.getByLabelText("Name")).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
    expect(screen.getByText(/Only editors and admins can edit personas/)).toBeInTheDocument();
  });
});
