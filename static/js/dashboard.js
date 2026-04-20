document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".panel, .mini-card, .tx-row").forEach((el, i) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(12px)";
    setTimeout(() => {
      el.style.transition = "all 0.45s ease";
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    }, 80 * i);
  });
});