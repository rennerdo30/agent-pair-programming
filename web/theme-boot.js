// Applies the saved theme before first paint (a separate file because the CSP forbids inline scripts).
try {
  const t = localStorage.getItem("pairdesk.theme");
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
} catch (e) { /* storage unavailable: follow the system theme */ }
