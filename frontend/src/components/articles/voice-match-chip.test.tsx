import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VoiceMatchChip } from "./voice-match-chip";

describe("VoiceMatchChip", () => {
  it("renders the match band (success) at score 80", () => {
    render(<VoiceMatchChip score={80} bySection={null} />);
    const pill = screen.getByRole("button");
    expect(pill).toHaveTextContent("Voice match 80");
    expect(pill.className).toContain("bg-success-light");
    expect(pill.className).toContain("text-success");
  });

  it("renders the close band (warning) at score 79", () => {
    render(<VoiceMatchChip score={79} bySection={null} />);
    const pill = screen.getByRole("button");
    expect(pill.className).toContain("bg-warning-light");
    expect(pill.className).toContain("text-warning");
  });

  it("renders the close band (warning) at score 60", () => {
    render(<VoiceMatchChip score={60} bySection={null} />);
    const pill = screen.getByRole("button");
    expect(pill.className).toContain("bg-warning-light");
    expect(pill.className).toContain("text-warning");
  });

  it("renders the off-voice band (error) at score 59", () => {
    render(<VoiceMatchChip score={59} bySection={null} />);
    const pill = screen.getByRole("button");
    expect(pill.className).toContain("bg-error-light");
    expect(pill.className).toContain("text-error");
  });

  it("opens a popover listing per-section scores on click", () => {
    render(
      <VoiceMatchChip
        score={82}
        bySection={{ "0": 90, "1": 74 }}
      />,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button"));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveTextContent("Section 1 — 90");
    expect(dialog).toHaveTextContent("Section 2 — 74");
  });

  it("shows an empty state in the popover when bySection is null", () => {
    render(<VoiceMatchChip score={82} bySection={null} />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("dialog")).toHaveTextContent(/no section/i);
  });
});
