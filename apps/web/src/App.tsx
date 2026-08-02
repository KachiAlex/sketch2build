import { Routes, Route, Link, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Sketch from "./pages/Sketch";
import Prompt from "./pages/Prompt";
import AdminRules from "./pages/AdminRules";
import Review from "./pages/Review";
import { Button } from "./components/ui/button";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) {
    return <div className="p-6">Loading…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function AppLayout() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <Link to="/" className="text-xl font-bold">
            Sketch2Build
          </Link>
          <nav className="flex items-center gap-4 text-sm text-muted-foreground">
            {user ? (
              <>
                <Link to="/dashboard">Dashboard</Link>
                <Link to="/projects">Projects</Link>
                {user.role === "admin" && <Link to="/admin/rules">Rules</Link>}
                <span>{user.name}</span>
                <Button variant="ghost" size="sm" onClick={logout}>
                  Sign out
                </Button>
              </>
            ) : (
              <>
                <Link to="/login">Sign in</Link>
                <Link to="/register">Create account</Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl p-6">
        <Routes>
          <Route
            path="/dashboard"
            element={
              <PrivateRoute>
                <Dashboard />
              </PrivateRoute>
            }
          />
          <Route
            path="/projects"
            element={
              <PrivateRoute>
                <Projects />
              </PrivateRoute>
            }
          />
          <Route
            path="/sketch"
            element={
              <PrivateRoute>
                <Sketch />
              </PrivateRoute>
            }
          />
          <Route
            path="/prompt"
            element={
              <PrivateRoute>
                <Prompt />
              </PrivateRoute>
            }
          />
          <Route
            path="/admin/rules"
            element={
              <PrivateRoute>
                <AdminRules />
              </PrivateRoute>
            }
          />
          <Route
            path="/review"
            element={
              <PrivateRoute>
                <Review />
              </PrivateRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public marketing site */}
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Authenticated app */}
        <Route path="/*" element={<AppLayout />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
