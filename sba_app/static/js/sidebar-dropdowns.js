// Sidebar dropdown functionality
document.addEventListener('DOMContentLoaded', function() {
    // Get all dropdown toggles
    const dropdownToggles = document.querySelectorAll('.sidebar-dropdown .dropdown-toggle');
    
    // Check if we're in mobile mode
    function isMobile() {
        return window.innerWidth <= 767;
    }
    
    // Restore dropdown states from localStorage
    function restoreDropdownStates() {
        const savedStates = localStorage.getItem('sidebarDropdownStates');
        if (savedStates) {
            const states = JSON.parse(savedStates);
            dropdownToggles.forEach(toggle => {
                const dropdown = toggle.closest('.sidebar-dropdown');
                const dropdownId = dropdown.querySelector('.dropdown-toggle span').textContent.trim();
                if (states[dropdownId]) {
                    dropdown.classList.add('expanded');
                }
            });
        }
    }
    
    // Save dropdown states to localStorage
    function saveDropdownStates() {
        const states = {};
        dropdownToggles.forEach(toggle => {
            const dropdown = toggle.closest('.sidebar-dropdown');
            const dropdownId = dropdown.querySelector('.dropdown-toggle span').textContent.trim();
            states[dropdownId] = dropdown.classList.contains('expanded');
        });
        localStorage.setItem('sidebarDropdownStates', JSON.stringify(states));
    }
    
    // Restore states on page load
    restoreDropdownStates();
    
    dropdownToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Get the parent dropdown container
            const dropdown = this.closest('.sidebar-dropdown');
            
            // Toggle the expanded class
            dropdown.classList.toggle('expanded');
            
            // Save the current state
            saveDropdownStates();
            
            // In mobile mode, FORCE sidebar to stay open
            if (isMobile()) {
                const sidebar = document.getElementById('sidebar');
                const overlay = document.getElementById('sidebarOverlay');
                const toggleBtn = document.getElementById('sidebarToggle');
                
                if (sidebar && overlay) {
                    // Force sidebar to stay open
                    sidebar.classList.add('active');
                    overlay.style.display = 'block';
                    
                    // Hide toggle button when sidebar is open
                    if (toggleBtn) {
                        toggleBtn.style.display = 'none';
                    }
                }
                
                // Prevent any other event handlers from running
                setTimeout(() => {
                    const sidebar = document.getElementById('sidebar');
                    const overlay = document.getElementById('sidebarOverlay');
                    if (sidebar && overlay) {
                        sidebar.classList.add('active');
                        overlay.style.display = 'block';
                    }
                }, 10);
            }
        });
    });
    
    // Save states when clicking on dropdown links (sub-items)
    const dropdownLinks = document.querySelectorAll('.sidebar-dropdown .dropdown-menu .sidebar-link');
    dropdownLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Save current states before navigation
            saveDropdownStates();
            
            // In mobile mode, let the sidebar close normally after navigation
            // The state will be restored when the new page loads
        });
    });
    
    // Close dropdowns when clicking outside - but not when clicking on dropdown items
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.sidebar-dropdown')) {
            dropdownToggles.forEach(toggle => {
                const dropdown = toggle.closest('.sidebar-dropdown');
                dropdown.classList.remove('expanded');
            });
            // Clear states when closing all dropdowns
            localStorage.removeItem('sidebarDropdownStates');
        }
    });
    
    // Handle window resize
    window.addEventListener('resize', function() {
        if (!isMobile()) {
            // In desktop mode, restore states
            restoreDropdownStates();
        }
    });
    
    // Additional mobile-specific handling
    if (isMobile()) {
        // Intercept any sidebar close attempts when clicking dropdown toggles
        const originalSidebarLinks = document.querySelectorAll('.sidebar-link:not(.dropdown-toggle)');
        originalSidebarLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                // Only allow normal navigation for non-dropdown links
                if (!this.closest('.sidebar-dropdown')) {
                    // Normal navigation - let sidebar close
                } else {
                    // This is a dropdown item, handle normally
                }
            });
        });
    }
});
