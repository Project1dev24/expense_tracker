// Main JavaScript for Trip Expense Tracker

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Format currency values
    document.querySelectorAll('.currency-value').forEach(function(element) {
        const value = parseFloat(element.textContent);
        if (!isNaN(value)) {
            element.textContent = formatCurrency(value);
        }
    });
    
    // Handle delete confirmations
    document.querySelectorAll('.delete-confirm').forEach(function(button) {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
                e.preventDefault();
            }
        });
    });
    
    // Handle form validations
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
    
    // Handle responsive button groups
    handleResponsiveButtons();
    
    // Add event listener for window resize
    window.addEventListener('resize', handleResponsiveButtons);
    
    // Handle responsive button groups for trip view
    handleTripViewButtons();
});

// Helper function to format currency values
function formatCurrency(value) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2
    }).format(value);
}

// Helper function to format dates
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}

// Helper function for calculating splits
function calculateEqualSplit(amount, participants) {
    if (!participants || participants.length === 0) return 0;
    return amount / participants.length;
}

// Function to toggle visibility of elements
function toggleElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        if (element.style.display === 'none') {
            element.style.display = 'block';
        } else {
            element.style.display = 'none';
        }
    }
}

// Function to handle AJAX requests
function fetchData(url, callback) {
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            callback(null, data);
        })
        .catch(error => {
            callback(error, null);
        });
}

// Function to submit data via AJAX
function submitData(url, method, data, callback) {
    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        callback(null, data);
    })
    .catch(error => {
        callback(error, null);
    });
}

// Function to handle responsive button groups
function handleResponsiveButtons() {
    const btnGroups = document.querySelectorAll('.btn-group');
    
    // On small screens, adjust button text and icons
    if (window.innerWidth < 576) {
        // Hide text on buttons and show only icons
        document.querySelectorAll('.btn span').forEach(function(span) {
            if (!span.classList.contains('d-sm-inline') && !span.classList.contains('d-md-inline') && !span.classList.contains('d-lg-inline')) {
                span.style.display = 'none';
            }
        });
        
        // Reduce padding on buttons
        document.querySelectorAll('.btn').forEach(function(btn) {
            btn.classList.add('btn-sm');
        });
    } else {
        // Show text on buttons
        document.querySelectorAll('.btn span').forEach(function(span) {
            span.style.display = '';
        });
        
        // Remove small button class if it was added
        document.querySelectorAll('.btn').forEach(function(btn) {
            btn.classList.remove('btn-sm');
        });
    }
}

// Function to handle responsive button groups for trip view
function handleTripViewButtons() {
    const tripViewButtons = document.querySelector('.trip-view-buttons');
    const btnGroup = tripViewButtons ? tripViewButtons.querySelector('.btn-group') : null;
    
    if (tripViewButtons && btnGroup) {
        if (window.innerWidth < 400) {
            // On very small screens, stack buttons vertically
            btnGroup.classList.add('flex-column');
            btnGroup.classList.remove('flex-wrap');
            
            // Adjust button text visibility
            const syncButton = tripViewButtons.querySelector('form button');
            if (syncButton) {
                const syncText = syncButton.querySelector('span');
                if (syncText) {
                    syncText.style.display = 'none';
                }
            }
        } else if (window.innerWidth < 768) {
            // On small screens, make buttons more compact
            btnGroup.classList.remove('flex-column');
            btnGroup.classList.add('flex-wrap');
            
            // Adjust button text visibility
            const syncButton = tripViewButtons.querySelector('form button');
            if (syncButton) {
                const syncText = syncButton.querySelector('span');
                if (syncText && window.innerWidth < 576) {
                    syncText.style.display = 'none';
                } else if (syncText) {
                    syncText.style.display = '';
                }
            }
        } else {
            // On larger screens, remove wrapping
            btnGroup.classList.remove('flex-column', 'flex-wrap');
            
            // Show all button text
            const syncButton = tripViewButtons.querySelector('form button span');
            if (syncButton) {
                syncButton.style.display = '';
            }
        }
    }
}

// Call handleTripViewButtons on resize
window.addEventListener('resize', handleTripViewButtons);