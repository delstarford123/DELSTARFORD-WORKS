// --- 1. CONFIGURATION ---
const firebaseConfig = {
    apiKey: "AIzaSyCdbCJvC2-WdaEMQc_ZGaggqA_-SMf1DYU",
    authDomain: "delstarford-works.firebaseapp.com",
    projectId: "delstarford-works",
    storageBucket: "delstarford-works.firebasestorage.app",
    messagingSenderId: "735702460296",
    appId: "1:735702460296:web:8534ca0b1e86cc6a76bc3d",
    measurementId: "G-DHSQPE2MZW"
};

// --- 2. INITIALIZATION ---
// Check if Firebase is already running to prevent errors
if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
    console.log("Firebase: Connected");
} else {
    firebase.app(); // Use existing connection
}

// --- 3. MAKE IT GLOBAL ---
// This allows ANY page (Dashboard, Services, AI Lab) to just type 'db' or 'auth'
window.auth = firebase.auth();
window.db = firebase.database();
window.currentUser = null; // Will store user info globally