document.addEventListener("DOMContentLoaded", () => {

  const toggleBtn = document.querySelector(".toggle-password");
  const passwordInput = document.querySelector("#password");
  const toggleIcon = toggleBtn?.querySelector("i");

  if (toggleBtn && passwordInput && toggleIcon) {
    toggleBtn.addEventListener("click", () => {
      const isPassword = passwordInput.type === "password";
      passwordInput.type = isPassword ? "text" : "password";

      toggleIcon.classList.toggle("fa-eye");
      toggleIcon.classList.toggle("fa-eye-slash");
    });
  }

  const popItems = document.querySelectorAll(
    ".login-card, .promo-stat, .promo-card, .offer-links a"
  );

  popItems.forEach((item, index) => {
    item.style.opacity = "0";
    item.style.transform = "translateY(18px) scale(0.96)";
    item.style.transition = "opacity 0.45s ease, transform 0.45s ease, box-shadow 0.25s ease";

    setTimeout(() => {
      requestAnimationFrame(() => {
        item.style.opacity = "1";
        item.style.transform = "translateY(0) scale(1)";
      });
    }, 80 * index);
  });

  const flashAlerts = document.querySelectorAll(".alert");

  flashAlerts.forEach((alert) => {
    setTimeout(() => {
      alert.classList.remove("show");

      setTimeout(() => {
        alert.remove();
      }, 150);
    }, 3000);
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const messageBox = document.getElementById("pageMessage");
  const categoryButtons = document.querySelectorAll(".category-link");

  categoryButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      // update selected option
      categoryButtons.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-pressed", "false");
      });

      btn.classList.add("active");
      btn.setAttribute("aria-pressed", "true");

      // show unavailable message
      if (messageBox) {
        messageBox.classList.add("show");

        clearTimeout(window.pageMessageTimer);
        window.pageMessageTimer = setTimeout(() => {
          messageBox.classList.remove("show");
        }, 3000);
      }
    });
  });
});