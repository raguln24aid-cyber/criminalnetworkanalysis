/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0F172A',
          800: '#1E293B',
          700: '#334155'
        },
        primary: {
          500: '#3B82F6',
          400: '#60A5FA'
        },
        danger: {
          500: '#EF4444'
        },
        warning: {
          500: '#F59E0B'
        },
        // Dual-tone holographic accent pair - used sparingly for glow effects
        // (icons, active states, key borders), not as body text/background
        // colors, so it reads as an accent rather than a theme change.
        cyan: {
          400: '#22D3EE',
          500: '#06B6D4'
        },
        neon: {
          pink: '#EC4899',
          magenta: '#E879F9'
        }
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(34,211,238,0.35), 0 0 60px rgba(34,211,238,0.15)',
        'glow-pink': '0 0 20px rgba(236,72,153,0.35), 0 0 60px rgba(236,72,153,0.15)',
        'glow-primary': '0 0 20px rgba(59,130,246,0.35), 0 0 60px rgba(59,130,246,0.15)',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { opacity: 1, filter: 'drop-shadow(0 0 12px rgba(34,211,238,0.6))' },
          '50%': { opacity: 0.85, filter: 'drop-shadow(0 0 24px rgba(236,72,153,0.6))' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0) translateX(0)' },
          '50%': { transform: 'translateY(-14px) translateX(6px)' },
        },
      },
      animation: {
        'pulse-glow': 'pulse-glow 3s ease-in-out infinite',
        float: 'float 7s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
