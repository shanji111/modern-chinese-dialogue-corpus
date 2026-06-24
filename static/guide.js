(function () {
    const links = Array.from(document.querySelectorAll("[data-guide-nav]"));
    const sections = Array.from(document.querySelectorAll("[data-guide-section]"));

    if (!links.length || !sections.length) {
        return;
    }

    function setActiveSection(id) {
        links.forEach((link) => {
            link.classList.toggle("is-active", link.dataset.guideNav === id);
        });
    }

    const observer = new IntersectionObserver(
        (entries) => {
            const visible = entries
                .filter((entry) => entry.isIntersecting)
                .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

            if (visible) {
                setActiveSection(visible.target.id);
            }
        },
        {
            rootMargin: "-20% 0px -60% 0px",
            threshold: [0.2, 0.4, 0.6],
        }
    );

    sections.forEach((section) => observer.observe(section));
    setActiveSection(sections[0].id);
})();
