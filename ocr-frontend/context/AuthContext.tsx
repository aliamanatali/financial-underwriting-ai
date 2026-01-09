"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load persisted auth state on mount
  useEffect(() => {
    try {
      const storedAuth = localStorage.getItem(AUTH_STORAGE_KEY);
      if (storedAuth) {
        const parsedUser = JSON.parse(storedAuth);
        setUser(parsedUser);
      }
    } catch (error) {
      console.error("Error loading auth state:", error);
      localStorage.removeItem(AUTH_STORAGE_KEY);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = (username: string, password: string): boolean => {
    // Hardcoded credentials check for demo
    if (username === "admin" && password === "admin123") {
      const userData: User = {
        username: "admin",
        name: "Financial Analyst",
        email: "analyst@valiance.com",
      };
      setUser(userData);
      // Persist to localStorage
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(userData));
      return true;
    }
    return false;
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
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
