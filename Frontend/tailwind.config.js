/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: 'rgb(var(--paper-rgb) / <alpha-value>)',
        ink: '#16181D',
        crimson: 'rgb(var(--crimson-rgb) / <alpha-value>)',
        'crimson-hover': 'rgb(var(--crimson-hover-rgb) / <alpha-value>)',
        cream: '#F2EAD3',
        navy: '#0F1722',
        'navy-2': '#16243B',
        'cream-ink': '#EDE4CF',
      },
      fontFamily: {
        display: ['"Playfair Display"', 'serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        ui: ['Inter', 'system-ui', 'sans-serif'],
      },
      spacing: {
        gutter: '2.5rem',
      },
      maxWidth: {
        broadsheet: '1200px',
      },
      boxShadow: {
        paper: '0 1px 0 rgba(22,24,29,0.08), 0 10px 30px -12px rgba(22,24,29,0.18)',
      },
    },
  },
  plugins: [],
};
