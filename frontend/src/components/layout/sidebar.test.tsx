import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "./sidebar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

describe("Sidebar", () => {
  it("renders Cognify logo text", () => {
    render(<Sidebar />);
    expect(screen.getByText("Cognify")).toBeInTheDocument();
  });

  it("renders all navigation items", () => {
    render(<Sidebar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Topics")).toBeInTheDocument();
    expect(screen.getByText("Articles")).toBeInTheDocument();
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Publishing")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders navigation links with correct hrefs", () => {
    render(<Sidebar />);
    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /topics/i })).toHaveAttribute("href", "/topics");
    expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute("href", "/settings");
  });
});
