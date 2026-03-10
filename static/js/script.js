// Rent Hub - Main Script
document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash-messages li');
    flashMessages.forEach(function (msg) {
        setTimeout(function () {
            msg.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-10px)';
            setTimeout(function () {
                msg.remove();
            }, 500);
        }, 5000);
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
