"use strict";

document.querySelectorAll("img[data-fallback]").forEach((image) => {
  const useFallback = () => {
    const fallback = image.dataset.fallback;
    if (fallback) {
      delete image.dataset.fallback;
      image.src = fallback;
    }
  };
  image.addEventListener("error", useFallback);
  if (image.complete && image.naturalWidth === 0) useFallback();
});

const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#navigation");

if (menuButton && navigation) {
  document.documentElement.classList.add("js-enabled");
  menuButton.hidden = false;
  const closeMenu = () => {
    menuButton.setAttribute("aria-expanded", "false");
    navigation.classList.remove("is-open");
  };
  menuButton.addEventListener("click", () => {
    const open = menuButton.getAttribute("aria-expanded") !== "true";
    menuButton.setAttribute("aria-expanded", String(open));
    navigation.classList.toggle("is-open", open);
  });
  navigation.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menuButton.getAttribute("aria-expanded") === "true") {
      closeMenu();
      menuButton.focus();
    }
  });
  window.matchMedia("(min-width: 901px)").addEventListener("change", closeMenu);
}

// 終了したイベントを「開催案内」のまま残さない。申し込み状況は主催者の案内を参照。
document.querySelectorAll("[data-event-end]").forEach((event) => {
  const end = Date.parse(event.dataset.eventEnd);
  if (Number.isFinite(end) && Date.now() >= end) {
    const status = event.querySelector("[data-event-status]");
    if (status) status.textContent = "開催終了";
    const link = event.querySelector(".event-link");
    if (link) {
      link.textContent = "開催時の案内を見る ↗";
    }
  }
});
