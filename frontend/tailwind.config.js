/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './pages/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        canvas: '#F5F8FC',
        brand: {
          primary: '#0B5D3B',
          secondary: '#17855A',
        },
        sidebar: {
          bg: '#061C14',
          hover: '#0E2E22',
          active: '#174836',
        },
        trust: {
          blue: '#EAF3FF',
          border: '#D6E8FF',
        },
        card: {
          border: '#DDE6F0',
        },
      },
      borderRadius: {
        card: '12px',
      },
      boxShadow: {
        saas: '0 1px 3px 0 rgba(16, 24, 40, 0.06), 0 1px 2px -1px rgba(16, 24, 40, 0.04)',
        'saas-elevated': '0 4px 12px -2px rgba(16, 24, 40, 0.08), 0 2px 6px -2px rgba(16, 24, 40, 0.04)',
        'saas-sticky': '0 2px 10px rgba(16, 24, 40, 0.05), 0 1px 2px rgba(16, 24, 40, 0.02)',
      },
    }
  },
  plugins: []
}
