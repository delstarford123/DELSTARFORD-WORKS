
// Initialize Firebase (Compat Version)
if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
}
const database = firebase.database();
document.addEventListener('DOMContentLoaded', () => {
    console.log("Delstarford Works Engine Initialized...");
    
    // Existing initializers...
    initNavigation();
    initScrollAnimations();
    if (document.getElementById('totalPrice')) initPriceEstimator();
    if (document.getElementById('project-status')) initDashboard();
    if (document.getElementById('requestForm')) initContactForm(); // Custom Solutions Form
    
    // --- ADD THIS LINE ---
    if (document.getElementById('contactForm')) initGeneralContactForm(); // General Contact Form
});
document.addEventListener('DOMContentLoaded', () => {
    console.log("Delstarford Works Engine Initialized...");
    
    // Initialize specific modules based on current page
    initNavigation();
    initScrollAnimations(); // Added new animation initializer

    // Only run these if the elements exist on the page
    if (document.getElementById('totalPrice')) initPriceEstimator();
    if (document.getElementById('project-status')) initDashboard();
    if (document.getElementById('requestForm')) initContactForm();
});

// 2. NAVIGATION & UI EFFECTS
function initNavigation() {
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                navbar.classList.add('navbar-scrolled');
            } else {
                navbar.classList.remove('navbar-scrolled');
            }
        });
    }
}

// 3. SCROLL ANIMATIONS (The "Fade In" Effect)
function initScrollAnimations() {
    const observerOptions = {
        threshold: 0.1, // Trigger when 10% of element is visible
        rootMargin: "0px 0px -50px 0px"
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target); // Only animate once
            }
        });
    }, observerOptions);

    // Watch all elements with the class 'scroll-trigger'
    document.querySelectorAll('.scroll-trigger, .hero-content').forEach(el => {
        observer.observe(el);
    });
}

// 4. AI PRICE ESTIMATOR (Logic for Custom Solutions)
function initPriceEstimator() {
    const inputs = ['modelType', 'dataSize', 'complexity'];
    
    // Add event listeners to all estimator inputs
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            const eventType = el.type === 'range' ? 'input' : 'change';
            el.addEventListener(eventType, updatePrice);
        }
    });

    // Handle radio buttons for complexity
    document.querySelectorAll('input[name="complexity"]').forEach(radio => {
        radio.addEventListener('change', updatePrice);
    });

    // Initial calculation
    updatePrice();
}

async function updatePrice() {
    // Check if elements exist before reading values
    const modelEl = document.getElementById('modelType');
    const dataSizeEl = document.getElementById('dataSize');
    const complexityEl = document.querySelector('input[name="complexity"]:checked');

    if (!modelEl || !dataSizeEl || !complexityEl) return;

    const modelType = modelEl.value;
    const dataSize = dataSizeEl.value;
    const complexity = complexityEl.value;

    // Update UI labels
    const sizeLabel = document.getElementById('sizeLabel');
    if (sizeLabel) sizeLabel.innerText = Number(dataSize).toLocaleString();

    try {
        const response = await fetch('/calculate-estimate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ modelType, dataSize, complexity })
        });
        
        const data = await response.json();
        const priceEl = document.getElementById('totalPrice');
        if (priceEl) {
            priceEl.innerText = `${data.currency} ${data.estimate.toLocaleString()}`;
        }
    } catch (err) {
        console.error("Estimation failed:", err);
    }
}

// 5. REAL-TIME DASHBOARD SYNC
function initDashboard() {
    const userId = "user_123"; // Mock ID for now

    // Listen for Project Status
    database.ref(`active_projects/${userId}`).on('value', (snapshot) => {
        const data = snapshot.val();
        const statusEl = document.getElementById('project-status');
        if (statusEl && data) {
            statusEl.innerText = data.status;
            // Add a class for color coding (e.g., status-completed, status-in-progress)
            const statusClass = `status-${data.status.toLowerCase().replace(/[^a-z0-9]/g, '-')}`;
            statusEl.className = statusClass;
        }
    });

    // Listen for Activity Feed
    const feedDiv = document.getElementById('activity-feed');
    if (feedDiv) {
        database.ref(`users/${userId}/activity`).limitToLast(5).on('child_added', (snapshot) => {
            const activity = snapshot.val();
            const item = document.createElement('div');
            item.className = 'feed-item fade-in';
            item.innerHTML = `<strong>${activity.time || 'Just now'}:</strong> ${activity.message}`;
            feedDiv.prepend(item); // Newest items first
        });
    }
}

// 6. FORM SUBMISSIONS & FIREBASE LEADS
function initContactForm() {
    const form = document.getElementById('requestForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = form.querySelector('button');
        const originalText = btn.innerText;
        
        btn.innerText = "Sending...";
        btn.disabled = true;

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            // 1. Save to Firebase (Instant Admin Access)
            await database.ref('leads/service_requests').push({
                ...data,
                timestamp: Date.now(),
                source: "Website Form"
            });

            // 2. Trigger Python Backend (Email Sending)
            const response = await fetch('/custom', { method: 'POST', body: formData });
            const result = await response.json();

            alert(result.message || "Success! Delstarford Works has received your request.");
            form.reset();
        } catch (err) {
            console.error(err);
            alert("Connection error. Please check your internet and try again.");
        } finally {
            btn.innerText = originalText;
            btn.disabled = false;
        }
    });
}

