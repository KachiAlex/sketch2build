import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ToastProvider } from "./components/ui/toast";
import { AppHeader } from "./components/AppHeader";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Sketch from "./pages/Sketch";
import Prompt from "./pages/Prompt";
import Results from "./pages/Results";
import AdminRules from "./pages/AdminRules";
import Review from "./pages/Review";
import NotFound from "./pages/NotFound";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-vellum">
        <div className="font-mono-tech text-sm text-muted">Loading…</div>
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function AppLayout() {
  return (
    <div className="min-h-screen bg-paper-bg text-foreground">
      <AppHeader />
      <main className="mx-auto max-w-[1320px] px-6 py-8 md:px-14">
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
            path="/results/:jobId"
            element={
              <PrivateRoute>
                <Results />
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
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <ToastProvider>
          <Routes>
          {/* Public marketing site */}
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Authenticated app */}
          <Route path="/*" element={<AppLayout />} />
        </Routes>
      </ToastProvider>
    </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
