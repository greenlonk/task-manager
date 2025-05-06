// Task Manager App JavaScript
document.addEventListener('DOMContentLoaded', () => {
  // Initialize theme based on user preference or previous setting
  initTheme();
  
  // Initialize Feather icons
  if (typeof feather !== 'undefined') {
    feather.replace();
  }
  
  // Setup theme toggle
  setupThemeToggle();
  
  // Handle file input display
  setupFileInputs();
  
  // Initialize cron description previews
  setupCronPreviews();
  
  // Set up category color previews
  setupCategoryColorPreviews();
  
  // Set up task filtering
  setupTaskFiltering();
  
  // Initialize task counts
  updateTaskCounts();
  
  // Store settings in local storage
  setupSettingsPersistence();
});

// Initialize theme based on user preference
function initTheme() {
  // Check for saved theme preference or prefer-color-scheme
  const savedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  
  if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
    document.documentElement.setAttribute('data-theme', 'dark');
    updateThemeIcon('dark');
  } else {
    document.documentElement.setAttribute('data-theme', 'light');
    updateThemeIcon('light');
  }
}

// Setup theme toggle functionality
function setupThemeToggle() {
  const themeToggle = document.getElementById('theme-toggle');
  if (!themeToggle) return;
  
  themeToggle.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    // Apply transition class for smooth theme change
    document.body.classList.add('dark-mode-transition');
    
    // Update theme
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
    
    // Small delay to ensure transition happens
    setTimeout(() => {
      document.body.classList.remove('dark-mode-transition');
    }, 500);
    
    // Update charts if they exist
    if (window.updateCharts) {
      window.updateCharts();
    }
  });
}

// Update the theme toggle icon based on current theme
function updateThemeIcon(theme) {
  const themeToggle = document.getElementById('theme-toggle');
  if (!themeToggle) return;
  
  if (theme === 'dark') {
    themeToggle.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    `;
  } else {
    themeToggle.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
      </svg>
    `;
  }
}

// Setup file input display
function setupFileInputs() {
  document.querySelectorAll('.file-input').forEach(input => {
    const fileNameElement = document.getElementById(input.id + '-name') || 
                            document.querySelector('.file-name');
    
    if (input && fileNameElement) {
      input.addEventListener('change', function() {
        if (this.files.length > 0) {
          fileNameElement.textContent = this.files[0].name;
        } else {
          fileNameElement.textContent = 'No file selected';
        }
      });
    }
  });
}

// Setup cron expression previews
function setupCronPreviews() {
  document.querySelectorAll('input[name="cron"]').forEach(input => {
    const previewElement = document.getElementById('cron-preview');
    if (!previewElement) return;
    
    // Update preview on input
    input.addEventListener('input', function() {
      updateCronPreview(this.value, previewElement);
    });
    
    // Initial preview
    if (input.value) {
      updateCronPreview(input.value, previewElement);
    }
    
    // Handle preset buttons
    document.querySelectorAll('.cron-preset').forEach(button => {
      button.addEventListener('click', function() {
        const cronValue = this.dataset.cron;
        input.value = cronValue;
        updateCronPreview(cronValue, previewElement);
      });
    });
  });
}

// Update cron description preview
function updateCronPreview(cronExpression, previewElement) {
  if (!window.cronstrue) return;
  
  try {
    if (cronExpression.trim()) {
      const description = cronstrue.toString(cronExpression.trim());
      previewElement.textContent = description;
      previewElement.classList.remove('error');
    } else {
      previewElement.textContent = 'Enter a cron expression';
      previewElement.classList.remove('error');
    }
  } catch (e) {
    previewElement.textContent = 'Invalid cron expression';
    previewElement.classList.add('error');
  }
}

// Setup category color previews
function setupCategoryColorPreviews() {
  const colorInput = document.querySelector('input[type="color"]');
  if (!colorInput) return;
  
  colorInput.addEventListener('input', function() {
    // Use the color for the input background
    this.style.backgroundColor = this.value;
    this.style.borderColor = this.value;
  });
  
  // Initialize color
  if (colorInput.value) {
    colorInput.style.backgroundColor = colorInput.value;
    colorInput.style.borderColor = colorInput.value;
  }
}

