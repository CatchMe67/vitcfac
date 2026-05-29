/**
 * Vercel Speed Insights Initialization
 * 
 * This script initializes Vercel Speed Insights for tracking web vitals
 * and performance metrics across the application.
 */

// Initialize Speed Insights queue
window.si = window.si || function () {
  (window.siq = window.siq || []).push(arguments);
};

// Load Speed Insights script
(function() {
  const script = document.createElement('script');
  script.src = '/_vercel/speed-insights/script.js';
  script.defer = true;
  script.setAttribute('data-sdkn', '@vercel/speed-insights');
  script.setAttribute('data-sdkv', '1.3.1');
  
  script.onerror = function() {
    console.log('[Vercel Speed Insights] Failed to load script. Please check if any content blockers are enabled and try again.');
  };
  
  document.head.appendChild(script);
})();
