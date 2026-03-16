function initFrameworkStory(root = document) {
  const container = root.querySelector("[data-framework-story]");
  if (!container) {
    return;
  }

  const steps = Array.from(container.querySelectorAll("[data-framework-step]"));
  const panels = Array.from(container.querySelectorAll("[data-framework-panel]"));

  const setActive = (key) => {
    steps.forEach((step) => {
      step.classList.toggle("is-active", step.dataset.frameworkStep === key);
    });
    panels.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.frameworkPanel === key);
    });
  };

  steps.forEach((step) => {
    step.addEventListener("click", () => {
      setActive(step.dataset.frameworkStep);
    });
  });
}

function initRevealAnimations(root = document) {
  const items = Array.from(root.querySelectorAll(".story-reveal"));
  if (!items.length) {
    return;
  }

  if (!("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    items.forEach((item) => item.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    {
      rootMargin: "0px 0px -10% 0px",
      threshold: 0.12,
    }
  );

  items.forEach((item, index) => {
    item.style.transitionDelay = `${Math.min(index % 4, 3) * 80}ms`;
    observer.observe(item);
  });
}

function initCountUp(root = document) {
  const counters = Array.from(root.querySelectorAll("[data-countup]"));
  if (!counters.length) {
    return;
  }

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const animateCounter = (element) => {
    const target = Number(element.dataset.countup || 0);
    if (!Number.isFinite(target)) {
      return;
    }
    if (prefersReducedMotion) {
      element.textContent = String(target);
      return;
    }

    const duration = 900;
    const start = performance.now();
    const step = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      element.textContent = String(Math.round(target * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) {
        window.requestAnimationFrame(step);
      }
    };
    window.requestAnimationFrame(step);
  };

  if (!("IntersectionObserver" in window)) {
    counters.forEach(animateCounter);
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) {
        return;
      }
      animateCounter(entry.target);
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.55 });

  counters.forEach((counter) => observer.observe(counter));
}

function initStickyStoryNav(root = document) {
  const nav = root.querySelector("[data-story-nav]");
  const links = Array.from(root.querySelectorAll("[data-story-nav-link]"));
  if (!nav || !links.length) {
    return;
  }

  const targets = links
    .map((link) => {
      const id = link.getAttribute("href");
      if (!id?.startsWith("#")) {
        return null;
      }
      return {
        link,
        section: document.querySelector(id),
      };
    })
    .filter((item) => item?.section);

  const setActive = (sectionId) => {
    targets.forEach(({ link, section }) => {
      link.classList.toggle("is-active", `#${section.id}` === sectionId);
    });
  };

  if (!("IntersectionObserver" in window)) {
    setActive(targets[0] ? `#${targets[0].section.id}` : "");
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];

    if (visible?.target?.id) {
      setActive(`#${visible.target.id}`);
    }
  }, {
    rootMargin: "-20% 0px -65% 0px",
    threshold: [0.2, 0.4, 0.6],
  });

  targets.forEach(({ section }) => observer.observe(section));
}

function initLifecycleFocus(root = document) {
  const steps = Array.from(root.querySelectorAll("[data-lifecycle-step]"));
  if (!steps.length) {
    return;
  }

  const setActive = (activeStep) => {
    steps.forEach((step) => {
      step.classList.toggle("is-active", step === activeStep);
    });
  };

  steps.forEach((step) => {
    step.addEventListener("mouseenter", () => setActive(step));
    step.addEventListener("focus", () => setActive(step));
    step.addEventListener("click", () => setActive(step));
    step.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setActive(step);
      }
    });
  });
}

export const DashboardStory = {
  init(root = document) {
    // The About page stays mostly static; only lightweight reveal effects are initialized.
    initFrameworkStory(root);
    initRevealAnimations(root);
    initCountUp(root);
    initStickyStoryNav(root);
    initLifecycleFocus(root);
  },
};

window.DashboardStory = DashboardStory;

DashboardStory.init(document);
