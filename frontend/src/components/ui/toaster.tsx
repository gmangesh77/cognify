"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

/**
 * INFRA-008 — one toaster for the whole dashboard. Replaces the three
 * hand-rolled `useState<string | null>` + `setTimeout` copies that lived
 * in the articles, settings and topics pages. Markup is unchanged.
 */

export const DEFAULT_TOAST_MS = 4000;

export type ShowToast = (message: string, ms?: number) => void;

interface ToastContextValue {
  showToast: ShowToast;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const showToast = useCallback<ShowToast>(
    (text, ms = DEFAULT_TOAST_MS) => {
      clearTimer();
      setMessage(text);
      timer.current = setTimeout(() => {
        setMessage(null);
        timer.current = null;
      }, ms);
    },
    [clearTimer],
  );

  useEffect(() => clearTimer, [clearTimer]);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {message && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-50 rounded-lg bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg"
        >
          {message}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}
