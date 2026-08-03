import { Link } from "react-router-dom";
import { Home as HomeIcon, ArrowLeft } from "lucide-react";
import { Button } from "../components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-vellum-grid">
      <div className="relative w-full max-w-md border-[1.5px] border-ink bg-white p-10 text-center shadow-sheet">
        <span className="tick tick-tl" />
        <span className="tick tick-tr" />
        <span className="tick tick-bl" />
        <span className="tick tick-br" />

        <p className="font-display text-6xl font-bold text-redline">404</p>
        <p className="mt-2 font-mono-tech text-xs text-muted">
          SHEET ERR-404 · PAGE NOT FOUND
        </p>
        <p className="mt-4 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Button variant="outline" asChild>
            <Link to="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Go back
            </Link>
          </Button>
          <Button asChild>
            <Link to="/dashboard">
              <HomeIcon className="mr-2 h-4 w-4" />
              Dashboard
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
