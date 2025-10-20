// Creative Interactions JavaScript for Expense Tracker

document.addEventListener('DOMContentLoaded', function() {
  // Enhanced 3D cube rotation
  const cube = document.querySelector('.expense-cube');
  if (cube) {
    let rotationX = 0;
    let rotationY = 0;
    
    // Auto-rotate
    setInterval(() => {
      rotationX += 0.5;
      rotationY += 0.5;
      cube.style.transform = `rotateX(${rotationX}deg) rotateY(${rotationY}deg) rotateZ(${rotationX * 0.5}deg)`;
    }, 50);
    
    // Mouse interaction
    cube.addEventListener('mousemove', (e) => {
      const rect = cube.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      
      const mouseX = e.clientX - centerX;
      const mouseY = e.clientY - centerY;
      
      const rotateY = mouseX * 0.1;
      const rotateX = -mouseY * 0.1;
      
      cube.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    });
    
    // Reset on mouse leave
    cube.addEventListener('mouseleave', () => {
      cube.style.transform = 'rotateX(0) rotateY(0)';
    });
  }
  
  // Particle animation enhancement
  const particles = document.querySelectorAll('.particle');
  particles.forEach((particle, index) => {
    // Randomize animation
    const delay = Math.random() * 5;
    const duration = 3 + Math.random() * 7;
    
    particle.style.animationDelay = `${delay}s`;
    particle.style.animationDuration = `${duration}s`;
    
    // Randomize size
    const size = 5 + Math.random() * 15;
    particle.style.width = `${size}px`;
    particle.style.height = `${size}px`;
    
    // Randomize position
    particle.style.left = `${Math.random() * 100}%`;
    particle.style.top = `${Math.random() * 100}%`;
  });
  
  // Holographic card tilt effect
  const cards = document.querySelectorAll('.holographic-card');
  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      
      const rotateY = (x - centerX) / 25;
      const rotateX = (centerY - y) / 25;
      
      card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    });
    
    card.addEventListener('mouseleave', () => {
      card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
    });
  });
  
  // Morphing shape color change
  const morphShape = document.querySelector('.morph-circle');
  if (morphShape) {
    let hue = 0;
    setInterval(() => {
      hue = (hue + 1) % 360;
      morphShape.style.background = `linear-gradient(45deg, hsl(${hue}, 100%, 60%), hsl(${(hue + 60) % 360}, 100%, 60%))`;
    }, 100);
  }
  
  // Interactive tracker enhancement
  const trackerMarkers = document.querySelectorAll('.tracker-marker');
  const trackerProgress = document.getElementById('trackerProgress');
  
  if (trackerMarkers.length > 0 && trackerProgress) {
    // Initialize progress
    setTimeout(() => {
      trackerProgress.style.width = '100%';
      trackerMarkers[trackerMarkers.length - 1].classList.add('active');
    }, 1000);
    
    // Add hover effects
    trackerMarkers.forEach(marker => {
      marker.addEventListener('mouseenter', function() {
        this.style.transform = 'translate(-50%, -50%) scale(1.3)';
      });
      
      marker.addEventListener('mouseleave', function() {
        this.style.transform = 'translate(-50%, -50%) scale(1)';
      });
    });
  }
  
  // Glow button enhancement
  const glowButtons = document.querySelectorAll('.glow-button');
  glowButtons.forEach(button => {
    button.addEventListener('mousemove', (e) => {
      const rect = button.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      button.style.background = `radial-gradient(circle at ${x}px ${y}px, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0.05))`;
    });
    
    button.addEventListener('mouseleave', () => {
      button.style.background = 'rgba(255, 255, 255, 0.1)';
    });
  });
  
  // Floating card enhancement
  const floatingCards = document.querySelectorAll('.floating-card');
  floatingCards.forEach((card, index) => {
    // Randomize animation delay
    card.style.animationDelay = `${index * 0.2}s`;
    
    // Add interactive hover effect
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      
      const moveX = (x - centerX) / 20;
      const moveY = (y - centerY) / 20;
      
      card.style.transform = `translateY(-10px) translate(${moveX}px, ${moveY}px)`;
    });
    
    card.addEventListener('mouseleave', () => {
      card.style.transform = 'translateY(-10px)';
    });
  });
});