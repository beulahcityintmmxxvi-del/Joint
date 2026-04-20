document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".notif-item, .summary-card").forEach((el, i) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(12px)";
    setTimeout(() => {
      el.style.transition = "all 0.42s ease";
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    }, 70 * i);
  });
});