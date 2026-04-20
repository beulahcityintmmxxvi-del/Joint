document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("txModal");

  if (!modal) return;

  modal.addEventListener("show.bs.modal", (event) => {
    const button = event.relatedTarget;

    const id = button.getAttribute("data-id");
    const date = button.getAttribute("data-date");
    const receiver = button.getAttribute("data-receiver");
    const purpose = button.getAttribute("data-purpose");
    const type = button.getAttribute("data-type");
    const status = button.getAttribute("data-status");
    const amount = button.getAttribute("data-amount");

    document.getElementById("modal-id").textContent = `#${id}`;
    document.getElementById("modal-date").textContent = date;
    document.getElementById("modal-receiver").textContent = receiver;
    document.getElementById("modal-purpose").textContent = purpose;
    document.getElementById("modal-type").textContent = type.charAt(0).toUpperCase() + type.slice(1);
    document.getElementById("modal-status").textContent = status.charAt(0).toUpperCase() + status.slice(1);
    document.getElementById("modal-amount").textContent = `$${amount}`;
  });
});