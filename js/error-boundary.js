window.addEventListener("error", (event) => {
  document.documentElement.dataset.jsError = event.message || "Unknown script error";
});

window.addEventListener("unhandledrejection", (event) => {
  document.documentElement.dataset.jsError = String(
    event.reason?.message || event.reason || "Unhandled rejection",
  );
});
