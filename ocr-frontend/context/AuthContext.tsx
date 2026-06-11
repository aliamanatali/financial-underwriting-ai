"use client";

import {
  createContext,
  useContext,
  useState,
  ReactNode,
} from "react";

interface User {
  username: string;
  name: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (username: string, password: string) => boolean;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTH_STORAGE_KEY = "financial_underwriting_auth";

// Signin is disabled — the app is always authenticated with this default user.
const DEFAULT_USER: User = {
  username: "admin",
  name: "Financial Analyst",
  email: "analyst@valiance.com",
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(DEFAULT_USER);
  const [isLoading, setIsLoading] = useState(false);

  // Signin is disabled — login always succeeds with the default user.
  const login = (): boolean => {
    setUser(DEFAULT_USER);
    return true;
  };

  // Logout keeps the app authenticated so the signin page never reappears.
  const logout = () => {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    setUser(DEFAULT_USER);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        login,
        logout,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
