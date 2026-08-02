import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, getToken, removeToken, setToken } from "../lib/api";

export type User = {
  id: string;
  email: string;
  name: string;
  role: string;
  organization?: string;
};

type AuthContextType = {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: {
    email: string;
    password: string;
    name: string;
    role: string;
    organization?: string;
  }) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (getToken()) {
      api
        .get<{ user: User }>("/auth/me")
        .then((data) => setUser(data.user))
        .catch(() => removeToken())
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  async function login(email: string, password: string) {
    const data = await api.post<{ user: User; token: string }>("/auth/login", { email, password });
    setToken(data.token);
    setUser(data.user);
  }

  async function register(input: {
    email: string;
    password: string;
    name: string;
    role: string;
    organization?: string;
  }) {
    const data = await api.post<{ user: User; token: string }>("/auth/register", input);
    setToken(data.token);
    setUser(data.user);
  }

  function logout() {
    removeToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
