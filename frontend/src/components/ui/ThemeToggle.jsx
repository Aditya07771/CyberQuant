import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from './ThemeProvider';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export const ThemeToggle = ({ className }) => {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={twMerge(
        'relative inline-flex items-center justify-center p-2 rounded-full transition-colors duration-200',
        'text-th-text-secondary hover:text-th-text-primary hover:bg-th-surface-el',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-th-accent',
        className
      )}
      aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
      title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
    >
      <Sun
        className={clsx(
          'w-4 h-4 transition-all duration-300 absolute',
          theme === 'light' ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 -rotate-90 scale-50'
        )}
      />
      <Moon
        className={clsx(
          'w-4 h-4 transition-all duration-300 absolute',
          theme === 'dark' ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 rotate-90 scale-50'
        )}
      />
      <span className="sr-only">Toggle theme</span>
    </button>
  );
};