// 7. GLOBAL UTILITIES
function submitToFirebase() {
    const priceEl = document.getElementById('totalPrice');
    const modelEl = document.getElementById('modelType');

    if (!priceEl || !modelEl) return;

    const finalPrice = priceEl.innerText;
    const model = modelEl.value;
    
    // Save the lead with the calculated price
    const requestRef = database.ref('leads/ai_requests').push();
    requestRef.set({
        client_name: "Interested Prospect", 
        model_type: model,
        estimated_price: finalPrice,
        timestamp: Date.now(),
        status: "Contact Pending"
    }).then(() => {
        alert("Your quote has been saved. Delstarford Works will contact you within 24 hours.");
    });
}
// 8. GENERAL CONTACT PAGE LOGIC
function initGeneralContactForm() {
    const form = document.getElementById('contactForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault(); // Stop page reload
        
        // UI Feedback
        const btn = document.getElementById('sendBtn') || form.querySelector('button');
        const originalText = btn.innerText;
        btn.innerText = "Sending...";
        btn.disabled = true;

        const formData = new FormData(form);

        try {
            // Send data to Python Backend
            const response = await fetch('/submit-contact', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok) {
                alert("Message Sent! Check your email for confirmation.");
                form.reset(); // Clear the form
            } else {
                alert("Error: " + (result.message || "Failed to send message."));
            }
        } catch (error) {
            console.error('Connection Error:', error);
            alert("Failed to connect to server. Please check your internet.");
        } finally {
            // Reset Button
            btn.innerText = originalText;
            btn.disabled = false;
        }
    });
}
/**
 * main.js
 * Handles Dashboard Authentication and Realtime Data
 */

document.addEventListener('DOMContentLoaded', () => {
    // AUTH LISTENER: This is the Gatekeeper
    // Ensure firebase is initialized in your base.html before this runs
    if (typeof firebase === 'undefined') {
        console.error("Firebase is not initialized!");
        return;
    }

    firebase.auth().onAuthStateChanged((user) => {
        const securityScreen = document.getElementById('security-screen');
        const mainDashboard = document.getElementById('main-dashboard');

        if (user) {
            // 1. User IS logged in -> Show Dashboard
            console.log("Access Granted: " + user.email);
            
            if (securityScreen) securityScreen.style.display = 'none';
            if (mainDashboard) mainDashboard.style.display = 'flex';
            
            // 2. Initialize Data
            initRealDashboard(user);
        } else {
            // 3. User is NOT logged in -> Kick them out
            console.log("Access Denied. Redirecting...");
            // Optional: Add a small delay so they see the spinner briefly
            window.location.href = "/login"; 
        }
    });
});

/**
 * Populates the dashboard with user data
 */
function initRealDashboard(user) {
    const db = firebase.database();
    const uid = user.uid;

    // --- 1. POPULATE PROFILE ---
    document.getElementById('display-name').innerText = user.displayName || "Member";
    document.getElementById('display-email').innerText = user.email;

    // Handle Profile Image
    if (user.photoURL) {
        const avatarCircle = document.querySelector('.avatar-circle');
        if (avatarCircle) {
            avatarCircle.innerHTML = `<img src="${user.photoURL}" alt="Profile" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;">`;
            avatarCircle.style.background = 'transparent';
        }
    }

    // --- 2. FETCH PROJECTS ---
    db.ref(`active_projects/${uid}`).on('value', (s) => {
        const d = s.val();
        const statusText = document.getElementById('project-status-text');
        const progressBar = document.getElementById('project-progress');

        if (statusText) statusText.innerText = d ? (d.status || "Active") : "No Projects";
        if (progressBar) progressBar.style.width = d ? (d.progress + "%") : "0%";
    });

    // --- 3. FETCH LICENSES ---
    db.ref(`users/${uid}/licenses`).on('value', s => {
        const licenseCount = document.getElementById('license-count');
        if (licenseCount) licenseCount.innerText = s.numChildren() || 0;
    });

    // --- 4. FETCH ACTIVITY LOG ---
    db.ref(`users/${uid}/activity`).limitToLast(5).on('value', (s) => {
        const rows = document.getElementById('activity-rows');
        if (!rows) return;

        rows.innerHTML = "";
        
        if (!s.exists()) {
            rows.innerHTML = `<tr><td colspan="3" class="text-center">No recent activity.</td></tr>`;
            return;
        }
        
        // Convert object to array and reverse to show newest first
        const acts = [];
        s.forEach(c => acts.unshift(c.val())); 

        acts.forEach(a => {
            rows.innerHTML += `
                <tr>
                    <td class="font-mono text-sm">${a.time || "Just now"}</td>
                    <td>${a.message}</td>
                    <td><span class="status-dot online"></span> Done</td>
                </tr>`;
        });
    });
}

/**
 * Global Logout Function
 * Attached to window so the HTML onclick="..." can find it
 */
window.handleLogout = function() {
    firebase.auth().signOut().then(() => {
        window.location.href = "/login";
    }).catch((error) => {
        console.error("Logout failed", error);
    });
};