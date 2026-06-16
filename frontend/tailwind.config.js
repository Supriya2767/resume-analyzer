// tailwind.config.js
// Tells Tailwind which files to scan for class names.
// Only classes found in these files will be included in the final CSS build.

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};