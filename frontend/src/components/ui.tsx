// PiAssess design system — shadcn-style components in the Pi World School identity.
import { forwardRef } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./dialog";
import { cn } from "../lib/utils";
import { Loader2, X } from "lucide-react";

/* ---------------------------------- Button --------------------------------- */
type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger" | "success";
type ButtonSize = "sm" | "md" | "lg" | "icon";

const buttonVariants: Record<ButtonVariant, string> = {
  primary: "bg-brand-600 text-cream hover:bg-brand-700 shadow-sm",
  secondary: "bg-brand-100 text-brand-700 hover:bg-brand-200",
  outline: "border border-stone-300 bg-white text-ink hover:bg-stone-50",
  ghost: "text-ink hover:bg-stone-100",
  danger: "bg-red-600 text-white hover:bg-red-700",
  success: "bg-green-600 text-white hover:bg-green-700",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-9 px-4 text-sm",
  lg: "h-10 px-5 text-sm",
  icon: "h-9 w-9 p-0",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", loading, disabled, children, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-1",
        "disabled:pointer-events-none disabled:opacity-50",
        buttonVariants[variant],
        buttonSizes[size],
        className
      )}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  )
);
Button.displayName = "Button";

/* ---------------------------------- Inputs --------------------------------- */
const inputBase =
  "h-9 w-full rounded-lg border border-stone-300 bg-white px-3 text-sm text-ink placeholder:text-stone-400 " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:opacity-50";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn(inputBase, className)} {...props} />
);
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea ref={ref} className={cn(inputBase, "min-h-[72px] py-2", className)} {...props} />
  )
);
Textarea.displayName = "Textarea";

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => (
    <select ref={ref} className={cn(inputBase, "pr-8", className)} {...props} />
  )
);
Select.displayName = "Select";

export function Label({ className, children, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn("mb-1 block text-xs font-medium text-stone-600", className)} {...props}>
      {children}
    </label>
  );
}

export function FieldError({ children }: { children?: React.ReactNode }) {
  if (!children) return null;
  return <p className="mt-1 text-xs text-red-600">{children}</p>;
}

/* ---------------------------------- Cards ---------------------------------- */
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-stone-200 bg-white shadow-card", className)} {...props} />;
}
export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center justify-between border-b border-stone-100 px-5 py-3.5", className)} {...props} />;
}
export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-sm font-semibold text-ink", className)} {...props} />;
}
export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 py-4", className)} {...props} />;
}

/* ---------------------------------- Badge ---------------------------------- */
type BadgeTone = "neutral" | "brand" | "blue" | "green" | "amber" | "red";
const badgeTones: Record<BadgeTone, string> = {
  neutral: "bg-stone-100 text-stone-600",
  brand: "bg-brand-100 text-brand-700",
  blue: "bg-blue-50 text-blue-700",
  green: "bg-green-50 text-green-700",
  amber: "bg-amber-50 text-amber-700",
  red: "bg-red-50 text-red-700",
};
export function Badge({ tone = "neutral", className, children }: { tone?: BadgeTone; className?: string; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium", badgeTones[tone], className)}>
      {children}
    </span>
  );
}

/* ---------------------------------- Table ---------------------------------- */
export function Table({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto">
      <table className={cn("w-full text-sm", className)} {...props} />
    </div>
  );
}
export function TH({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn("border-b border-stone-200 px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-stone-500", className)} {...props} />;
}
export function TD({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("border-b border-stone-100 px-4 py-2.5 text-ink", className)} {...props} />;
}

/* --------------------------------- States ---------------------------------- */
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-5 w-5 animate-spin text-brand-600", className)} />;
}

export function EmptyState({ icon, title, description, action }: { icon?: React.ReactNode; title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      {icon && <div className="text-stone-300">{icon}</div>}
      <p className="text-sm font-medium text-ink">{title}</p>
      {description && <p className="max-w-sm text-xs text-stone-500">{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <p className="text-sm text-red-600">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

/* --------------------------------- Dialog ---------------------------------- */
export { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter };

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Delete",
  tone = "danger",
  onConfirm,
  loading,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  tone?: "danger" | "primary";
  onConfirm: () => void;
  loading?: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant={tone === "danger" ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* -------------------------------- PageHeader -------------------------------- */
export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold text-ink">{title}</h1>
        {description && <p className="mt-0.5 text-sm text-stone-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, icon, hint }: { label: string; value: React.ReactNode; icon?: React.ReactNode; hint?: string }) {
  return (
    <Card className="flex items-center gap-4 px-5 py-4">
      {icon && <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-600">{icon}</div>}
      <div className="min-w-0">
        <p className="truncate text-xs font-medium text-stone-500">{label}</p>
        <p className="text-xl font-semibold text-ink">{value}</p>
        {hint && <p className="text-[11px] text-stone-400">{hint}</p>}
      </div>
    </Card>
  );
}
