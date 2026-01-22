/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#007ACC',
        'primary-hover': '#0E6BBF',
        background: '#FFFFFF',
        foreground: '#1E1E1E',
        muted: '#616161',
        border: '#E0E0E0',
        success: '#27AE60',
        danger: '#E74C3C',
        warning: '#F39C12',
      },
    },
  },
  plugins: [],
}
