// Logout function for user profile
function logout() {
    console.log('🚪 Logging out...');
    // Clear all session storage
    sessionStorage.clear();
    // Clear any local storage if used
    localStorage.clear();
    // Redirect to login page
    window.location.href = '/login.html';
}
