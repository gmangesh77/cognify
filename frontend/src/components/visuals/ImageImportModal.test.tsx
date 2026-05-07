import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/visuals", () => ({
  fetchImageFromUrl: vi.fn(),
  uploadBrandAsset: vi.fn(),
}));

import { fetchImageFromUrl, uploadBrandAsset } from "@/lib/api/visuals";
import { ImageImportModal } from "./ImageImportModal";

describe("ImageImportModal", () => {
  beforeEach(() => {
    vi.mocked(uploadBrandAsset).mockReset();
    vi.mocked(fetchImageFromUrl).mockReset();
  });

  it("renders nothing when closed", () => {
    render(
      <ImageImportModal
        open={false}
        onClose={() => {}}
        onImported={() => {}}
      />,
    );
    expect(screen.queryByTestId("image-import-modal")).not.toBeInTheDocument();
  });

  it("renders both tabs when open", () => {
    render(
      <ImageImportModal open onClose={() => {}} onImported={() => {}} />,
    );
    expect(screen.getByText("Upload from file")).toBeInTheDocument();
    expect(screen.getByText("Fetch from URL")).toBeInTheDocument();
  });

  it("uploads the selected file and emits the result", async () => {
    const onImported = vi.fn();
    vi.mocked(uploadBrandAsset).mockResolvedValue({
      image_url: "https://cdn.test/x.png",
      object_key: "uploads/sub/x.png",
      size_bytes: 1024,
      mime_type: "image/png",
    });
    render(
      <ImageImportModal open onClose={() => {}} onImported={onImported} />,
    );
    const fileInput = screen.getByLabelText(/Drag & drop your image here/);
    const file = new File(["x"], "logo.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /^Import$/ }));
    await waitFor(() => {
      expect(uploadBrandAsset).toHaveBeenCalledWith(file);
    });
    await waitFor(() => {
      expect(onImported).toHaveBeenCalledWith(
        expect.objectContaining({ object_key: "uploads/sub/x.png" }),
      );
    });
  });

  it("surfaces upload errors as alerts", async () => {
    vi.mocked(uploadBrandAsset).mockRejectedValue(new Error("too big"));
    render(
      <ImageImportModal open onClose={() => {}} onImported={() => {}} />,
    );
    const fileInput = screen.getByLabelText(/Drag & drop your image here/);
    const file = new File(["x"], "huge.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /^Import$/ }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("too big");
  });

  it("switches to the Fetch from URL tab on click", () => {
    render(
      <ImageImportModal open onClose={() => {}} onImported={() => {}} />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Fetch from URL" }));
    expect(
      screen.getByLabelText(/Image URL/i),
    ).toBeInTheDocument();
  });

  it("calls fetchImageFromUrl with the typed URL and surfaces success", async () => {
    const onImported = vi.fn();
    vi.mocked(fetchImageFromUrl).mockResolvedValue({
      image_url: "https://cdn.test/from-url.png",
      object_key: "imports/sub/from-url.png",
      final_url: "https://cdn.test/from-url.png",
      mime_type: "image/png",
      size_bytes: 2048,
    });
    render(
      <ImageImportModal open onClose={() => {}} onImported={onImported} />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Fetch from URL" }));
    fireEvent.change(screen.getByLabelText(/Image URL/i), {
      target: { value: "https://cdn.test/from-url.png" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Fetch & import/ }));
    await waitFor(() => {
      expect(fetchImageFromUrl).toHaveBeenCalledWith({
        url: "https://cdn.test/from-url.png",
      });
    });
    await waitFor(() => {
      expect(onImported).toHaveBeenCalled();
    });
  });

  it("surfaces fetch errors as alerts", async () => {
    vi.mocked(fetchImageFromUrl).mockRejectedValue(new Error("private host"));
    render(
      <ImageImportModal open onClose={() => {}} onImported={() => {}} />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Fetch from URL" }));
    fireEvent.change(screen.getByLabelText(/Image URL/i), {
      target: { value: "http://127.0.0.1/x.png" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Fetch & import/ }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("private host");
  });
});
