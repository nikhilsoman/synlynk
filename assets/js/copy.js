document.querySelectorAll('.copy-btn').forEach(button => {
    button.addEventListener('click', () => {
        const text = button.getAttribute('data-copy');
        navigator.clipboard.writeText(text).then(() => {
            button.classList.add('success');
            const icon = button.querySelector('svg');
            const originalPath = icon.innerHTML;
            
            // Checkmark SVG path
            icon.innerHTML = '<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>';
            
            setTimeout(() => {
                button.classList.remove('success');
                icon.innerHTML = originalPath;
            }, 1500);
        });
    });
});
