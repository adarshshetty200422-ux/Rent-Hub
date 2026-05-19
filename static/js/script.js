// Rent Hub - Main Script
document.addEventListener('DOMContentLoaded', function () {
    // Add close button to flash messages and handle dismissal
    const flashMessages = document.querySelectorAll('.flash-messages li');
    flashMessages.forEach(function (msg) {
        const closeBtn = document.createElement('span');
        closeBtn.innerHTML = '&times;';
        closeBtn.style.cssText = 'margin-left: auto; cursor: pointer; font-size: 1.2rem; font-weight: bold; opacity: 0.7;';
        closeBtn.onclick = function() {
            msg.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-10px)';
            setTimeout(() => msg.remove(), 300);
        };
        msg.appendChild(closeBtn);
    });

    // Add subtle entrance animation to cards
    const cards = document.querySelectorAll('.card, .stat-card, .info-card, .service-card');
    const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    cards.forEach(function (card) {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        observer.observe(card);
    });
});
