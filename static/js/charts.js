// Charts for analytics section
let charts = {};

document.addEventListener('DOMContentLoaded', function() {
  // Initialize charts when analytics section is shown
  document.querySelectorAll('.sidebar-link').forEach(link => {
    if (link.dataset.section === 'analytics-section') {
      link.addEventListener('click', initCharts);
    }
  });
  
  // If analytics section is active on load, initialize charts
  if (document.getElementById('analytics-section').classList.contains('active')) {
    initCharts();
  }
});

function initCharts() {
  // Fetch data for charts
  fetch('/analytics/stats.json')
    .then(response => response.json())
    .then(data => {
      const stats = data.stats;
      const completionRate = data.completion_rate;
      
      createStatusChart(stats);
      createPriorityChart(stats);
      createCategoryChart(stats);
      createCompletionChart(completionRate);
    })
    .catch(error => {
      console.error('Error fetching analytics data:', error);
    });
}

// Create status distribution chart
function createStatusChart(stats) {
  const statusCtx = document.getElementById('status-chart');
  if (!statusCtx) return;
  
  // Destroy existing chart if it exists
  if (charts.statusChart) {
    charts.statusChart.destroy();
  }
  
  const statusLabels = Object.keys(stats.status_counts).map(s => s.charAt(0).toUpperCase() + s.slice(1));
  const statusData = Object.values(stats.status_counts);
  const statusColors = [
    '#4facfe', // pending
    '#00d084', // completed
    '#f6ad55'  // snoozed
  ];
  
  // Create new chart
  charts.statusChart = new Chart(statusCtx, {
    type: 'doughnut',
    data: {
      labels: statusLabels,
      datasets: [{
        data: statusData,
        backgroundColor: statusColors,
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary')
          }
        }
      }
    }
  });
}

// Create priority distribution chart
function createPriorityChart(stats) {
  const priorityCtx = document.getElementById('priority-chart');
  if (!priorityCtx) return;
  
  // Destroy existing chart if it exists
  if (charts.priorityChart) {
    charts.priorityChart.destroy();
  }
  
  const priorityLabels = Object.keys(stats.priority_counts).map(p => p.charAt(0).toUpperCase() + p.slice(1));
  const priorityData = Object.values(stats.priority_counts);
  const priorityColors = [
    '#38b2ac', // low
    '#4facfe', // medium
    '#f78ca0'  // high
  ];
  
  // Create new chart
  charts.priorityChart = new Chart(priorityCtx, {
    type: 'bar',
    data: {
      labels: priorityLabels,
      datasets: [{
        label: 'Tasks by Priority',
        data: priorityData,
        backgroundColor: priorityColors,
        borderWidth: 0,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            precision: 0,
            color: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary')
          },
          grid: {
            color: getComputedStyle(document.documentElement).getPropertyValue('--border-color')
          }
        },
        x: {
          ticks: {
            color: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary')
          },
          grid: {
            color: getComputedStyle(document.documentElement).getPropertyValue('--border-color')
          }
        }
      }
    }
  });
}

// Create category distribution chart
function createCategoryChart(stats) {
  const categoryCtx = document.getElementById('category-chart');
  if (!categoryCtx) return;
  
  // Destroy existing chart if it exists
  if (charts.categoryChart) {
    charts.categoryChart.destroy();
  }
  
  const categories = stats.category_distribution;
  const categoryLabels = Object.keys(categories);
  const categoryData = categoryLabels.map(cat => categories[cat].count);
  const categoryColors = categoryLabels.map(cat => categories[cat].color);
  
  // Create new chart
  charts.categoryChart = new Chart(categoryCtx, {
    type: 'pie',
    data: {
      labels: categoryLabels,
      datasets: [{
        data: categoryData,
        backgroundColor: categoryColors,
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            boxWidth: 15,
            color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary')
          }
        }
      }
    }
  });
}

// Create completion rate chart
function createCompletionChart(completionRate) {
  const completionCtx = document.getElementById('completion-chart');
  if (!completionCtx) return;
  
  // Destroy existing chart if it exists
  if (charts.completionChart) {
    charts.completionChart.destroy();
  }
  
  const completionData = [completionRate.completed, completionRate.created - completionRate.completed];
  
  // Create new chart
  charts.completionChart = new Chart(completionCtx, {
    type: 'doughnut',
    data: {
      labels: ['Completed', 'Pending'],
      datasets: [{
        data: completionData,
        backgroundColor: ['#00f2c3', '#e2e8f0'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '80%',
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const label = context.label || '';
              const value = context.raw || 0;
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const percentage = ((value / total) * 100).toFixed(1);
              return `${label}: ${value} (${percentage}%)`;
            }
          }
        }
      }
    }
  });
}

// Update charts when theme changes
function updateCharts() {
  // Chart.js automatically uses the correct colors when redrawn
  Object.values(charts).forEach(chart => {
    if (chart) {
      chart.update();
    }
  });
}

// Make updateCharts available globally
window.updateCharts = updateCharts;
