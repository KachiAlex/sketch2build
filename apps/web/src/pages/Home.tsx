import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { useInView } from "../lib/useInView";
import { useAuth } from "../contexts/AuthContext";

/* ------------------------------------------------------------------ */
/* Reveal wrapper                                                      */
/* ------------------------------------------------------------------ */
function Reveal({
  children,
  className = "",
  delay = 0,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: keyof JSX.IntrinsicElements;
}) {
  const { ref, inView } = useInView<HTMLDivElement>();
  const Comp = Tag as any;
  return (
    <Comp
      ref={ref as any}
      className={`reveal ${inView ? "is-visible" : ""} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </Comp>
  );
}

/* ------------------------------------------------------------------ */
/* Drafting button (matches .btn in design)                           */
/* ------------------------------------------------------------------ */
type BtnVariant = "solid" | "ghost" | "block";
function DraftButton({
  children,
  variant = "solid",
  className = "",
  as: Comp = "button",
  full = false,
  ...rest
}: {
  children: ReactNode;
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

/* ------------------------------------------------------------------ */
/* Logo mark (matches .logo .mark)                                     */
/* ------------------------------------------------------------------ */
function LogoMark({ light = false }: { light?: boolean }) {
  return (
    <span className="flex items-center gap-[9px] font-display font-bold text-[17px]">
      <span
        className={`relative h-5 w-5 border-2 ${light ? "border-white" : "border-ink"}`}
      >
        <span className="absolute -right-1 -bottom-1 h-2 w-2 bg-redline" />
      </span>
      <span className={light ? "text-white" : "text-ink"}>Sketch2Build</span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Navbar (plain, non-sticky — inside vellum grid)                     */
/* ------------------------------------------------------------------ */
function Navbar() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  const links = [
    { label: "Product", href: "#features" },
    { label: "How it works", href: "#how" },
    { label: "Pricing", href: "#pricing" },
    { label: "Docs", href: "https://github.com/KachiAlex/sketch2build#readme" },
  ];

  return (
    <nav className="relative mx-auto flex max-w-[1320px] items-center justify-between px-6 py-[22px] md:px-14">
      <Link to="/" className="shrink-0">
        <LogoMark />
      </Link>

      <div className="hidden items-center gap-[34px] md:flex">
        {links.map((l) => (
          <a
            key={l.label}
            href={l.href}
            className="text-[13.5px] font-medium text-ink-soft transition-colors hover:text-redline"
          >
            {l.label}
          </a>
        ))}
      </div>

      <div className="hidden items-center gap-3 md:flex">
        {user ? (
          <>
            <DraftButton as={Link} to="/dashboard" variant="ghost">
              Dashboard
            </DraftButton>
            <DraftButton variant="block" onClick={logout}>
              Sign out
            </DraftButton>
          </>
        ) : (
          <>
            <DraftButton as={Link} to="/login" variant="ghost">
              Sign in
            </DraftButton>
            <DraftButton as={Link} to="/register" variant="solid">
              Get started
            </DraftButton>
          </>
        )}
      </div>

      <button
        className="grid h-10 w-10 place-items-center rounded-[2px] border-[1.5px] border-ink md:hidden"
        onClick={() => setOpen((v) => !v)}
        aria-label="Toggle menu"
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full border-t border-vellum-line bg-vellum px-6 py-4 md:hidden">
          <div className="flex flex-col gap-3">
            {links.map((l) => (
              <a
                key={l.label}
                href={l.href}
                onClick={() => setOpen(false)}
                className="text-[13.5px] font-medium text-ink-soft"
              >
                {l.label}
              </a>
            ))}
            <div className="mt-2 flex flex-col gap-2">
              {user ? (
                <DraftButton as={Link} to="/dashboard" variant="solid" full>
                  Go to dashboard
                </DraftButton>
              ) : (
                <>
                  <DraftButton as={Link} to="/login" variant="ghost" full>
                    Sign in
                  </DraftButton>
                  <DraftButton as={Link} to="/register" variant="solid" full>
                    Get started
                  </DraftButton>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/* Hero sheet visual (sketch → vector) — exact SVG from design         */
/* ------------------------------------------------------------------ */
function HeroSheet() {
  return (
    <div className="relative aspect-[1/0.92] w-full border-[1.5px] border-ink bg-white shadow-sheet">
      {/* corner ticks */}
      <span className="tick tick-tl" />
      <span className="tick tick-tr" />
      <span className="tick tick-bl" />
      <span className="tick tick-br" />

      {/* label */}
      <div className="absolute left-4 top-3.5 font-mono-tech text-[10.5px] tracking-[0.05em] text-muted-soft">
        FIG.01 — SKETCH TO VECTOR
      </div>

      {/* static red divider with rotated label (matches canvas inset) */}
      <div className="divider-scan left-1/2 top-[38px] bottom-[60px]" />

      {/* canvas: inset 38px 20px 60px */}
      <div className="absolute left-5 right-5 top-[38px] bottom-[60px]">
        <svg viewBox="0 0 400 340" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
          {/* left: hand sketch */}
          <g
            stroke="#8B93A6"
            strokeWidth="2.4"
            fill="none"
            strokeLinecap="round"
            className="animate-draw"
          >
            <path d="M12,10 L182,13 L179,168 L10,164 Z" />
            <path d="M12,90 L100,88" />
            <path d="M100,88 L98,164" />
            <path d="M40,10 L42,50 L60,49 L58,9" />
            <path d="M130,164 L128,140 L160,142" />
          </g>

          {/* right: vectorized plan */}
          <g
            stroke="#2C5AA0"
            strokeWidth="1.6"
            fill="none"
            className="animate-draw-slow"
            style={{ animationDelay: "0.5s" }}
          >
            <rect x="210" y="10" width="180" height="160" />
            <line x1="300" y1="10" x2="300" y2="170" />
            <line x1="210" y1="90" x2="300" y2="90" />
            <rect x="238" y="4" width="24" height="4" fill="#2C5AA0" stroke="none" />
            <rect x="330" y="166" width="24" height="4" fill="#2C5AA0" stroke="none" />
          </g>

          {/* dimensions */}
          <g fontFamily="JetBrains Mono, monospace" fontSize="8" fill="#9BA3B4">
            <text x="210" y="188">3.60m</text>
            <text x="330" y="188">2.40m</text>
            <text x="393" y="90" transform="rotate(90 393 90)">4.80m</text>
          </g>
        </svg>
      </div>

      {/* title block */}
      <div className="absolute bottom-0 right-0 min-w-[150px] bg-ink px-3.5 py-2.5 font-mono-tech text-[10px] leading-[1.6] text-white">
        <b className="text-[11px]">PROJECT — OJO RESIDENCE</b>
        <br />
        SCALE 1:100 &nbsp; REV.04
        <br />
        DRAWN — SKETCH2BUILD AI
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Hero                                                                */
/* ------------------------------------------------------------------ */
function Hero() {
  return (
    <div className="mx-auto flex max-w-[1320px] flex-col items-center gap-10 px-6 pb-[70px] pt-[30px] md:px-14 lg:flex-row lg:gap-[60px] lg:items-center">
      <div className="flex-1 text-center lg:basis-[1.05] lg:text-left">
        <Reveal>
          <span className="mb-[22px] inline-block border border-blueprint px-2.5 py-1 font-mono-tech text-[11.5px] tracking-[0.09em] text-blueprint">
            SHEET A-100 · OVERVIEW
          </span>
        </Reveal>

        <Reveal delay={80}>
          <h1 className="mx-auto max-w-xl text-balance font-display text-4xl font-bold leading-[1.1] tracking-[-0.5px] text-ink sm:text-5xl lg:mx-0 lg:text-[46px]">
            From a rough sketch to a{" "}
            <em className="not-italic text-redline">structurally sound</em> plan.
          </h1>
        </Reveal>

        <Reveal delay={160}>
          <p className="mx-auto mb-[30px] max-w-[480px] text-balance text-base leading-[1.65] text-[#454B58] lg:mx-0">
            Sketch2Build turns a hand-drawn sketch or a plain-language brief into a
            dimensioned, code-checked floor plan — reviewed by a licensed architect,
            exported straight into the CAD or BIM tool you already use.
          </p>
        </Reveal>

        <Reveal delay={240}>
          <div className="mb-9 flex flex-col items-center gap-3.5 sm:flex-row lg:justify-start">
            <DraftButton as={Link} to="/register" variant="solid" className="w-full sm:w-auto">
              Start a project
            </DraftButton>
            <DraftButton as="a" href="#how" variant="block" className="w-full sm:w-auto">
              See how it works
            </DraftButton>
          </div>
        </Reveal>

        <Reveal delay={320}>
          <div className="flex flex-wrap justify-center gap-[26px] font-mono-tech text-xs text-muted lg:justify-start">
            <span>EXPORTS: DXF · IFC · PDF</span>
            <span>CODE: NIGERIAN NBC</span>
          </div>
        </Reveal>
      </div>

      <Reveal delay={200} className="w-full max-w-md lg:max-w-none lg:flex-1">
        <HeroSheet />
      </Reveal>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Section heading with sheet number                                   */
/* ------------------------------------------------------------------ */
function SectionHead({ no, title }: { no: string; title: string }) {
  return (
    <Reveal className="mb-[34px] flex items-baseline gap-4">
      <span className="border border-redline px-[9px] py-[3px] font-mono-tech text-xs text-redline">
        {no}
      </span>
      <h2 className="font-display text-[26px] font-bold text-ink">{title}</h2>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ */
/* How it works                                                        */
/* ------------------------------------------------------------------ */
const STEPS = [
  {
    num: "A-101",
    title: "Sketch or describe",
    desc: "Upload a hand sketch and set one reference dimension, or describe the brief — plot size, orientation, room program — in plain language.",
  },
  {
    num: "A-102",
    title: "AI drafts the plan",
    desc: "The engine digitizes or generates ranked layout candidates, checked against setback, room-size, and circulation rules as it works.",
  },
  {
    num: "A-103",
    title: "Architect reviews",
    desc: "Edit walls and labels directly, resolve any compliance flags, then sign off before the plan is finalized and exported.",
  },
];

function HowItWorks() {
  return (
    <section id="how" className="mx-auto max-w-[1320px] px-6 py-[60px] md:px-14">
      <SectionHead no="01" title="How it works" />
      <Reveal>
        {/* container: border-top ink; children: border-right vellum-line except last */}
        <div className="flex flex-col border-t-[1.5px] border-ink md:flex-row">
          {STEPS.map((s, i) => (
            <div
              key={s.num}
              className={`flex-1 pt-[22px] px-[22px] ${
                i < STEPS.length - 1
                  ? "border-b-[1.5px] border-vellum-line md:border-b-0 md:border-r-[1.5px] md:border-vellum-line"
                  : ""
              }`}
            >
              <span className="mb-2.5 block font-mono-tech text-xs text-blueprint">
                {s.num}
              </span>
              <h3 className="mb-2 font-display text-[16.5px] font-semibold text-ink">
                {s.title}
              </h3>
              <p className="mb-5 text-[13px] leading-[1.6] text-[#565E6C]">{s.desc}</p>
            </div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Features                                                            */
/* ------------------------------------------------------------------ */
const FEATURES = [
  {
    title: "Sketch digitization",
    desc: "Walls, doors, and windows detected and vectorized from a single photographed sketch.",
  },
  {
    title: "Prompt-to-design",
    desc: "Generate multiple ranked layout options directly from a written brief and site dimensions.",
  },
  {
    title: "Compliance checking",
    desc: "Setbacks, minimum room sizes, and circulation validated against local building code.",
  },
  {
    title: "CAD / BIM export",
    desc: "Clean DXF, DWG, and IFC output that opens directly in AutoCAD, Revit, or ArchiCAD.",
  },
];

function FeatureIcon() {
  return (
    <span className="relative mb-3.5 block h-[30px] w-[30px] border-[1.5px] border-blueprint">
      <span className="absolute inset-1.5 border-[1.5px] border-blueprint" />
    </span>
  );
}

function Features() {
  return (
    <section id="features" className="mx-auto max-w-[1320px] px-6 pb-[60px] pt-0 md:px-14">
      <SectionHead no="02" title="Built for the way plans actually get made" />
      <Reveal>
        <div className="grid grid-cols-1 gap-[1.5px] border-[1.5px] border-vellum-line bg-vellum-line sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="bg-vellum px-5 py-6 transition-colors duration-300 hover:bg-blueprint-pale"
            >
              <FeatureIcon />
              <h4 className="mb-2 font-display text-sm font-semibold text-ink">{f.title}</h4>
              <p className="text-xs leading-[1.55] text-[#565E6C]">{f.desc}</p>
            </div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* CTA band                                                            */
/* ------------------------------------------------------------------ */
function CTABand() {
  return (
    <section id="pricing" className="bg-ink">
      <Reveal>
        <div className="mx-auto flex max-w-[1320px] flex-col items-start justify-between gap-6 px-6 py-14 md:flex-row md:items-center md:px-14 md:py-14">
          <div>
            <h3 className="mb-1.5 font-display text-[22px] font-semibold text-white">
              Start your first plan
            </h3>
            <p className="font-mono-tech text-[13.5px] text-[#9AA3B8]">
              NO CAD LICENSE REQUIRED TO BEGIN
            </p>
          </div>
          <DraftButton as={Link} to="/register" variant="solid" className="w-full sm:w-auto">
            Get started free
          </DraftButton>
        </div>
      </Reveal>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Footer                                                              */
/* ------------------------------------------------------------------ */
function Footer() {
  return (
    <footer className="mx-auto flex max-w-[1320px] flex-col items-center justify-between gap-3 px-6 py-[26px] font-mono-tech text-xs text-muted md:flex-row md:px-14">
      <span>© SKETCH2BUILD</span>
      <span className="flex gap-4">
        <a href="/login" className="hover:text-ink">PRIVACY</a>
        <a href="/login" className="hover:text-ink">TERMS</a>
        <a href="https://github.com/KachiAlex/sketch2build#readme" className="hover:text-ink">DOCS</a>
      </span>
    </footer>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */
export default function Home() {
  const topRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    topRef.current?.scrollIntoView({ block: "start" });
  }, []);

  return (
    <div ref={topRef} className="min-h-screen bg-vellum">
      {/* nav + hero share the vellum grid background (matches .home.grid-bg) */}
      <div className="bg-vellum-grid">
        <Navbar />
        <Hero />
      </div>

      <main>
        <HowItWorks />
        <Features />
        <CTABand />
      </main>
      <Footer />
    </div>
  );
}
