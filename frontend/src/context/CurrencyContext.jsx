import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { setCurrencyConfig } from '../api/client';

const STORAGE_KEY = 'cyberquant_currency';
const DEFAULT_RATE = Number(import.meta.env.VITE_USD_INR_RATE) || 88;

const CurrencyContext = createContext(null);

export function CurrencyProvider({ children }) {
  const [currency, setCurrencyState] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored === 'INR' ? 'INR' : 'USD';
    } catch {
      return 'USD';
    }
  });

  const rate = DEFAULT_RATE;

  // Keep client.js formatter in sync with currency and rate
  useEffect(() => {
    setCurrencyConfig(currency, rate);
  }, [currency, rate]);

  const setCurrency = useCallback((next) => {
    setCurrencyState(next);
    setCurrencyConfig(next, rate);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch { /* ignore */ }
  }, [rate]);

  const toggleCurrency = useCallback(() => {
    setCurrency(currency === 'USD' ? 'INR' : 'USD');
  }, [currency, setCurrency]);

  return (
    <CurrencyContext.Provider value={{ currency, rate, setCurrency, toggleCurrency }}>
      {children}
    </CurrencyContext.Provider>
  );
}

export function useCurrency() {
  const ctx = useContext(CurrencyContext);
  if (!ctx) throw new Error('useCurrency must be used inside <CurrencyProvider>');
  return ctx;
}
