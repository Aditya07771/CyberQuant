/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        th: {
          bg:               'var(--bg)',
          surface:          'var(--surface)',
          'surface-el':     'var(--surface-elevated)',
          border:           'var(--border)',
          'text-primary':   'var(--text-primary)',
          'text-secondary': 'var(--text-secondary)',
          'text-muted':     'var(--text-muted)',
          accent:           'var(--accent-primary)',
          'accent-hover':   'var(--accent-primary-hover)',
          'accent-sec':     'var(--accent-secondary)',
          brand:            'var(--brand)',
          'brand-hover':    'var(--brand-hover)',
          success:          'var(--success)',
          warning:          'var(--warning)',
          danger:           'var(--danger)',
          'brand-tint':     'var(--brand-tint)',
          'success-tint':   'var(--success-tint)',
          'warning-tint':   'var(--warning-tint)',
          'danger-tint':    'var(--danger-tint)',
          'border-strong':  'var(--border-strong)',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        serif: ['"DM Serif Display"', 'Georgia', '"Times New Roman"', 'serif'],
        mono: ['"IBM Plex Mono"', 'JetBrains Mono', 'monospace'],
      },
      fontSize: {
        'fluid-hero': 'clamp(2rem, 1.5rem + 2.5vw, 3.5rem)',
        'fluid-h2':   'clamp(1.5rem, 1.2rem + 1.5vw, 2.25rem)',
        'fluid-h3':   'clamp(1rem, 0.9rem + 0.5vw, 1.25rem)',
        'fluid-body':  'clamp(0.8125rem, 0.75rem + 0.25vw, 0.9375rem)',
      },
      borderRadius: {
        sm:      '12px',
        DEFAULT: '12px',
        md:      '16px',
        lg:      '20px',
        xl:      '24px',
        full:    '9999px',
      },
      boxShadow: {
        'soft':     'var(--shadow-soft)',
        'card':     'var(--shadow-card)',
        'elevated': 'var(--shadow-elevated)',
      },
      spacing: {
        'fluid-sm': 'clamp(0.75rem, 0.5rem + 1vw, 1.25rem)',
        'fluid-md': 'clamp(1rem, 0.75rem + 1.25vw, 1.75rem)',
        'fluid-lg': 'clamp(1.5rem, 1rem + 2vw, 3rem)',
        'fluid-xl': 'clamp(2rem, 1.5rem + 2.5vw, 4rem)',
      },
    },
  },
  plugins: [],
}
