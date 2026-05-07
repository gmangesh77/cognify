import { describe, expect, it } from "vitest";
import { pickGeneratedImageSrc } from "./imageSrc";

describe("pickGeneratedImageSrc", () => {
  it("prefers image_url when present", () => {
    const src = pickGeneratedImageSrc({
      image_url: "https://cdn.test/foo.png",
      image_base64: null,
      mime_type: "image/png",
    });
    expect(src).toBe("https://cdn.test/foo.png");
  });

  it("falls back to a base64 data URL", () => {
    const src = pickGeneratedImageSrc({
      image_url: null,
      image_base64: "iVBOR=",
      mime_type: "image/png",
    });
    expect(src).toBe("data:image/png;base64,iVBOR=");
  });

  it("defaults mime to image/png when missing", () => {
    const src = pickGeneratedImageSrc({
      image_url: null,
      image_base64: "iVBOR=",
      mime_type: "",
    });
    expect(src).toBe("data:image/png;base64,iVBOR=");
  });

  it("returns null when neither URL nor base64 is set", () => {
    const src = pickGeneratedImageSrc({
      image_url: null,
      image_base64: null,
      mime_type: "image/png",
    });
    expect(src).toBeNull();
  });

  it("ignores base64 when a URL is also present", () => {
    const src = pickGeneratedImageSrc({
      image_url: "https://cdn.test/foo.png",
      image_base64: "iVBOR=",
      mime_type: "image/png",
    });
    expect(src).toBe("https://cdn.test/foo.png");
  });
});
