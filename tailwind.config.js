/**
 * Tailwind CSS Configuration
 * With RTL (Right-to-Left) support for Persian language
 * Per Requirement 2 - Dual-Language Support
 */

module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './static/js/**/*.js',
  ],
  
  darkMode: 'class', // Enable dark mode with class strategy
  
  theme: {
    extend: {
      // Custom colors for jewelry shop theme
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        gold: {
          50: '#fefce8',
          100: '#fef9c3',
          200: '#fef08a',
          300: '#fde047',
          400: '#facc15',
          500: '#eab308',
          600: '#ca8a04',
          700: '#a16207',
          800: '#854d0e',
          900: '#713f12',
        },
      },
      
      // Custom spacing for RTL layouts
      spacing: {
        '128': '32rem',
        '144': '36rem',
      },
      
      // Custom font families
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        persian: ['Vazir', 'Tahoma', 'Arial', 'sans-serif'],
      },
      
      // Custom border radius
      borderRadius: {
        '4xl': '2rem',
      },
    },
  },
  
  plugins: [
    // RTL support plugin
    require('tailwindcss-rtl'),
    
    // Forms plugin for better form styling
    require('@tailwindcss/forms'),
    
    // Typography plugin for rich text content
    require('@tailwindcss/typography'),
    
    // Aspect ratio plugin
    require('@tailwindcss/aspect-ratio'),
  ],
  
  // Safelist classes that might be generated dynamically
  safelist: [
    'rtl',
    'ltr',
    'text-right',
    'text-left',
    {
      pattern: /^(ml|mr|pl|pr|border-(l|r))-/,
      variants: ['rtl', 'ltr'],
    },
  ],
}
