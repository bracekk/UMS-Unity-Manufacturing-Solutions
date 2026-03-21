document.addEventListener("DOMContentLoaded", function () {
  initCustomSelects();
});

function initCustomSelects(root = document) {
  const selects = root.querySelectorAll(".custom-select");

  selects.forEach((select) => {
    if (select.dataset.initialized === "true") return;
    select.dataset.initialized = "true";

    const trigger = select.querySelector(".custom-select-trigger");
    const triggerText = trigger ? trigger.querySelector("span") : null;
    const hiddenInput = select.querySelector('input[type="hidden"]');
    const options = select.querySelectorAll(".custom-option");

    if (!trigger || !triggerText || !hiddenInput || !options.length) return;

    function setSelected(value, text) {
      hiddenInput.value = value;
      triggerText.textContent = text;

      options.forEach((option) => {
        option.classList.toggle("selected", option.dataset.value === String(value));
      });
    }

    const currentOption = Array.from(options).find(
      (option) => option.dataset.value === String(hiddenInput.value)
    );

    if (currentOption) {
      setSelected(currentOption.dataset.value, currentOption.textContent.trim());
    }

    trigger.addEventListener("click", function (e) {
      e.stopPropagation();

      document.querySelectorAll(".custom-select.open").forEach((other) => {
        if (other !== select) other.classList.remove("open");
      });

      select.classList.toggle("open");
    });

    options.forEach((option) => {
      option.addEventListener("click", function (e) {
        e.stopPropagation();

        const value = option.dataset.value || "";
        const text = option.textContent.trim();

        setSelected(value, text);
        select.classList.remove("open");

        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
      });

      option.addEventListener("mouseenter", function () {
        option.classList.add("option-hovered");
      });

      option.addEventListener("mouseleave", function () {
        option.classList.remove("option-hovered");
      });
    });

    trigger.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        select.classList.toggle("open");
      }

      if (e.key === "Escape") {
        select.classList.remove("open");
      }
    });
  });

  document.addEventListener("click", function () {
    document.querySelectorAll(".custom-select.open").forEach((select) => {
      select.classList.remove("open");
    });
  });
}