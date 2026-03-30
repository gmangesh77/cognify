import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CreateTopicModal } from "./create-topic-modal";

// Mock the API
vi.mock("@/lib/api/trends", () => ({
  analyzeTopic: vi.fn(),
}));

import { analyzeTopic } from "@/lib/api/trends";
const mockAnalyze = vi.mocked(analyzeTopic);

describe("CreateTopicModal", () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    onCreateOnly: vi.fn(),
    onCreateAndGenerate: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <CreateTopicModal {...defaultProps} open={false} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders title input and analyze button", () => {
    render(<CreateTopicModal {...defaultProps} />);
    expect(screen.getByPlaceholderText(/zero trust/i)).toBeInTheDocument();
    expect(screen.getByText("Analyze")).toBeInTheDocument();
  });

  it("disables analyze button when title is too short", () => {
    render(<CreateTopicModal {...defaultProps} />);
    const btn = screen.getByText("Analyze");
    expect(btn).toBeDisabled();
  });

  it("enables analyze button when title has 3+ characters", () => {
    render(<CreateTopicModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/zero trust/i);
    fireEvent.change(input, { target: { value: "Zero Trust" } });
    expect(screen.getByText("Analyze")).not.toBeDisabled();
  });

  it("shows analysis results after successful analyze", async () => {
    mockAnalyze.mockResolvedValue({
      description: "An exploration of zero trust",
      domain: "cybersecurity",
      keywords: ["zero trust", "cloud"],
      target_audience: "Security engineers",
      content_tone: "technical-authoritative",
      preferred_angle: "Implementation guide",
    });

    render(<CreateTopicModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/zero trust/i);
    fireEvent.change(input, { target: { value: "Zero Trust Architecture" } });
    fireEvent.click(screen.getByText("Analyze"));

    await waitFor(() => {
      // "Create Topic" appears as both a heading and a button — find the button specifically
      expect(
        screen.getByRole("button", { name: "Create Topic" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Create & Generate Article" }),
      ).toBeInTheDocument();
    });
  });

  it("shows error message when analyze fails", async () => {
    mockAnalyze.mockRejectedValue(new Error("API Error"));

    render(<CreateTopicModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/zero trust/i);
    fireEvent.change(input, { target: { value: "Test Topic" } });
    fireEvent.click(screen.getByText("Analyze"));

    await waitFor(() => {
      expect(screen.getByText(/failed to analyze/i)).toBeInTheDocument();
    });
  });

  it("calls onClose when Cancel is clicked", () => {
    render(<CreateTopicModal {...defaultProps} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it("calls onCreateOnly with correct data when Create Topic is clicked", async () => {
    mockAnalyze.mockResolvedValue({
      description: "An exploration of zero trust",
      domain: "cybersecurity",
      keywords: ["zero trust", "cloud"],
      target_audience: "Security engineers",
      content_tone: "technical-authoritative",
      preferred_angle: "Implementation guide",
    });

    render(<CreateTopicModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/zero trust/i);
    fireEvent.change(input, { target: { value: "Zero Trust Architecture" } });
    fireEvent.click(screen.getByText("Analyze"));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Create Topic" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Create Topic" }));
    expect(defaultProps.onCreateOnly).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Zero Trust Architecture",
        domain: "cybersecurity",
      }),
    );
  });

  it("calls onCreateAndGenerate with correct data when Create & Generate Article is clicked", async () => {
    mockAnalyze.mockResolvedValue({
      description: "An exploration of zero trust",
      domain: "cybersecurity",
      keywords: ["zero trust", "cloud"],
      target_audience: "Security engineers",
      content_tone: "technical-authoritative",
      preferred_angle: "Implementation guide",
    });

    render(<CreateTopicModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/zero trust/i);
    fireEvent.change(input, { target: { value: "Zero Trust Architecture" } });
    fireEvent.click(screen.getByText("Analyze"));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Create & Generate Article" }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Create & Generate Article" }));
    expect(defaultProps.onCreateAndGenerate).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Zero Trust Architecture",
        keywords: ["zero trust", "cloud"],
      }),
    );
  });

  it("shows analyzing state while request is pending", async () => {
    let resolveAnalyze!: (value: unknown) => void;
    mockAnalyze.mockReturnValue(
      new Promise((resolve) => {
        resolveAnalyze = resolve;
      }) as ReturnType<typeof analyzeTopic>,
    );

    render(<CreateTopicModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/zero trust/i);
    fireEvent.change(input, { target: { value: "Zero Trust Architecture" } });
    fireEvent.click(screen.getByText("Analyze"));

    await waitFor(() => {
      expect(screen.getByText("Analyzing...")).toBeInTheDocument();
    });

    resolveAnalyze({
      description: "desc",
      domain: "cybersecurity",
      keywords: [],
      target_audience: "engineers",
      content_tone: "technical-authoritative",
      preferred_angle: "guide",
    });
  });
});
