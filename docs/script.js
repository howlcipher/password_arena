document.addEventListener('DOMContentLoaded', () => {
    // Hamburger Menu
    const hamburger = document.getElementById('hamburger-menu');
    const navLinks = document.getElementById('nav-links');

    hamburger.addEventListener('click', () => {
        navLinks.classList.toggle('active');
    });

    // Theme Toggle (Green / Amber)
    const themeToggle = document.getElementById('theme-toggle');
    const htmlElement = document.documentElement;

    themeToggle.addEventListener('click', () => {
        const currentTheme = htmlElement.getAttribute('data-theme');
        if (currentTheme === 'dark') {
            htmlElement.setAttribute('data-theme', 'light');
            document.querySelector('.theme-icon').textContent = '[ AMBER_MODE ]';
        } else {
            htmlElement.setAttribute('data-theme', 'dark');
            document.querySelector('.theme-icon').textContent = '[ GREEN_MODE ]';
        }
    });

    // Initialize button text based on default theme
    if (htmlElement.getAttribute('data-theme') === 'light') {
        document.querySelector('.theme-icon').textContent = '[ AMBER_MODE ]';
    } else {
        document.querySelector('.theme-icon').textContent = '[ GREEN_MODE ]';
    }

    // Typewriter Effect
    const typingContainer = document.getElementById('typing-container');
    const lines = [
        "LOGON: FALKEN",
        "GREETINGS PROFESSOR FALKEN.",
        "HOW ABOUT A NICE GAME OF CHESS?",
        "OR PERHAPS...",
        "PASSWORD ARENA"
    ];

    let lineIndex = 0;
    
    // Create cursor element
    const cursor = document.createElement('span');
    cursor.className = 'typewriter-cursor';

    function typeLine() {
        if (lineIndex >= lines.length) {
            typingContainer.appendChild(cursor);
            return;
        }

        const currentLineText = lines[lineIndex];
        const lineElement = document.createElement('p');
        typingContainer.appendChild(lineElement);
        lineElement.appendChild(cursor); // move cursor to current line

        let charIndex = 0;

        function typeChar() {
            if (charIndex < currentLineText.length) {
                // Insert character before the cursor
                const charNode = document.createTextNode(currentLineText.charAt(charIndex));
                lineElement.insertBefore(charNode, cursor);
                charIndex++;
                
                // Add some random variation to typing speed (like a modem or human)
                const delay = Math.random() * 50 + 50; 
                setTimeout(typeChar, delay);
            } else {
                // Line finished, wait a bit then start next line
                lineIndex++;
                setTimeout(typeLine, 800);
            }
        }

        typeChar();
    }

    // Start typing after a short delay
    setTimeout(typeLine, 1000);
});
