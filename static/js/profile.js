document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".panel, .snapshot-item, .quick-link").forEach((el, i) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(12px)";
    setTimeout(() => {
      el.style.transition = "all 0.4s ease";
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    }, 70 * i);
  });
});