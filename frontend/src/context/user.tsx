import { createContext, useContext, useMemo, useState, type ReactNode, useEffect, useCallback } from 'react';

export type User = {
  userId: string;
  email: string;
  name: string;
  email_verified: boolean;
  userName?: string;
  displayName?: string;
  profilePicture?: string;
  schoolName?: string;
  sellerRating?: number;
  buyerRating?: number;
};

export type AuthTokens = {
  access_token: string;
  id_token: string;
  refresh_token?: string;
  expires_in?: number;
};

export type UserContextValue = {
  user: User | null;
  tokens: AuthTokens | null;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setTokens: (tokens: AuthTokens | null) => void;
  logout: () => void;
  isAuthenticated: boolean;
};

const USER_STORAGE_KEY = 'user';
const TOKENS_STORAGE_KEY = 'auth_tokens';

const UserContext = createContext<UserContextValue | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(null);
  const [tokens, setTokensState] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    try {
      const userRaw = localStorage.getItem(USER_STORAGE_KEY);
      const tokensRaw = localStorage.getItem(TOKENS_STORAGE_KEY);
      
      if (userRaw) {
        const parsed = JSON.parse(userRaw) as User;
        setUserState(parsed);
      }
      
      if (tokensRaw) {
        const parsed = JSON.parse(tokensRaw) as AuthTokens;
        setTokensState(parsed);
      }
    } catch {
      // ignore storage errors
    } finally {
      setIsLoading(false);
    }
  }, []);

  const setUser = useCallback((next: User | null) => {
    setUserState(next);
    try {
      if (next) {
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(next));
      } else {
        localStorage.removeItem(USER_STORAGE_KEY);
      }
    } catch {
      // ignore storage errors
    }
  }, []);

  const setTokens = useCallback((next: AuthTokens | null) => {
    setTokensState(next);
    try {
      if (next) {
        localStorage.setItem(TOKENS_STORAGE_KEY, JSON.stringify(next));
      } else {
        localStorage.removeItem(TOKENS_STORAGE_KEY);
      }
    } catch {
      // ignore storage errors
    }
  }, []);

  const logout = useCallback(() => {
    setUserState(null);
    setTokensState(null);
    try {
      localStorage.removeItem(USER_STORAGE_KEY);
      localStorage.removeItem(TOKENS_STORAGE_KEY);
    } catch {
      // ignore storage errors
    }
  }, []);

  const isAuthenticated = useMemo(() => {
    return !!(user && tokens?.access_token);
  }, [user, tokens]);

  const value = useMemo(() => ({ 
    user, 
    tokens, 
    isLoading, 
    setUser, 
    setTokens, 
    logout, 
    isAuthenticated 
  }), [user, tokens, isLoading, setUser, setTokens, logout, isAuthenticated]);

  return (
    <UserContext.Provider value={value}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return ctx;
}
