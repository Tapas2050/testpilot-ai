import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => 
    sessionStorage.getItem('testpilot_token') || localStorage.getItem('testpilot_token')
  );
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadUser() {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const userData = await api.auth.me();
        setUser(userData);
      } catch (err) {
        console.warn('Session restoration failed:', err);
        sessionStorage.removeItem('testpilot_token');
        localStorage.removeItem('testpilot_token');
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, [token]);

  const login = async (email, password) => {
    const res = await api.auth.login(email, password);
    const accessToken = res.access_token;
    sessionStorage.setItem('testpilot_token', accessToken);
    setToken(accessToken);
    const userData = await api.auth.me();
    setUser(userData);
    return userData;
  };

  const register = async (email, password) => {
    return await api.auth.register(email, password);
  };

  const logout = async () => {
    try {
      if (token) {
        await api.auth.logout();
      }
    } catch (err) {
      console.warn('Logout API call failed:', err);
    } finally {
      sessionStorage.removeItem('testpilot_token');
      localStorage.removeItem('testpilot_token');
      setToken(null);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
