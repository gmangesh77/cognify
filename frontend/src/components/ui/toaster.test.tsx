import { describe, it, expect, vi, afterEach } from "vitest";
import { act, render, renderHook, screen } from "@testing-library/react";
import { ToastProvider, useToast, DEFAULT_TOAST_MS } from "./toaster";

function Trigger({ message, ms }: { message: string; ms?: number }) {
  const { showToast } = useToast();
  return (
    <button type="button" onClick={() => showToast(message, ms)}>
      fire
    </button>
  );
}

describe("ToastProvider / useToast", () => {
  afterEach(() => vi.useRealTimers());

  it("shows the message and hides it after the default duration", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Trigger message="Saved" />
      </ToastProvider>,
    );
    act(() => screen.getByText("fire").click());
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
    act(() => vi.advanceTimersByTime(DEFAULT_TOAST_MS - 1));
    expect(screen.getByRole("status")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("a newer toast replaces the old one and restarts the timer", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Trigger message="First" ms={1000} />
        <Trigger message="Second" ms={1000} />
      </ToastProvider>,
    );
    const [first, second] = screen.getAllByText("fire");
    act(() => first.click());
    act(() => vi.advanceTimersByTime(900));
    act(() => second.click());
    expect(screen.getByRole("status")).toHaveTextContent("Second");
    act(() => vi.advanceTimersByTime(900));
    // The first toast's timer must not have cleared the second one.
    expect(screen.getByRole("status")).toHaveTextContent("Second");
    act(() => vi.advanceTimersByTime(100));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("useToast throws outside a provider", () => {
    expect(() => renderHook(() => useToast())).toThrow(/ToastProvider/);
  });
});
