// Main JavaScript for Complaint Management System

document.addEventListener('DOMContentLoaded', function () {
  // Mobile sidebar toggle
  const sidebar = document.querySelector('.app-sidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');
  const backdrop = document.querySelector('.sidebar-backdrop');

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('show');
    if (backdrop) backdrop.classList.remove('show');
  }

  if (sidebarToggle && sidebar && backdrop) {
    sidebarToggle.addEventListener('click', function () {
      sidebar.classList.toggle('show');
      backdrop.classList.toggle('show');
    });

    backdrop.addEventListener('click', closeSidebar);
  }

  if (sidebarCloseBtn) {
    sidebarCloseBtn.addEventListener('click', closeSidebar);
  }

  // Auto-dismiss standard alerts after 5 seconds
  const autoAlerts = document.querySelectorAll('.alert-dismissible');
  autoAlerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) {
        bsAlert.close();
      }
    }, 6000);
  });
});
