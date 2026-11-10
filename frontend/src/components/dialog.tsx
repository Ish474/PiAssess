// Headless dialog built on the native <dialog>-like overlay (React state driven).
import { useEffect } from "react";
import { cn } from "../lib/utils";
import { X } from "lucide-react";

export function Dialog({ open, onOpenChange, children }: { open: boolean; onOpenChange: (open: boolean) => void; children: React.ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onOpenChange(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-ink/40" onClick={() => onOpenChange(false)} aria-hidden />
      {children}
    </div>
  );
}

export function DialogContent({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className={cn(
        "relative z-10 max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-stone-200 bg-white shadow-xl",
        className
      )}
    >
      {children}
    </div>
  );
}

export function DialogHeader({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("border-b border-stone-100 px-5 py-4", className)}>{children}</div>;
}

export function DialogTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h2 className={cn("text-sm font-semibold text-ink", className)}>{children}</h2>;
}

export function DialogDescription({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn("mt-1 text-xs text-stone-500", className)}>{children}</p>;
}

export function DialogFooter({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("flex justify-end gap-2 border-t border-stone-100 px-5 py-3.5", className)}>{children}</div>;
}

export function DialogCloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="absolute right-3.5 top-3.5 rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-ink"
      aria-label="Close"
    >
      <X className="h-4 w-4" />
    </button>
  );
}

export function DialogBody({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("px-5 py-4", className)}>{children}</div>;
}
