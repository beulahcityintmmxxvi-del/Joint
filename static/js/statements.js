document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".summary-card, .info-item, .stmt-table tbody tr").forEach((el, i) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(12px)";
    setTimeout(() => {
      el.style.transition = "all 0.42s ease";
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    }, 60 * i);
  });
});