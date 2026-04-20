document.addEventListener("DOMContentLoaded", () => {
  const modalEl = document.getElementById("securityModal");
  const startBtn = document.getElementById("startSecurityCheck");
  const stepOne = document.getElementById("securityStepOne");
  const stepTwo = document.getElementById("securityStepTwo");
  const stepThree = document.getElementById("securityStepThree");

  if (!modalEl || !startBtn || !stepOne || !stepTwo || !stepThree) return;

  const returnUrl = modalEl.getAttribute("data-return-url") || "/";
  let timerId = null;

  const resetModal = () => {
    stepOne.classList.remove("d-none");
    stepTwo.classList.add("d-none");
    stepThree.classList.add("d-none");
    startBtn.disabled = false;
    startBtn.textContent = "Continue";

    if (timerId) {
      clearTimeout(timerId);
      timerId = null;
    }
  };

  startBtn.addEventListener("click", () => {
    startBtn.disabled = true;
    stepOne.classList.add("d-none");
    stepThree.classList.add("d-none");
    stepTwo.classList.remove("d-none");

    timerId = setTimeout(() => {
      stepTwo.classList.add("d-none");
      stepThree.classList.remove("d-none");

      setTimeout(() => {
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) modalInstance.hide();

        window.location.href = returnUrl;
      }, 1800);
    }, 5000);
  });

  modalEl.addEventListener("hidden.bs.modal", resetModal);
});