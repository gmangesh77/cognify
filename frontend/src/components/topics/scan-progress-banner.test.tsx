import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScanProgressBanner } from "./scan-progress-banner";

describe("ScanProgressBanner", () => {
  it("shows scanning progress with 0 completed", () => {
    render(<ScanProgressBanner isScanning={true} completedSources={0} totalSources={5} failedSources={[]} />);
    expect(screen.getByText(/0 of 5 sources complete/)).toBeInTheDocument();
  });
  it("shows scanning progress mid-scan", () => {
    render(<ScanProgressBanner isScanning={true} completedSources={3} totalSources={5} failedSources={[]} />);
    expect(screen.getByText(/3 of 5 sources complete/)).toBeInTheDocument();
  });
  it("shows partial failure warning after scan", () => {
    render(<ScanProgressBanner isScanning={false} completedSources={5} totalSources={5} failedSources={["reddit"]} />);
    expect(screen.getByText(/1 of 5 sources failed/)).toBeInTheDocument();
  });
  it("renders nothing when idle with no failures", () => {
    const { container } = render(
      <ScanProgressBanner isScanning={false} completedSources={0} totalSources={5} failedSources={[]} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