// Setup task filtering persistence
function setupTaskFiltering() {
  // Save filters to session storage when changed
  document.querySelectorAll('#status-filter, #category-filter, #priority-filter, #sort-filter, #sort-direction').forEach(filter => {
    filter.addEventListener('change', function() {
      sessionStorage.setItem(this.id, this.value);
    });
    
    // Load saved filter value if exists
    const savedValue = sessionStorage.getItem(filter.id);
    if (savedValue) {
      filter.value = savedValue;
    }
  });
}

// Update task counts in UI
function updateTaskCounts() {
  const taskRows = document.querySelectorAll('.task-row');
  const totalTasksElement = document.getElementById('total-tasks-count');
  const activeTasksElement = document.getElementById('active-tasks-count');
  
  if (totalTasksElement) {
    totalTasksElement.textContent = taskRows.length;
  }
  
  if (activeTasksElement) {
    const activeTasks = document.querySelectorAll('.task-row.pending-task').length;
    activeTasksElement.textContent = activeTasks;
  }
}

// Store user settings in local storage
function setupSettingsPersistence() {
  const defaultTopicInput = document.getElementById('default-topic');
  const defaultTimezoneSelect = document.getElementById('default-timezone');
  const saveSettingsBtn = document.getElementById('save-settings');
  
  if (!defaultTopicInput || !defaultTimezoneSelect || !saveSettingsBtn) return;
  
  // Load saved settings
  defaultTopicInput.value = localStorage.getItem('default-topic') || '';
  defaultTimezoneSelect.value = localStorage.getItem('default-timezone') || 'Europe/Berlin';
  
  // Save settings
  saveSettingsBtn.addEventListener('click', function() {
    localStorage.setItem('default-topic', defaultTopicInput.value);
    localStorage.setItem('default-timezone', defaultTimezoneSelect.value);
    
    // Show confirmation
    const confirmation = document.createElement('div');
    confirmation.className = 'settings-saved';
    confirmation.textContent = 'Settings saved';
    this.parentNode.appendChild(confirmation);
    
    setTimeout(() => {
      confirmation.remove();
    }, 2000);
  });
}

// Handle task actions via delegation
document.addEventListener('click', function(event) {
  // Handle task detail view
  if (event.target.closest('.view-task-btn')) {
    const button = event.target.closest('.view-task-btn');
    const taskId = button.dataset.taskId;
    openTaskDetail(taskId);
  }
  
  // Close modal when clicking outside content or on close button
  if (event.target.classList.contains('modal') || event.target.closest('.close-modal')) {
    closeTaskDetail();
  }
});

// Open task detail modal
function openTaskDetail(taskId) {
  const modal = document.getElementById('task-modal');
  if (!modal) return;
  
  // Show modal and load content
  modal.classList.add('show');
  modal.querySelector('.modal-content').innerHTML = '<div class="loader"></div>';
  
  fetch(`/task/${taskId}`)
    .then(response => response.text())
    .then(html => {
      modal.querySelector('.modal-content').innerHTML = html;
      if (typeof feather !== 'undefined') {
        feather.replace();
      }
    });
}

// Close task detail modal
function closeTaskDetail() {
  const modal = document.getElementById('task-modal');
  if (modal) {
    modal.classList.remove('show');
  }
}

// HTMX events for UI feedback
document.body.addEventListener('htmx:beforeSwap', function(event) {
  const targetElement = document.querySelector(event.detail.target);
  if (targetElement) {
    targetElement.style.opacity = '0.5';
    targetElement.style.transition = 'opacity 0.3s ease';
  }
});

document.body.addEventListener('htmx:afterSwap', function(event) {
  const targetElement = document.querySelector(event.detail.target);
  if (targetElement) {
    targetElement.style.opacity = '1';
    
    // Reinitialize feather icons
    if (typeof feather !== 'undefined') {
      feather.replace();
    }
    
    // Update task counts
    updateTaskCounts();
  }
});

// Form submission animation
document.addEventListener('submit', function(event) {
  const form = event.target;
  const submitButton = form.querySelector('button[type="submit"]');
  
  if (submitButton) {
    submitButton.classList.add('pulse');
    setTimeout(() => {
      submitButton.classList.remove('pulse');
    }, 1000);
  }
});
