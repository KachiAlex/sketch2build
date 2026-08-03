import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

type BtnVariant = "solid" | "ghost" | "block";
function DraftButton({
  children,
  variant = "solid",
  className = "",
  as: Comp = "button",
  full = false,
  ...rest
}: {
  children: React.ReactNode;
  variant?: BtnVariant;
  className?: string;
  as?: any;
  full?: boolean;
  [key: string]: any;
}) {
  const base =
    "inline-flex items-center justify-center font-display font-semibold text-[13.5px] px-5 py-2.5 rounded-[2px] border-[1.5px] border-transparent transition-colors duration-200 cursor-pointer";
  const variants: Record<BtnVariant, string> = {
    solid: "bg-redline text-white hover:bg-redline-dark border-redline",
    ghost: "text-ink border-ink bg-transparent hover:bg-ink hover:text-white",
    block: "text-ink border-ink bg-transparent hover:bg-ink/5",
  };
  return (
    <Comp
      className={`${base} ${variants[variant]} ${full ? "w-full text-center" : ""} ${className}`}
      {...rest}
    >
      {children}
    </Comp>
  );
}

function LogoMark() {
  return (
    <span className="flex items-center gap-[9px] font-display font-bold text-[17px]">
      <span className="relative h-5 w-5 border-2 border-ink">
        <span className="absolute -right-1 -bottom-1 h-2 w-2 bg-redline" />
      </span>
      <span className="text-ink">Sketch2Build</span>
    </span>
  );
}

export function AppHeader() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();

  const navLinks = [
    { label: "Dashboard", href: "/dashboard" },
    { label: "Projects", href: "/projects" },
    { label: "Sketch", href: "/sketch" },
    { label: "Prompt Studio", href: "/prompt" },
  ];

  if (user?.role === "admin") {
    navLinks.push({ label: "Rules", href: "/admin/rules" });
  }

  return (
    <header className="border-b-[1.5px] border-vellum-line bg-vellum">
      <div className="mx-auto flex max-w-[1320px] items-center justify-between px-6 py-[16px] md:px-14">
        <Link to="/" className="shrink-0">
          <LogoMark />
        </Link>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-[28px] md:flex">
          {navLinks.map((l) => {
            const active = location.pathname === l.href;
            return (
              <Link
                key={l.href}
                to={l.href}
                className={`text-[13.5px] font-medium transition-colors ${
                  active
                    ? "text-redline"
                    : "text-ink-soft hover:text-redline"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        {/* Desktop auth */}
        <div className="hidden items-center gap-3 md:flex">
          <span className="font-mono-tech text-xs text-muted">
            {user?.name}
          </span>
          <DraftButton variant="block" onClick={logout}>
            Sign out
          </DraftButton>
        </div>

        {/* Mobile toggle */}
        <button
          className="grid h-10 w-10 place-items-center rounded-[2px] border-[1.5px] border-ink md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="border-t border-vellum-line bg-vellum px-6 py-4 md:hidden">
          <div className="flex flex-col gap-3">
            {navLinks.map((l) => {
              const active = location.pathname === l.href;
              return (
                <Link
                  key={l.href}
                  to={l.href}
                  onClick={() => setOpen(false)}
                  className={`text-[13.5px] font-medium ${
                    active ? "text-redline" : "text-ink-soft"
                  }`}
                >
                  {l.label}
                </Link>
              );
            })}
            <div className="mt-2 flex flex-col gap-2">
              <span className="font-mono-tech text-xs text-muted">
                {user?.name}
              </span>
              <DraftButton
                variant="block"
                full
                onClick={() => {
                  logout();
                  setOpen(false);
                }}
              >
                Sign out
              </DraftButton>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
