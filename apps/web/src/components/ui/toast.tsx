import * as React from "react";
import { cn } from "../../lib/utils";

type ToastVariant = "default" | "success" | "error" | "warning";

interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

const ToastContext = React.createContext<{
  toast: (t: Omit<ToastItem, "id">) => void;
} | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);

  const toast = React.useCallback((t: Omit<ToastItem, "id">) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { ...t, id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id));
    }, 5000);
  }, []);

  const variantStyles: Record<ToastVariant, string> = {
    default: "border-border bg-background text-foreground",
    success: "border-green-300 bg-green-50 text-green-900",
    error: "border-red-300 bg-red-50 text-red-900",
    warning: "border-amber-300 bg-amber-50 text-amber-900",
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto flex max-w-sm flex-col gap-1 rounded-md border px-4 py-3 shadow-lg",
              variantStyles[t.variant]
            )}
          >
            <p className="text-sm font-semibold">{t.title}</p>
            {t.description && (
              <p className="text-xs opacity-90">{t.description}</p>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be inside ToastProvider");
  return ctx;
}
